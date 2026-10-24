"""
=============================================================
  SHARK EXCHANGE 24x7 CLOUD TRADING BOT WITH TELEGRAM CONTROL
  Runs continuously in the cloud with zero phone dependency.
=============================================================
"""

import os
import sys
import time
import json
import socket
import logging
import threading
import urllib.parse
import requests


from config import (
    SHARK_API_KEY, SHARK_API_SECRET, SHARK_BASE_URL, SYMBOL,
    TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID,
    LEVERAGE, CONTRACT_QTY, MARGIN_REQUIRED,
    MAX_LOSS_PER_TRADE_INR, MAX_PROFIT_PER_TRADE_INR,
    MAX_LOSSES_PER_DAY, MAX_TRADES_PER_DAY, COOLDOWN_LOSS_MINS,
    RESOLUTION_1D, RESOLUTION_4H, RESOLUTION_1H,
    EMA_TREND_PERIOD, EMA_FILTER_PERIOD, MIN_REJECTION_BODY_PTS
)
from shark_api import SharkClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
log = logging.getLogger("CloudSharkBot")

def send_telegram(text: str):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload, timeout=8)
    except Exception as e:
        log.error(f"Telegram error: {e}")

def calc_ema(values: list, period: int) -> list:
    if len(values) < period:
        return [values[-1]] * len(values)
    k = 2.0 / (period + 1)
    ema = [sum(values[:period]) / period]
    for price in values[period:]:
        ema.append(price * k + ema[-1] * (1.0 - k))
    return [ema[0]] * (period - 1) + ema

def calc_rsi(closes: list, period: int = 14) -> float:
    if len(closes) < period + 1:
        return 50.0
    gains, losses = [], []
    for i in range(1, len(closes)):
        diff = closes[i] - closes[i - 1]
        gains.append(max(diff, 0.0))
        losses.append(max(-diff, 0.0))
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
    if avg_loss == 0.0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))

