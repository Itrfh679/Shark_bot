"""
=============================================================
  1-YEAR COMPREHENSIVE BACKTESTER FOR SOLANA STRATEGY
  Evaluates 1 Full Year (365 Days) on 15m HTF + 5m LTF
=============================================================
"""

import time
import datetime
import requests
import os
import json

CACHE_DIR = "/data/user/0/com.termux/files/home/.gemini/antigravity-cli/scratch/shark_bot/cloud_bot/backtest_cache"
os.makedirs(CACHE_DIR, exist_ok=True)

USD_INR_RATE = 88.0

def fetch_candles(symbol: str, interval: str, days: int = 365):
    cache_file = os.path.join(CACHE_DIR, f"{symbol}_{interval}_{days}d.json")
    if os.path.exists(cache_file):
        print(f"Loading cached {interval} data from {cache_file}...")
        with open(cache_file, "r") as f:
            return json.load(f)

    print(f"Downloading {days} days of {interval} candles for {symbol}...")
    url = "https://api.binance.com/api/v3/klines"
    now_ms = int(time.time() * 1000)
    start_ms = now_ms - (days * 86400 * 1000)
    candles = []
    curr_start = start_ms

    while curr_start < now_ms:
        try:
            r = requests.get(
                url,
                params={"symbol": symbol, "interval": interval, "startTime": curr_start, "limit": 1000},
                timeout=12
            )
            if r.status_code != 200:
                print(f"Error {r.status_code}, retrying...")
                time.sleep(1)
                continue
            data = r.json()
            if not data or not isinstance(data, list):
                break
            for c in data:
                candles.append({
                    "time": int(c[0]) // 1000,
                    "open": float(c[1]) * USD_INR_RATE,
                    "high": float(c[2]) * USD_INR_RATE,
                    "low": float(c[3]) * USD_INR_RATE,
                    "close": float(c[4]) * USD_INR_RATE,
                    "volume": float(c[5])
                })
            curr_start = data[-1][6] + 1
            time.sleep(0.04) # respectful rate limit
            if len(candles) % 10000 == 0:
                print(f"  Downloaded {len(candles)} candles so far...")
        except Exception as e:
            print(f"Fetch exception: {e}, waiting 2s...")
            time.sleep(2)

    # Sort and remove duplicates
    candles.sort(key=lambda x: x["time"])
    dedup = []
    seen = set()
    for c in candles:
        if c["time"] not in seen:
            seen.add(c["time"])
            dedup.append(c)

    print(f"Total unique {interval} candles downloaded: {len(dedup)}")
    with open(cache_file, "w") as f:
        json.dump(dedup, f)
    return dedup

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

