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
import requests

from config import (
    SHARK_API_KEY, SHARK_API_SECRET, SHARK_BASE_URL, SYMBOL,
    TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID,
    LEVERAGE, CONTRACT_QTY, RISK_PER_TRADE_INR, MIN_CONTRACT_QTY, MAX_CONTRACT_QTY,
    MAX_TRADES_PER_DAY, RISK_REWARD_RATIO,
    MIN_SL_POINTS, MAX_SL_POINTS, SL_BUFFER_POINTS, COOLDOWN_LOSS_MINS,
    HTF_RESOLUTION, EMA_HTF, EMA_HTF_MIN_SLOPE, EMA_HTF_DANGER_PCT,
    LTF_RESOLUTION, EMA_FAST, EMA_SLOW, RSI_PERIOD,
    RSI_BUY_MIN, RSI_BUY_MAX, RSI_SELL_MIN, RSI_SELL_MAX, MIN_WICK_RATIO
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
        self.daily_stats = {
            "date": time.strftime("%Y-%m-%d"),
            "trades_today": 0,
            "wins_today": 0,
            "losses_today": 0,
            "pnl_inr_today": 0.0,
            "total_month_pnl_inr": 0.0
        }

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
                "🟢 *Cloud Bot Started / Resumed!*\n\n"
                f"• Asset: `{SYMBOL}`\n"
                f"• Leverage: `{LEVERAGE}×`\n"
                f"• Strategy: 15m EMA 200 + 5m Pullback + RSI\n"
                f"• Status: Active 24x7 scanning in Cloud."
            )

        elif cmd_lower in ["/stop", "/pause", "stop", "pause"]:
            self.is_running = False
            send_telegram("⏸️ *Cloud Bot Paused!*\nScanning stopped. Send `/start` to resume.")

        elif cmd_lower in ["/status", "status"]:
            c5m = self.client.get_candles(LTF_RESOLUTION, 5)
            curr_price = c5m[-1]["close"] if c5m else 0.0
            pos_text = f"{self.active_trade['side']} (Entry: ₹{self.active_trade['entry']:,.0f})" if self.active_trade else "No Open Trade (Waiting Setup)"
            state = "🟢 RUNNING" if self.is_running else "⏸️ PAUSED"
            send_telegram(
                f"📊 *Cloud Bot Status Report* ☁️\n\n"
                f"• *Status*: {state}\n"
                f"• *Cloud Server IP*: `{self.public_ip}`\n"
                f"• *Current SOL Price*: ₹{curr_price:,.0f} INR\n"
                f"• *Active Position*: {pos_text}\n"
                f"• *Trades Today*: {self.daily_stats['trades_today']}/{MAX_TRADES_PER_DAY}\n"
                f"• *Today P&L*: *₹{self.daily_stats['pnl_inr_today']:+.1f} INR*\n"
                f"• *Uptime*: 24×7 Cloud Active (No phone needed)"
            )

        elif cmd_lower in ["/balance", "balance"]:
            bal = self.client.get_wallet_balance()
            send_telegram(
                f"💳 *Shark Exchange Wallet Balance*\n\n"
                f"• *Futures Wallet Balance*: *₹{bal:,.2f} INR*\n"
                f"• *Capital Allocated*: ₹1,000 INR\n"
                f"• *Margin per Trade*: ~₹160 INR (at {LEVERAGE}×)\n"
                f"• *Free Safe Buffer*: ~₹840 INR"
            )

        elif cmd_lower in ["/close", "close"]:
            success = self.client.close_all_positions()
            self.active_trade = None
            msg = "✅ *All Positions Closed Immediately!*" if success else "⚠️ *Close Request Sent!*"
            send_telegram(msg)

        elif cmd_lower in ["/help", "help"]:
            send_telegram(
                "🤖 *Cloud Trading Bot Commands:*\n\n"
                "• `/status` - Live SOL price, trend & trade state\n"
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
            f"🦈 *SHARK EXCHANGE 24x7 CLOUD BOT ONLINE!* ☁️\n\n"
            f"• *Cloud Server IP*: `{self.public_ip}`\n"
            f"• *Pair*: `{SYMBOL}` (Solana INR Perpetual)\n"
            f"• *Leverage*: `{LEVERAGE}×`\n"
            f"• *Risk*: Strictly ₹15 - ₹30 per trade 🛑\n"
            f"• *Target (1:{RISK_REWARD_RATIO})*: Strictly ₹50 - ₹70 per trade 🎯\n"
            f"• *Daily Limit*: Max {MAX_TRADES_PER_DAY} Trades / Day 🔒\n"
            f"• *Phone Status*: You can close your phone/Termux now! 📱💤\n\n"
            f"👉 Send `/status` or `/balance` anytime to inspect!"
        )

        while True:
            try:
                self._reset_daily_stats_if_needed()
                if self.is_running:
                    self._scan_market_cycle()
            except Exception as e:
                log.error(f"Strategy error: {e}")
            time.sleep(30)

    def _scan_market_cycle(self):
        # Fetch candles
        c15m = self.client.get_candles(HTF_RESOLUTION, 220)
        c5m  = self.client.get_candles(LTF_RESOLUTION, 70)

        if len(c15m) < 205 or len(c5m) < 55:
            return

        closes_15m = [c["close"] for c in c15m]
        ema200_15m = calc_ema(closes_15m, EMA_HTF)
        e200_curr   = ema200_15m[-1]
        e200_prev   = ema200_15m[-2]
        slope_15m   = e200_curr - e200_prev

        closes_5m = [c["close"] for c in c5m]
        ema20_5m  = calc_ema(closes_5m, EMA_FAST)
        ema50_5m  = calc_ema(closes_5m, EMA_SLOW)
        rsi       = calc_rsi(closes_5m, RSI_PERIOD)

        curr_5m   = c5m[-1]
        prev_5m   = c5m[-2]
        sol_price = curr_5m["close"]

        htf_dist = abs(sol_price - e200_curr) / sol_price * 100.0
        htf_bullish = (sol_price > e200_curr) and (slope_15m >= EMA_HTF_MIN_SLOPE) and (htf_dist >= EMA_HTF_DANGER_PCT)
        htf_bearish = (sol_price < e200_curr) and (slope_15m <= -EMA_HTF_MIN_SLOPE) and (htf_dist >= EMA_HTF_DANGER_PCT)

        # Heartbeat every 1 hour
        now = time.time()
        if now - self.last_heartbeat_time >= 3600:
            self.last_heartbeat_time = now
            pos_str = f"{self.active_trade['side']} (₹{self.active_trade['entry']:,.0f})" if self.active_trade else "No Open Trade (Waiting A+)"
            send_telegram(
                f"💓 *Shark Cloud Bot Heartbeat (Active)* 🟢\n\n"
                f"• *SOL Price*: ₹{sol_price:,.0f} INR\n"
                f"• *Status*: {pos_str}\n"
                f"• *Trades Today*: {self.daily_stats['trades_today']}/{MAX_TRADES_PER_DAY}\n"
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
            if side == "BUY":
                if curr_5m["low"] <= sl:
                    trade_closed, is_win, exit_price = True, False, sl
                elif curr_5m["high"] >= tgt:
                    trade_closed, is_win, exit_price = True, True, tgt
            else:
                if curr_5m["high"] >= sl:
                    trade_closed, is_win, exit_price = True, False, sl
                elif curr_5m["low"] <= tgt:
                    trade_closed, is_win, exit_price = True, True, tgt

            if trade_closed:
                pnl_pts = (exit_price - entry) if side == "BUY" else (entry - exit_price)
                pnl_inr = pnl_pts * qty
                self.daily_stats["pnl_inr_today"] += pnl_inr
                self.daily_stats["total_month_pnl_inr"] += pnl_inr

                if is_win:
                    self.daily_stats["wins_today"] += 1
                    outcome_str, outcome_emoji = "PROFIT 🎯", "🎉"
                else:
                    self.daily_stats["losses_today"] += 1
                    outcome_str, outcome_emoji = "STOP LOSS 🛑", "🛡️"
                    self.last_loss_time = time.time()

                send_telegram(
                    f"🏁 *TRADE CLOSED ({outcome_str})* {outcome_emoji}\n\n"
                    f"• *Side*: {side} ({qty} SOL)\n"
                    f"• *Entry Price*: ₹{entry:,.0f} INR\n"
                    f"• *Exit Price*: ₹{exit_price:,.0f} INR\n"
                    f"• *Net P&L*: *₹{pnl_inr:+.1f} INR* {outcome_emoji}\n\n"
                    f"📊 *Scorecard Today:*\n"
                    f"• Trades: {self.daily_stats['trades_today']}/{MAX_TRADES_PER_DAY}\n"
                    f"• Today P&L: *₹{self.daily_stats['pnl_inr_today']:+.1f} INR*"
                )
                self.active_trade = None
            return

        # Entry constraints
        if self.daily_stats["trades_today"] >= MAX_TRADES_PER_DAY:
            return
        if self.last_loss_time > 0 and (time.time() - self.last_loss_time < COOLDOWN_LOSS_MINS * 60):
            return
        if curr_5m["time"] == self.last_candle_time:
            return

        # Rejection & pullback check
        c_range = max(curr_5m["high"] - curr_5m["low"], 0.001)
        lower_wick = min(curr_5m["open"], curr_5m["close"]) - curr_5m["low"]
        upper_wick = curr_5m["high"] - max(curr_5m["open"], curr_5m["close"])
        bull_rej = (lower_wick / c_range) >= MIN_WICK_RATIO
        bear_rej = (upper_wick / c_range) >= MIN_WICK_RATIO

        e20, e50 = ema20_5m[-1], ema50_5m[-1]
        signal = None
        if htf_bullish and (e20 > e50) and (prev_5m["low"] <= e20) and (curr_5m["close"] >= e20) and bull_rej and (RSI_BUY_MIN <= rsi <= RSI_BUY_MAX):
            signal = "BUY"
        elif htf_bearish and (e20 < e50) and (prev_5m["high"] >= e20) and (curr_5m["close"] <= e20) and bear_rej and (RSI_SELL_MIN <= rsi <= RSI_SELL_MAX):
            signal = "SELL"

        if not signal:
            return

        lookback = 5
        swing_low  = min(c5m[j]["low"] for j in range(len(c5m) - lookback, len(c5m)))
        swing_high = max(c5m[j]["high"] for j in range(len(c5m) - lookback, len(c5m)))

        entry = sol_price
        if signal == "BUY":
            sl = swing_low - SL_BUFFER_POINTS
            risk = entry - sl
            if not (MIN_SL_POINTS <= risk <= MAX_SL_POINTS):
                return
            target = entry + (risk * RISK_REWARD_RATIO)
        else:
            sl = swing_high + SL_BUFFER_POINTS
            risk = sl - entry
            if not (MIN_SL_POINTS <= risk <= MAX_SL_POINTS):
                return
            target = entry - (risk * RISK_REWARD_RATIO)

        # Dynamic Position Sizing Formula: Quantity = Risk (₹25) / Stop Loss Distance (Points)
        raw_qty = RISK_PER_TRADE_INR / max(risk, 1.0)
        trade_qty = round(max(MIN_CONTRACT_QTY, min(raw_qty, MAX_CONTRACT_QTY)), 2)
        expected_risk = risk * trade_qty
        expected_reward = (risk * RISK_REWARD_RATIO) * trade_qty
        margin_required = (entry * trade_qty) / LEVERAGE

        # Place Order
        res = self.client.place_bracket_order(signal, trade_qty, sl, target)
        if not res.get("success"):
            raw_err = str(res.get("raw", {}).get("error", "Rejected"))
            log.error(f"Order failed on exchange: {raw_err}")
            send_telegram(f"⚠️ *Order Blocked by Exchange!*\nReason: `{raw_err}`")
            return

        self.last_candle_time = curr_5m["time"]
        self.daily_stats["trades_today"] += 1
        self.active_trade = {
            "side": signal,
            "entry": entry,
            "sl": sl,
            "target": target,
            "qty": trade_qty
        }

        send_telegram(
            f"🚀 *A+ {signal} ORDER EXECUTED ON SHARK!* 🦈\n\n"
            f"• *Pair*: `{SYMBOL}` (Solana INR Perpetual)\n"
            f"• *Side*: `{signal}` 🟢\n"
            f"• *Dynamic Size*: `{trade_qty} SOL` (~₹{margin_required:,.0f} Margin at {LEVERAGE}×)\n"
            f"• *Entry Price*: ₹{entry:,.0f} INR\n"
            f"• *Stop Loss*: ₹{sl:,.0f} (-₹{expected_risk:.1f} Risk [~₹25]) 🛑\n"
            f"• *Target (1:{RISK_REWARD_RATIO})*: ₹{target:,.0f} (+₹{expected_reward:.1f} Profit) 🎯\n\n"
            f"📈 Trades Today: {self.daily_stats['trades_today']}/{MAX_TRADES_PER_DAY}\n"
            f"🛡️ Dynamic Risk Management Active 🔒"
        )

import http.server
import socketserver

class HealthCheckHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/trade-xrp":
            client = SharkClient()
            sym = "XRPINR"
            # Set 60x leverage
            client.set_leverage(60, sym)
            # Place 4.5 XRP order (~Rs 560 value, margin is Rs 9.36 at 60x)
            res = client.place_market_order("BUY", 4.5, sym)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(res).encode())
            if res.get("success"):
                send_telegram(
                    "🎉 *LIVE XRP TEST TRADE EXECUTED!* 🚀\n\n"
                    "• *Asset*: `XRPINR`\n"
                    "• *Side*: `BUY` 🟢\n"
                    "• *Quantity*: `4.5 XRP` (~₹560 Value)\n"
                    "• *Leverage*: `60×`\n"
                    "• *Margin Used*: `₹9.36 INR` (Under ₹10!)\n\n"
                    "Aap apne Shark Exchange app me Positions tab me ye live trade dekh sakte hain!"
                )
            else:
                send_telegram(f"❌ *XRP Order Error:*\n`{res.get('error')}`")
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
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(res).encode())
                if res.get("success"):
                    send_telegram(
                        "🎯 *XRP TEST POSITION: TP & SL SET HO GAYA!* 🛡️\n\n"
                        f"• *Position ID*: `{pos_id}`\n"
                        f"• *Quantity*: `{qty} XRP`\n"
                        f"• *Take Profit (TP)*: `₹{tp_price}` (+₹8.00 Profit Target) 🎯\n"
                        f"• *Stop Loss (SL)*: `₹{sl_price}` (-₹8.00 Loss Limit) 🛑\n\n"
                        "Aap Shark Exchange App me Positions me dekh sakte hain, TP aur SL lag chuka hai!"
                    )
                else:
                    send_telegram(f"❌ *TP/SL Set Error:*\n`{res.get('data') or res.get('error')}`")
            else:
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": "No open XRP position found in API", "raw": positions}).encode())
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