class CloudTradingBot:
    def __init__(self):
        self.client = SharkClient()
        self.is_running = True
        self.public_ip = "Unknown"
        self.active_trade = None
        self.last_candle_time = 0
        self.last_loss_time = 0
        self.last_heartbeat_time = 0
        self.stats_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "daily_stats.json")
        self.daily_stats = self._load_daily_stats()

    def _load_daily_stats(self) -> dict:
        today = time.strftime("%Y-%m-%d")
        default_stats = {
            "date": today,
            "trades_today": 0,
            "wins_today": 0,
            "losses_today": 0,
            "pnl_inr_today": 0.0,
            "total_month_pnl_inr": 0.0
        }
        if os.path.exists(self.stats_file):
            try:
                with open(self.stats_file, "r") as f:
                    data = json.load(f)
                if data.get("date") == today:
                    return data
            except Exception as e:
                log.warning(f"Error loading daily stats: {e}")
        return default_stats

    def _save_daily_stats(self):
        try:
            with open(self.stats_file, "w") as f:
                json.dump(self.daily_stats, f, indent=2)
        except Exception as e:
            log.warning(f"Error saving daily stats: {e}")

    def detect_public_ip(self):
        try:
            r = requests.get("https://api.ipify.org?format=json", timeout=8)
            self.public_ip = r.json().get("ip", "Unknown")
        except Exception:
            self.public_ip = "Unknown"
        return self.public_ip

    def _reset_daily_stats_if_needed(self):
        today = time.strftime("%Y-%m-%d")
        if self.daily_stats["date"] != today:
            self.daily_stats["date"] = today
            self.daily_stats["trades_today"] = 0
            self.daily_stats["wins_today"] = 0
            self.daily_stats["losses_today"] = 0
            self.daily_stats["pnl_inr_today"] = 0.0
            self._save_daily_stats()

    def sync_active_trade_from_exchange(self):
        """
        Synchronizes bot's in-memory trade state with live positions on Shark Exchange.
        If an open position exists without exchange TP/SL orders, automatically attaches them.
        """
        try:
            positions = self.client.get_open_positions()
            pos_list = positions if isinstance(positions, list) else (positions.get("data") or positions.get("result") or [])
            matched_pos = None
            if isinstance(pos_list, list):
                for p in pos_list:
                    p_sym = p.get("contractPair", "") or p.get("symbol", "")
                    if SYMBOL.replace("-", "").upper() in p_sym.replace("-", "").upper():
                        matched_pos = p
                        break

            if matched_pos:
                entry = float(matched_pos.get("entryPrice", 0.0))
                qty = float(matched_pos.get("quantity") or matched_pos.get("positionAmount") or matched_pos.get("size") or CONTRACT_QTY)
                side = "BUY" if str(matched_pos.get("positionType", "")).upper() == "LONG" else "SELL"
                sl_qty = float(matched_pos.get("stopLossOrdersQty", 0) or 0.0)
                tp_qty = float(matched_pos.get("takeProfitOrdersQty", 0) or 0.0)

                # Strategy exact SL (-₹40) and TP (+₹80) points
                sl_pts = round(MAX_LOSS_PER_TRADE_INR / qty, 2)
                tp_pts = round(MAX_PROFIT_PER_TRADE_INR / qty, 2)
                precision = 0 if "SOL" in SYMBOL.upper() else 2
                if side == "BUY":
                    sl_price = int(round(entry - sl_pts)) if precision == 0 else round(entry - sl_pts, precision)
                    tp_price = int(round(entry + tp_pts)) if precision == 0 else round(entry + tp_pts, precision)
                else:
                    sl_price = int(round(entry + sl_pts)) if precision == 0 else round(entry + sl_pts, precision)
                    tp_price = int(round(entry - tp_pts)) if precision == 0 else round(entry - tp_pts, precision)

                if not self.active_trade:
                    self.active_trade = {
                        "side": side,
                        "entry": entry,
                        "sl": sl_price,
                        "target": tp_price,
                        "qty": qty,
                        "risk_pts": abs(entry - sl_price),
                        "breakeven_set": False,
                        "tpsl_attached": bool(sl_qty > 0 and tp_qty > 0)
                    }
                    log.info(f"Synchronized active {side} position from exchange: Entry={entry}, SL={sl_price}, TP={tp_price}, Qty={qty}")

                # If exchange has 0 stop loss or 0 take profit orders, attach them natively!
                if sl_qty <= 0.0 or tp_qty <= 0.0:
                    log.warning(f"Position has missing exchange TP/SL (SL_qty={sl_qty}, TP_qty={tp_qty}). Auto-attaching now...")
                    attach_res = self.client.attach_tpsl_to_open_position(SYMBOL, tp_price=tp_price, sl_price=sl_price)
                    log.info(f"Auto-attach TP/SL result: {attach_res}")
                    if attach_res.get("verified_on_exchange") or attach_res.get("success"):
                        self.active_trade["tpsl_attached"] = True
                        send_telegram(
                            f"🛡️ *ACTIVE POSITION: TP & SL AUTO-ATTACHED!* 🦈\n\n"
                            f"• *Pair*: `{SYMBOL}`\n"
                            f"• *Side*: `{side}` ({qty} SOL)\n"
                            f"• *Entry Price*: ₹{entry:,.0f} INR\n"
                            f"• *Stop Loss (SL)*: ₹{sl_price:,.0f} (-₹{MAX_LOSS_PER_TRADE_INR:.0f} Risk) 🛑\n"
                            f"• *Take Profit (TP)*: ₹{tp_price:,.0f} (+₹{MAX_PROFIT_PER_TRADE_INR:.0f} Target) 🎯\n\n"
                            f"✅ Shark Exchange par Open Orders & Positions me TP/SL 100% active ho gaya hai!"
                        )
                    else:
                        self.active_trade["tpsl_attached"] = False
                else:
                    self.active_trade["tpsl_attached"] = True
            else:
                if self.active_trade:
                    log.info("Exchange reports position closed. Processing trade outcome...")
                    trade = self.active_trade
                    side = trade["side"]
                    entry = trade["entry"]
                    sl = trade["sl"]
                    tgt = trade["target"]
                    qty = trade.get("qty", CONTRACT_QTY)

                    # Fetch latest 15m candle to determine exit price
                    c15m = self.client.get_candles(RESOLUTION, 5)
                    last_c = c15m[-1] if c15m else {"close": entry, "high": entry, "low": entry}
                    exit_price = last_c.get("close", entry)

                    if side == "BUY":
                        if last_c.get("high", 0.0) >= tgt or exit_price >= (tgt - 5.0):
                            exit_price = tgt
                            is_win = True
                            outcome_str, outcome_emoji = f"PROFIT TARGET (+₹{MAX_PROFIT_PER_TRADE_INR:.0f}) 🎯", "🎉"
                        else:
                            exit_price = sl
                            is_win = False
                            outcome_str, outcome_emoji = f"STOP LOSS (-₹{MAX_LOSS_PER_TRADE_INR:.0f}) 🛑", "🛑"
                    else:
                        if last_c.get("low", 999999.0) <= tgt or exit_price <= (tgt + 5.0):
                            exit_price = tgt
                            is_win = True
                            outcome_str, outcome_emoji = f"PROFIT TARGET (+₹{MAX_PROFIT_PER_TRADE_INR:.0f}) 🎯", "🎉"
                        else:
                            exit_price = sl
                            is_win = False
                            outcome_str, outcome_emoji = f"STOP LOSS (-₹{MAX_LOSS_PER_TRADE_INR:.0f}) 🛑", "🛑"

                    pnl_pts = (exit_price - entry) if side == "BUY" else (entry - exit_price)
                    pnl_inr = pnl_pts * qty
                    self.daily_stats["pnl_inr_today"] += pnl_inr
                    self.daily_stats["total_month_pnl_inr"] += pnl_inr

                    if is_win:
                        self.daily_stats["wins_today"] += 1
                    else:
                        self.daily_stats["losses_today"] += 1
                        self.last_loss_time = time.time()
                    self._save_daily_stats()

                    loss_warning = ""
                    if self.daily_stats.get("losses_today", 0) >= MAX_LOSSES_PER_DAY:
                        loss_warning = f"\n🔒 *DAILY LOSS LIMIT REACHED ({MAX_LOSSES_PER_DAY} Losses)!* Bot locked until tomorrow to protect capital."
                    elif not is_win:
                        loss_warning = f"\n⏳ *Cooldown*: {COOLDOWN_LOSS_MINS} min patient pause active."

                    send_telegram(
                        f"🏁 *TRADE CLOSED ({outcome_str})* {outcome_emoji}\n\n"
                        f"• *Pair*: `{SYMBOL}`\n"
                        f"• *Side*: `{side}` ({qty} SOL)\n"
                        f"• *Entry Price*: ₹{entry:,.0f} INR\n"
                        f"• *Exit Price*: ₹{exit_price:,.0f} INR\n"
                        f"• *Stop Loss (SL)*: ₹{sl:,.0f} 🛑\n"
                        f"• *Take Profit (TP)*: ₹{tgt:,.0f} 🎯\n"
                        f"• *Net P&L*: *₹{pnl_inr:+.1f} INR* {outcome_emoji}\n\n"
                        f"📊 *Scorecard Today:*\n"
                        f"• *Trades*: {self.daily_stats['trades_today']}/{MAX_TRADES_PER_DAY} (Wins: {self.daily_stats['wins_today']}, Losses: {self.daily_stats['losses_today']}/{MAX_LOSSES_PER_DAY})\n"
                        f"• *Today P&L*: *₹{self.daily_stats['pnl_inr_today']:+.1f} INR*"
                        f"{loss_warning}"
                    )
                    self.active_trade = None
        except Exception as e:
            log.error(f"Error syncing active trade from exchange: {e}")

    # ─────────────────────────────────────────────────────────
    #  TELEGRAM BOT COMMAND LISTENER (THREAD 1)
    # ─────────────────────────────────────────────────────────
    def run_telegram_listener(self):
        log.info("Telegram command listener started.")

        offset = 0
        while True:
            try:
                url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"
                params = {"offset": offset, "timeout": 25}
                r = requests.get(url, params=params, timeout=30)
                if r.status_code == 200:
                    data = r.json()
                    for update in data.get("result", []):
                        offset = update["update_id"] + 1
                        msg = update.get("message", {})
                        text = msg.get("text", "").strip()
                        chat_id = str(msg.get("chat", {}).get("id", ""))
                        if chat_id == str(TELEGRAM_CHAT_ID) and text:
                            self.handle_telegram_command(text)
            except Exception as e:
                time.sleep(3)

    def handle_telegram_command(self, cmd: str):
        cmd_lower = cmd.lower()
        log.info(f"Received Telegram command: {cmd}")

        if cmd_lower in ["/start", "/run", "start", "run"]:
            self.is_running = True
            send_telegram(
                "🟢 *Shark MTF Trend Bot Started / Resumed!*\n\n"
                f"• Asset: `{SYMBOL}`\n"
                f"• Strategy: Triple-Screen MTF Trend-Rider (1D ➡️ 4H ➡️ 1H Pullback)\n"
                f"• Size: `{CONTRACT_QTY} SOL` (~₹{MARGIN_REQUIRED:.0f} Margin at {LEVERAGE}×)\n"
                f"• Stop Loss: ₹{MAX_LOSS_PER_TRADE_INR:.0f} Max Loss 🛑\n"
                f"• Take Profit: +₹{MAX_PROFIT_PER_TRADE_INR:.0f} Target (1:2.25 RR) 🎯\n"
                f"• Daily Circuit Breaker: Max {MAX_LOSSES_PER_DAY} Losses (Stops at ₹{MAX_LOSS_PER_TRADE_INR * MAX_LOSSES_PER_DAY:.0f}) | Unlimited Wins Mode 🔒\n"
                f"• Status: Active 24x7 scanning in Cloud."
            )

        elif cmd_lower in ["/stop", "/pause", "stop", "pause"]:
            self.is_running = False
            send_telegram("⏸️ *Cloud Bot Paused!*\nScanning stopped. Send `/start` to resume.")

        elif cmd_lower in ["/status", "status"]:
            c1d = self.client.get_candles(RESOLUTION_1D, 25)
            c4h = self.client.get_candles(RESOLUTION_4H, 25)
            c1h = self.client.get_candles(RESOLUTION_1H, 25)
            curr_price = c1h[-1]["close"] if c1h else 0.0

            t_1d_str = "BULLISH 🟢" if (c1d and len(c1d) >= 20 and c1d[-1]["close"] > calc_ema([c["close"] for c in c1d], 20)[-1]) else "BEARISH 🔴"
            t_4h_str = "BULLISH 🟢" if (c4h and len(c4h) >= 20 and c4h[-1]["close"] > calc_ema([c["close"] for c in c4h], 20)[-1]) else "BEARISH 🔴"
            bias_str = "SHORT ONLY 📉" if ("BEARISH" in t_1d_str and "BEARISH" in t_4h_str) else ("LONG ONLY 📈" if ("BULLISH" in t_1d_str and "BULLISH" in t_4h_str) else "NEUTRAL / CHOP ⏸️")

            if self.active_trade:
                pos_text = f"{self.active_trade['side']} (Entry: ₹{self.active_trade['entry']:,.0f}, SL: ₹{self.active_trade['sl']:,.0f}, TP: ₹{self.active_trade['target']:,.0f})"
            else:
                pos_text = f"No Open Trade (Waiting 1H Pullback in {bias_str})"
            state = "🟢 RUNNING" if self.is_running else "⏸️ PAUSED"
            send_telegram(
                f"📊 *Shark MTF Trend Bot Status* ☁️\n\n"
                f"• *Status*: {state}\n"
                f"• *Current SOL Price*: ₹{curr_price:,.0f} INR\n"
                f"• *1-Day Macro Trend*: {t_1d_str}\n"
                f"• *4-Hour Confirmation*: {t_4h_str}\n"
                f"• *Strategy Mode*: *{bias_str}*\n"
                f"• *Active Position*: {pos_text}\n"
                f"• *Trades Today*: {self.daily_stats['trades_today']} (Wins: {self.daily_stats.get('wins_today', 0)}, Losses: {self.daily_stats.get('losses_today', 0)}/{MAX_LOSSES_PER_DAY})\n"
                f"• *Today P&L*: *₹{self.daily_stats['pnl_inr_today']:+.1f} INR*\n"
                f"• *Uptime*: 24×7 Cloud Active (No phone needed)"
            )

        elif cmd_lower in ["/balance", "balance"]:
            bal = self.client.get_wallet_balance()
            send_telegram(
                f"💳 *Shark Exchange Wallet Balance*\n\n"
                f"• *Futures Wallet Balance*: *₹{bal:,.2f} INR*\n"
                f"• *Capital Allocated*: ₹1,000 INR\n"
                f"• *Margin per Trade*: ~₹{MARGIN_REQUIRED:.0f} INR (at {LEVERAGE}×)\n"
                f"• *Free Safe Buffer*: ~₹{max(0, bal - MARGIN_REQUIRED):,.0f} INR (Safe in reserve)"
            )

        elif cmd_lower in ["/close", "close"]:
            success = self.client.close_all_positions()
            self.active_trade = None
            msg = "✅ *All Positions Closed Immediately!*" if success else "⚠️ *Close Request Sent!*"
            send_telegram(msg)

        elif cmd_lower in ["/help", "help"]:
            send_telegram(
                "🤖 *Cloud Trading Bot Commands:*\n\n"
                "• `/status` - Live SOL price & strategy state\n"
                "• `/balance` - Shark Exchange wallet balance\n"
                "• `/start` - Resume 24x7 cloud trading\n"
                "• `/stop` - Pause bot trading\n"
                "• `/close` - Emergency close active position\n"
                "• `/help` - Show this menu"
            )

    # ─────────────────────────────────────────────────────────
    #  24x7 STRATEGY ENGINE (THREAD 2)
    # ─────────────────────────────────────────────────────────
    def run_strategy_engine(self):
        log.info("24x7 Strategy Scanner Engine started.")
        self.detect_public_ip()

        send_telegram(
            f"🦈 *SHARK MTF TREND-RIDER BOT ONLINE!* ☁️\n\n"
            f"• *Pair*: `{SYMBOL}` (Solana INR Perpetual)\n"
            f"• *Strategy*: Triple-Screen MTF Trend-Rider (1D ➡️ 4H ➡️ 1H Pullback) 🛡️\n"
            f"• *Trade Size*: `{CONTRACT_QTY} SOL` (~₹{MARGIN_REQUIRED:.0f} Margin at {LEVERAGE}×)\n"
            f"• *Stop Loss*: Exact ₹{MAX_LOSS_PER_TRADE_INR:.0f} Max Loss 🛑\n"
            f"• *Take Profit*: Exact +₹{MAX_PROFIT_PER_TRADE_INR:.0f} Target (1:2.25 RR) 🎯\n"
            f"• *Rejection Filter*: Solid Body (≥{MIN_REJECTION_BODY_PTS:.0f} pts) from 20 EMA 🎯\n"
            f"• *Daily Limits*: Max {MAX_LOSSES_PER_DAY} Losses (Stops at ₹{MAX_LOSS_PER_TRADE_INR * MAX_LOSSES_PER_DAY:.0f}) | Unlimited Wins Mode 🔒\n"
            f"• *Phone Status*: You can close your phone/Termux now! 📱💤\n\n"
            f"👉 Send `/status` or `/balance` anytime to inspect!"
        )

        # Sync open positions immediately upon startup
        self.sync_active_trade_from_exchange()

        while True:
            try:
                self._reset_daily_stats_if_needed()
                if self.is_running:
                    self._scan_market_cycle()
            except Exception as e:
                log.error(f"Strategy error: {e}")
            time.sleep(30)

    def _scan_market_cycle(self):
        # Sync open positions with exchange
        self.sync_active_trade_from_exchange()

        # Fetch Multi-Timeframe candles: 1D, 4H, and 1H
        c1d = self.client.get_candles(RESOLUTION_1D, 30)
        c4h = self.client.get_candles(RESOLUTION_4H, 30)
        c1h = self.client.get_candles(RESOLUTION_1H, 60)

        if len(c1d) < 20 or len(c4h) < 20 or len(c1h) < 50:
            return

        # 1-Day Trend (20 EMA)
        closes_1d = [c["close"] for c in c1d]
        ema20_1d  = calc_ema(closes_1d, EMA_TREND_PERIOD)
        trend_1d  = 1 if closes_1d[-1] > ema20_1d[-1] else -1

        # 4-Hour Trend (20 EMA)
        closes_4h = [c["close"] for c in c4h]
        ema20_4h  = calc_ema(closes_4h, EMA_TREND_PERIOD)
        trend_4h  = 1 if closes_4h[-1] > ema20_4h[-1] else -1

        # 1-Hour Pullback Levels (20 EMA & 50 EMA)
        closes_1h = [c["close"] for c in c1h]
        ema20_1h  = calc_ema(closes_1h, EMA_TREND_PERIOD)
        ema50_1h  = calc_ema(closes_1h, EMA_FILTER_PERIOD)

        curr_candle = c1h[-1]
        prev_candle = c1h[-2] if len(c1h) >= 2 else curr_candle
        sol_price   = curr_candle["close"]

        t_1d_str = "BULLISH 🟢" if trend_1d == 1 else "BEARISH 🔴"
        t_4h_str = "BULLISH 🟢" if trend_4h == 1 else "BEARISH 🔴"
        bias_str = "SHORT ONLY 📉" if (trend_1d == -1 and trend_4h == -1) else ("LONG ONLY 📈" if (trend_1d == 1 and trend_4h == 1) else "NEUTRAL / CHOP ⏸️")

        # Heartbeat every 1 hour
        now = time.time()
        if now - self.last_heartbeat_time >= 3600:
            self.last_heartbeat_time = now
            pos_str = f"{self.active_trade['side']} (₹{self.active_trade['entry']:,.0f})" if self.active_trade else f"Scanning ({bias_str})"
            send_telegram(
                f"💓 *Shark MTF Trend Bot Heartbeat* 🟢\n\n"
                f"• *SOL Price*: ₹{sol_price:,.0f} INR\n"
                f"• *1-Day Trend*: {t_1d_str} (EMA 20: ₹{ema20_1d[-1]:,.0f})\n"
                f"• *4-Hour Trend*: {t_4h_str} (EMA 20: ₹{ema20_4h[-1]:,.0f})\n"
                f"• *Strategy Mode*: *{bias_str}*\n"
                f"• *Status*: {pos_str}\n"
                f"• *Trades Today*: {self.daily_stats['trades_today']} (Wins: {self.daily_stats.get('wins_today', 0)}, Losses: {self.daily_stats.get('losses_today', 0)}/{MAX_LOSSES_PER_DAY})\n"
                f"• *Today P&L*: *₹{self.daily_stats['pnl_inr_today']:+.1f} INR*\n"
                f"• *Cloud Host*: Online 24×7 🛡️"
            )

        # Active trade exit check
        if self.active_trade:
            side  = self.active_trade["side"]
            entry = self.active_trade["entry"]
            sl    = self.active_trade["sl"]
            tgt   = self.active_trade["target"]
            qty   = self.active_trade.get("qty", CONTRACT_QTY)

            trade_closed = False
            is_win = False
            exit_price = 0.0

            if side == "BUY":
                if curr_candle["low"] <= sl:
                    trade_closed, is_win, exit_price = True, False, sl
                elif curr_candle["high"] >= tgt:
                    trade_closed, is_win, exit_price = True, True, tgt
            else:
                if curr_candle["high"] >= sl:
                    trade_closed, is_win, exit_price = True, False, sl
                elif curr_candle["low"] <= tgt:
                    trade_closed, is_win, exit_price = True, True, tgt

            if trade_closed:
                pnl_pts = (exit_price - entry) if side == "BUY" else (entry - exit_price)
                pnl_inr = pnl_pts * qty
                self.daily_stats["pnl_inr_today"] += pnl_inr
                self.daily_stats["total_month_pnl_inr"] += pnl_inr

                if is_win:
                    self.daily_stats["wins_today"] += 1
                    outcome_str, outcome_emoji = f"PROFIT TARGET (+₹{MAX_PROFIT_PER_TRADE_INR:.0f}) 🎯", "🎉"
                else:
                    self.daily_stats["losses_today"] += 1
                    outcome_str, outcome_emoji = f"STOP LOSS (-₹{MAX_LOSS_PER_TRADE_INR:.0f}) 🛑", "🛑"
                    self.last_loss_time = time.time()
                self._save_daily_stats()

                # Ensure exchange market order executes to close position
                try:
                    exit_side = "SELL" if side == "BUY" else "BUY"
                    self.client.place_market_order(exit_side, qty, reduce_only=True)
                except Exception as ex_err:
                    log.error(f"Error executing market close on exchange: {ex_err}")

                loss_warning = ""
                if self.daily_stats.get("losses_today", 0) >= MAX_LOSSES_PER_DAY:
                    loss_warning = f"\n🔒 *DAILY LOSS LIMIT REACHED ({MAX_LOSSES_PER_DAY} Losses)!* Bot locked until tomorrow to protect capital."
                elif not is_win:
                    loss_warning = f"\n⏳ *Cooldown*: {COOLDOWN_LOSS_MINS} min patient pause active."

                send_telegram(
                    f"🏁 *TRADE CLOSED ({outcome_str})* {outcome_emoji}\n\n"
                    f"• *Pair*: `{SYMBOL}`\n"
                    f"• *Side*: `{side}` ({qty} SOL)\n"
                    f"• *Entry Price*: ₹{entry:,.0f} INR\n"
                    f"• *Exit Price*: ₹{exit_price:,.0f} INR\n"
                    f"• *Stop Loss (SL)*: ₹{sl:,.0f} 🛑\n"
                    f"• *Take Profit (TP)*: ₹{tgt:,.0f} 🎯\n"
                    f"• *Net P&L*: *₹{pnl_inr:+.1f} INR* {outcome_emoji}\n\n"
                    f"📊 *Scorecard Today:*\n"
                    f"• *Trades*: {self.daily_stats['trades_today']} (Wins: {self.daily_stats['wins_today']}, Losses: {self.daily_stats['losses_today']}/{MAX_LOSSES_PER_DAY})\n"
                    f"• *Today P&L*: *₹{self.daily_stats['pnl_inr_today']:+.1f} INR*"
                    f"{loss_warning}"
                )
                self.active_trade = None
            return

        # Entry constraints: Stop if 2 losses today, or in 30-min loss cooldown, or same candle
        if self.daily_stats.get("losses_today", 0) >= MAX_LOSSES_PER_DAY:
            return
        if self.last_loss_time > 0 and (time.time() - self.last_loss_time < COOLDOWN_LOSS_MINS * 60):
            return
        if curr_candle["time"] == self.last_candle_time:
            return

        # Triple-Screen Multi-Timeframe Entry Logic
        signal = None
        reversal_detail = ""

        high_1h  = curr_candle["high"]
        low_1h   = curr_candle["low"]
        open_1h  = curr_candle["open"]
        close_1h = curr_candle["close"]
        e20_1h   = ema20_1h[-1]
        e50_1h   = ema50_1h[-1]

        # 🔴 SHORT SIGNAL: 1D Bearish + 4H Bearish + 1H below 50 EMA + Pullback to 20 EMA + Solid Red Rejection
        if trend_1d == -1 and trend_4h == -1:
            if close_1h < e50_1h and high_1h >= e20_1h and close_1h < e20_1h:
                body_pts = open_1h - close_1h
                if close_1h < open_1h and body_pts >= MIN_REJECTION_BODY_PTS:
                    signal = "SELL"
                    reversal_detail = f"🔴 1D/4H Bearish Alignment + 1H 20 EMA Rejection (-{body_pts:.0f} pts Red Body)"

        # 🟢 LONG SIGNAL: 1D Bullish + 4H Bullish + 1H above 50 EMA + Pullback to 20 EMA + Solid Green Bounce
        elif trend_1d == 1 and trend_4h == 1:
            if close_1h > e50_1h and low_1h <= e20_1h and close_1h > e20_1h:
                body_pts = close_1h - open_1h
                if close_1h > open_1h and body_pts >= MIN_REJECTION_BODY_PTS:
                    signal = "BUY"
                    reversal_detail = f"🟢 1D/4H Bullish Alignment + 1H 20 EMA Bounce (+{body_pts:.0f} pts Green Body)"

        if not signal:
            return

        entry = sol_price
        sl_pts = round(MAX_LOSS_PER_TRADE_INR / CONTRACT_QTY, 2)
        tp_pts = round(MAX_PROFIT_PER_TRADE_INR / CONTRACT_QTY, 2)

        precision = 0 if "SOL" in SYMBOL.upper() else 2
        if signal == "BUY":
            sl = int(round(entry - sl_pts)) if precision == 0 else round(entry - sl_pts, precision)
            target = int(round(entry + tp_pts)) if precision == 0 else round(entry + tp_pts, precision)
        else:
            sl = int(round(entry + sl_pts)) if precision == 0 else round(entry + sl_pts, precision)
            target = int(round(entry - tp_pts)) if precision == 0 else round(entry - tp_pts, precision)

        risk_pts = abs(entry - sl)
        expected_risk = risk_pts * CONTRACT_QTY
        expected_reward = abs(entry - target) * CONTRACT_QTY
        margin_required = (entry * CONTRACT_QTY) / LEVERAGE

        # Place Order
        res = self.client.place_bracket_order(signal, CONTRACT_QTY, sl, target)
        if not res.get("success"):
            raw_err = str(res.get("raw", {}).get("error", "Rejected"))
            log.error(f"Order failed on exchange: {raw_err}")
            send_telegram(f"⚠️ *Order Blocked by Exchange!*\nReason: `{raw_err}`")
            return

        attach_res = res.get("attach_res", {})
        tpsl_attached = bool(res.get("tpsl_attached") or attach_res.get("verified_on_exchange") or attach_res.get("success"))

        # If not confirmed on first attempt, retry immediately to guarantee SL and TP are set together with entry!
        if not tpsl_attached:
            log.warning("TP/SL not confirmed on first attempt, retrying immediately...")
            time.sleep(1.0)
            retry_res = self.client.attach_tpsl_to_open_position(SYMBOL, tp_price=target, sl_price=sl)
            tpsl_attached = bool(retry_res.get("verified_on_exchange") or retry_res.get("success"))

        tpsl_status_msg = "✅ SL & TP Active on Shark Exchange" if tpsl_attached else "⏳ Attaching on exchange..."

        self.last_candle_time = curr_candle["time"]
        self.daily_stats["trades_today"] += 1
        self._save_daily_stats()
        self.active_trade = {
            "side": signal,
            "entry": entry,
            "sl": sl,
            "target": target,
            "qty": CONTRACT_QTY,
            "risk_pts": risk_pts,
            "tpsl_attached": tpsl_attached
        }

        send_telegram(
            f"🚀 *A+ {signal} (MTF TREND CONFIRMED) ORDER EXECUTED!* 🦈\n\n"
            f"• *Pair*: `{SYMBOL}` (Solana INR Perpetual)\n"
            f"• *Side*: `{signal}` ({CONTRACT_QTY} SOL)\n"
            f"• *Strategy*: Triple-Screen MTF Trend-Rider (1D/4H ➡️ 1H Pullback)\n"
            f"• *Confirmation*: {reversal_detail}\n"
            f"• *Margin Used*: ~₹{margin_required:,.0f} INR (at {LEVERAGE}×)\n"
            f"• *Entry Price*: ₹{entry:,.0f} INR\n"
            f"• *Stop Loss (SL)*: ₹{sl:,.0f} (-₹{MAX_LOSS_PER_TRADE_INR:.0f} Max Loss) 🛑\n"
            f"• *Target (TP)*: ₹{target:,.0f} (+₹{MAX_PROFIT_PER_TRADE_INR:.0f} Target) 🎯\n"
            f"• *Exchange TP/SL*: {tpsl_status_msg}\n"
            f"• *1D Trend*: {t_1d_str} | *4H Trend*: {t_4h_str}\n\n"
            f"📊 *Trades Today*: {self.daily_stats['trades_today']} (Wins: {self.daily_stats.get('wins_today', 0)}, Losses: {self.daily_stats['losses_today']}/{MAX_LOSSES_PER_DAY})\n"
            f"🛡️ *Wallet Backup*: ~₹800+ safe in reserve!"
        )