def run_backtest():
    c15m = fetch_candles("SOLUSDT", "15m", days=365)
    c5m = fetch_candles("SOLUSDT", "5m", days=365)

    print("\nCalculating Technical Indicators across 1-year data...")
    closes_15m = [c["close"] for c in c15m]
    ema200_15m = calc_ema(closes_15m, 200)

    closes_5m = [c["close"] for c in c5m]
    ema20_5m = calc_ema(closes_5m, 20)
    ema50_5m = calc_ema(closes_5m, 50)

    print("Running 1-year bar-by-bar Strategy Simulation...")
    daily_trades = {}
    in_trade = False
    active = {}
    last_loss_time = 0

    monthly_stats = {}
    wins = 0
    losses = 0
    be_exits = 0
    total_pnl = 0.0
    peak_equity = 1000.0
    curr_equity = 1000.0
    max_drawdown_inr = 0.0
    all_trade_records = []

    # Map 15m index lookups
    t15_times = [c["time"] for c in c15m]
    ptr_15m = 0
    total_15m = len(c15m)

    for i in range(60, len(c5m)):
        curr_5m = c5m[i]
        prev_5m = c5m[i - 1]
        t = curr_5m["time"]

        # Sync 15m index pointer
        while ptr_15m + 1 < total_15m and t15_times[ptr_15m + 1] <= t:
            ptr_15m += 1

        dt = datetime.datetime.fromtimestamp(t, datetime.timezone.utc) + datetime.timedelta(hours=5, minutes=30)
        day_str = dt.strftime("%Y-%m-%d")
        month_str = dt.strftime("%Y-%m")

        if month_str not in monthly_stats:
            monthly_stats[month_str] = {"trades": 0, "wins": 0, "losses": 0, "be": 0, "pnl": 0.0}
        if day_str not in daily_trades:
            daily_trades[day_str] = 0

        # Handle active trade exit
        if in_trade:
            side = active["side"]
            entry = active["entry"]
            sl = active["sl"]
            tgt = active["target"]
            risk = active["risk"]

            # Auto Break-Even check (shift SL to entry when 1:1 profit reached)
            if not active["be_set"]:
                if side == "BUY" and curr_5m["high"] >= (entry + risk):
                    active["be_set"] = True
                    active["sl"] = entry
                    sl = entry
                elif side == "SELL" and curr_5m["low"] <= (entry - risk):
                    active["be_set"] = True
                    active["sl"] = entry
                    sl = entry

            closed = False
            win = False
            exit_price = 0.0

            if side == "BUY":
                if curr_5m["low"] <= sl:
                    closed, win, exit_price = True, False, sl
                elif curr_5m["high"] >= tgt:
                    closed, win, exit_price = True, True, tgt
            else:
                if curr_5m["high"] >= sl:
                    closed, win, exit_price = True, False, sl
                elif curr_5m["low"] <= tgt:
                    closed, win, exit_price = True, True, tgt

            if closed:
                in_trade = False
                monthly_stats[month_str]["trades"] += 1
                if win:
                    wins += 1
                    monthly_stats[month_str]["wins"] += 1
                    monthly_stats[month_str]["pnl"] += 80.0
                    curr_equity += 80.0
                    outcome = "WIN"
                elif active["be_set"] and abs(exit_price - entry) <= 2.0:
                    be_exits += 1
                    monthly_stats[month_str]["be"] += 1
                    outcome = "BREAK_EVEN"
                else:
                    losses += 1
                    monthly_stats[month_str]["losses"] += 1
                    monthly_stats[month_str]["pnl"] -= 40.0
                    curr_equity -= 40.0
                    last_loss_time = t
                    outcome = "LOSS"

                peak_equity = max(peak_equity, curr_equity)
                drawdown = peak_equity - curr_equity
                max_drawdown_inr = max(max_drawdown_inr, drawdown)

                all_trade_records.append({
                    "date": dt.strftime("%Y-%m-%d %H:%M"),
                    "side": side,
                    "entry": entry,
                    "exit": exit_price,
                    "outcome": outcome,
                    "equity": curr_equity
                })
                continue

        # Discipline & Constraints
        if daily_trades[day_str] >= 2:
            continue
        if last_loss_time > 0 and (t - last_loss_time < 3600): # 1-hour cooldown
            continue
        if ptr_15m < 200:
            continue

        # 15m HTF Trend Filter
        e200_curr = ema200_15m[ptr_15m]
        e200_prev = ema200_15m[ptr_15m - 1]
        slope_15m = e200_curr - e200_prev
        sol_price = curr_5m["close"]
        htf_dist = abs(sol_price - e200_curr) / sol_price * 100.0

        bull_htf = (sol_price > e200_curr) and (slope_15m >= 0.6) and (htf_dist >= 0.20)
        bear_htf = (sol_price < e200_curr) and (slope_15m <= -0.6) and (htf_dist >= 0.20)

        if not (bull_htf or bear_htf):
            continue

        # 5m LTF EMAs
        e20 = ema20_5m[i]
        e50 = ema50_5m[i]
        if bull_htf and not (e20 > e50):
            continue
        if bear_htf and not (e20 < e50):
            continue

        # Pullback check (min low <= e20 and close >= e20 for BUY)
        pullback_bull = (min(curr_5m["low"], prev_5m["low"]) <= e20) and (curr_5m["close"] >= e20)
        pullback_bear = (max(curr_5m["high"], prev_5m["high"]) >= e20) and (curr_5m["close"] <= e20)

        if bull_htf and not pullback_bull:
            continue
        if bear_htf and not pullback_bear:
            continue

        # 30% Rejection Wick Check
        cr = max(curr_5m["high"] - curr_5m["low"], 0.001)
        lower_wick = min(curr_5m["open"], curr_5m["close"]) - curr_5m["low"]
        upper_wick = curr_5m["high"] - max(curr_5m["open"], curr_5m["close"])
        rej_bull = (lower_wick / cr) >= 0.30
        rej_bear = (upper_wick / cr) >= 0.30

        if bull_htf and not rej_bull:
            continue
        if bear_htf and not rej_bear:
            continue

        # RSI Momentum Window (50-66 for BUY, 34-50 for SELL)
        rsi = calc_rsi(closes_5m[max(0, i - 60):i + 1], 14)
        if bull_htf and not (50.0 <= rsi <= 66.0):
            continue
        if bear_htf and not (34.0 <= rsi <= 50.0):
            continue

        # Dynamic Stop Loss
        lookback = 5
        swing_low = min(c5m[j]["low"] for j in range(i - lookback, i))
        swing_high = max(c5m[j]["high"] for j in range(i - lookback, i))

        if bull_htf:
            sl = swing_low - 10.0
            risk = sol_price - sl
        else:
            sl = swing_high + 10.0
            risk = sl - sol_price

        # New lightened SL range: 12 to 110 points
        if not (12.0 <= risk <= 110.0):
            continue

        target = (sol_price + (risk * 2.0)) if bull_htf else (sol_price - (risk * 2.0))
        daily_trades[day_str] += 1
        in_trade = True
        active = {
            "side": "BUY" if bull_htf else "SELL",
            "entry": sol_price,
            "sl": sl,
            "target": target,
            "risk": risk,
            "be_set": False
        }

    total_trades = wins + losses + be_exits
    total_pnl = (wins * 80.0) - (losses * 40.0)
    win_rate_total = (wins / total_trades * 100.0) if total_trades > 0 else 0.0
    effective_win_rate = (wins / (wins + losses) * 100.0) if (wins + losses) > 0 else 0.0

    print("\n" + "=" * 60)
    print("      🦈 SHARK SOLANA STRATEGY 1-YEAR BACKTEST REPORT 🦈")
    print("=" * 60)
    print(f"• Backtest Period       : 365 Days (1 Full Year)")
    print(f"• Starting Capital      : ₹1,000 INR")
    print(f"• Final Capital         : ₹{curr_equity:,.1f} INR")
    print(f"• Net Profit            : ₹{total_pnl:+,.1f} INR ({((curr_equity-1000)/1000)*100:+.1f}%)")
    print(f"• Max Drawdown          : ₹{max_drawdown_inr:.1f} INR ({(max_drawdown_inr/1000)*100:.1f}%)")
    print(f"• Total Trades Taken    : {total_trades}")
    print(f"• Target Wins (1:2 RR)  : {wins} (+₹80 each)")
    print(f"• Stop Losses           : {losses} (-₹40 each)")
    print(f"• Auto Break-Even Exits : {be_exits} (₹0 Zero Loss)")
    print(f"• Effective Win Rate    : {effective_win_rate:.1f}% (Wins vs Losses)")
    print(f"• Overall Win Rate      : {win_rate_total:.1f}% (Including Break-Even)")
    print(f"• Trades Per Week       : {total_trades / 52.0:.1f} trades/week")

    print("\n--- 📅 MONTH-BY-MONTH BREAKDOWN ---")
    print(f"{'Month':<10} | {'Trades':<7} | {'Wins':<5} | {'Loss':<5} | {'BE':<5} | {'Net P&L (INR)':<15}")
    print("-" * 55)
    for m, st in sorted(monthly_stats.items()):
        print(f"{m:<10} | {st['trades']:<7} | {st['wins']:<5} | {st['losses']:<5} | {st['be']:<5} | ₹{st['pnl']:+,.1f}")

    # Output json summary
    summary_path = "/data/user/0/com.termux/files/home/.gemini/antigravity-cli/scratch/shark_bot/cloud_bot/backtest_summary.json"
    with open(summary_path, "w") as f:
        json.dump({
            "start_capital": 1000.0,
            "final_capital": curr_equity,
            "net_pnl": total_pnl,
            "total_trades": total_trades,
            "wins": wins,
            "losses": losses,
            "be_exits": be_exits,
            "effective_win_rate": effective_win_rate,
            "max_drawdown": max_drawdown_inr,
            "monthly": monthly_stats
        }, f, indent=2)

if __name__ == "__main__":
    run_backtest()