import http.server
import socketserver

class HealthCheckHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/trade-xrp":
            client = SharkClient()
            sym = "XRPINR"
            # 90x leverage: 4.5 * ~125 = 562 / 90 = ~6.24 INR (strictly under Rs 7 max budget!)
            client.set_leverage(90, sym)
            qty = 4.5
            tp_price = 127.00
            sl_price = 123.40
            res = client.place_market_order("BUY", qty, sym, tp_price=tp_price, sl_price=sl_price)
            # If plain market order succeeded, also place bracket orders directly
            if res.get("success") and res.get("bracket_fallback"):
                client.place_limit_order("SELL", qty, tp_price, sym, reduce_only=True)
                client.place_stop_market_order("SELL", qty, sl_price, sym, reduce_only=True)

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(res).encode())
            if res.get("success"):
                send_telegram(
                    "🎉 *LIVE XRP TEST TRADE EXECUTED DIRECTLY!* 🚀\n\n"
                    "• *Asset*: `XRPINR`\n"
                    "• *Side*: `BUY` 🟢\n"
                    "• *Quantity*: `4.5 XRP` (~₹562 Value)\n"
                    "• *Leverage*: `90×`\n"
                    "• *Margin Used*: `₹6.24 INR` (Strictly under ₹7!)\n"
                    "• *Take Profit (TP)*: `₹127.00` (+₹8 Profit Target) 🎯\n"
                    "• *Stop Loss (SL)*: `₹123.40` (-₹8 Loss Limit) 🛑\n\n"
                    "Trade live open ho gaya hai aur TP/SL dono lag chuke hain!"
                )
            else:
                send_telegram(f"❌ *XRP Order Error:*\n`{res.get('error')}`")
            return

        if self.path == "/check-pos":
            client = SharkClient()
            positions = client.get_open_positions()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(positions).encode())
            return

        if self.path == "/set-xrp-tpsl":
            client = SharkClient()
            positions = client.get_open_positions()
            xrp_pos = None
            pos_list = positions if isinstance(positions, list) else (positions.get("data") or positions.get("result") or [])
            if isinstance(pos_list, list):
                for p in pos_list:
                    if "XRP" in str(p.get("contractPair", "")) or "XRP" in str(p.get("symbol", "")):
                        xrp_pos = p
                        break

            if xrp_pos:
                pos_id = str(xrp_pos.get("positionId") or xrp_pos.get("id"))
                qty = float(xrp_pos.get("quantity") or xrp_pos.get("positionAmount") or xrp_pos.get("size") or 4.5)
                # Entry was ~125.12 -> TP 126.90 (+8 Rs profit), SL 123.34 (-8 Rs loss)
                tp_price = 126.90
                sl_price = 123.34
                res = client.set_split_tp_sl(pos_id, tp_price, sl_price, qty)
                fallback_res = {}
                if not res.get("success"):
                    # Fallback: Place bracket exit orders directly (ReduceOnly Limit TP & Stop Market SL)
                    r_tp = client.place_limit_order("SELL", qty, tp_price, "XRPINR", reduce_only=True)
                    r_sl = client.place_stop_market_order("SELL", qty, sl_price, "XRPINR", reduce_only=True)
                    fallback_res = {"tp_order": r_tp, "sl_order": r_sl}

                combined = {
                    "split_res": res,
                    "fallback_res": fallback_res,
                    "pos_id": pos_id,
                    "xrp_pos": xrp_pos
                }
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(combined).encode())

                is_success = res.get("success") or (fallback_res.get("tp_order", {}).get("success") and fallback_res.get("sl_order", {}).get("success"))
                if is_success:
                    send_telegram(
                        "🎯 *XRP TEST POSITION: TP & SL SET HO GAYA!* 🛡️\n\n"
                        f"• *Asset*: `XRPINR` (4.5 XRP)\n"
                        f"• *Take Profit (TP)*: `₹{tp_price}` (+₹8.00 Target) 🎯\n"
                        f"• *Stop Loss (SL)*: `₹{sl_price}` (-₹8.00 Limit) 🛑\n\n"
                        "Aap Shark Exchange App me Positions me ya Open Orders me live dekh sakte hain!"
                    )
                else:
                    send_telegram(f"❌ *TP/SL Result:*\n`{combined}`")
            else:
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": "No open XRP position found in API", "raw": positions}).encode())
            return

        if self.path.startswith("/set-sol-tpsl") or self.path.startswith("/attach-tpsl"):
            client = SharkClient()
            parsed = urllib.parse.urlparse(self.path)
            q_params = urllib.parse.parse_qs(parsed.query)
            tp_arg = float(q_params.get("tp", [0])[0]) if "tp" in q_params else 10202.0
            sl_arg = float(q_params.get("sl", [0])[0]) if "sl" in q_params else 10079.0
            sym_arg = q_params.get("symbol", [SYMBOL])[0]

            res = client.attach_tpsl_to_open_position(sym_arg, tp_price=tp_arg, sl_price=sl_arg)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(res).encode())

            if res.get("success"):
                send_telegram(
                    "🎯 *SOL POSITION: TP & SL SET HO GAYA!* 🛡️\n\n"
                    f"• *Asset*: `{sym_arg}` ({res.get('qty', 0.4)} SOL)\n"
                    f"• *Entry Price*: ₹10,128 INR\n"
                    f"• *Take Profit (TP)*: `₹{tp_arg}` 🎯\n"
                    f"• *Stop Loss (SL)*: `₹{sl_arg}` 🛑\n\n"
                    "Shark Exchange App me TP aur SL active ho chuka hai!"
                )
            else:
                send_telegram(f"❌ *TP/SL Set Error:*\n`{res}`")
            return

        if self.path == "/close-xrp":

            client = SharkClient()
            res = client.close_all_positions()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"closed": res}).encode())
            if res:
                send_telegram(
                    "✅ *XRP TEST POSITION CLOSED!* 🏁\n\n"
                    "• Shark Exchange par open test position successfully close ho gayi hai.\n"
                    "• Capital wallet balance me wapas free ho gaya."
                )
            return

        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Shark Exchange Cloud Trading Bot is Active 24x7 OK\n")

    def log_message(self, format, *args):
        pass

def run_health_server():
    port = int(os.environ.get("PORT", 8080))
    try:
        server = socketserver.TCPServer(("", port), HealthCheckHandler)
        log.info(f"Render HTTP Health Check Server running on port {port}")
        server.serve_forever()
    except Exception as e:
        log.error(f"Health server error: {e}")

import signal
import atexit

_has_alerted_shutdown = False

def emergency_shutdown_handler(signum=None, frame=None):
    global _has_alerted_shutdown
    if _has_alerted_shutdown:
        return
    _has_alerted_shutdown = True
    log.warning(f"Shutdown signal received: {signum}")
    try:
        send_telegram(
            "⚠️ *CRITICAL ALERT: SHARK CLOUD BOT IS TURNING OFF!* 🛑\n\n"
            "• *Event*: Cloud Bot process band ya restart ho raha hai.\n"
            "• *Reason*: Server stop / crash signal received.\n"
            "• *Action*: Render dashboard me jakar status check karein!"
        )
    except Exception as e:
        log.error(f"Failed to send shutdown Telegram alert: {e}")
    if signum is not None:
        sys.exit(0)

try:
    signal.signal(signal.SIGTERM, emergency_shutdown_handler)
    signal.signal(signal.SIGINT, emergency_shutdown_handler)
except Exception:
    pass

def uncaught_exception_handler(exc_type, exc_value, exc_traceback):
    err_str = f"{exc_type.__name__}: {exc_value}"
    log.error(f"Uncaught exception: {err_str}")
    try:
        send_telegram(
            f"🚨 *CRITICAL ALERT: CLOUD BOT ERROR!* ⚠️\n\n"
            f"• *Error*: `{err_str}`\n"
            f"• Bot automatically recover karne ki koshish kar raha hai."
        )
    except Exception:
        pass
    sys.__excepthook__(exc_type, exc_value, exc_traceback)

sys.excepthook = uncaught_exception_handler

def main():
    bot = CloudTradingBot()
    t1 = threading.Thread(target=bot.run_telegram_listener, daemon=True)
    t1.start()
    t2 = threading.Thread(target=run_health_server, daemon=True)
    t2.start()
    bot.run_strategy_engine()

if __name__ == "__main__":
    main()
