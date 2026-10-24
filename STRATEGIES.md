# 🦈 Shark Exchange Trading Strategies (Permanent Record)

### 1. Strategy 3: "MTF-20" (Current Live Bot - Trend-Rider)
* **Full Name:** Triple-Screen Multi-Timeframe Trend-Rider (1D Macro ➡️ 4H Confirmation ➡️ 1H 20 EMA Pullback)
* **Exchange:** Shark Exchange (`https://api.sharkexchange.in`)
* **Timeframes:**
  * Screen 1: 1-Day (`1d`) EMA 20 (Macro Trend Direction)
  * Screen 2: 4-Hour (`4h`) EMA 20 (Swing Trend Confirmation)
  * Screen 3: 1-Hour (`1h`) EMA 20 Pullback + 50 EMA Filter + Solid Rejection Candle (≥ 20 pts)
* **Logic:**
  * **SHORT ONLY** if 1D < EMA 20 and 4H < EMA 20 (Longs strictly blocked).
    * Entry on 1H: Close < EMA 50, High touches/crosses EMA 20, Close back below EMA 20 with Solid Red Candle (Body ≥ 20 pts).
  * **LONG ONLY** if 1D > EMA 20 and 4H > EMA 20 (Shorts strictly blocked).
    * Entry on 1H: Close > EMA 50, Low touches/crosses EMA 20, Close back above EMA 20 with Solid Green Candle (Body ≥ 20 pts).
  * If 1D & 4H conflict: **NO TRADE** (Preserves capital in chop).
* **Risk & Position:**
  * Margin: ₹150 INR (25× leverage, 0.38 SOL)
  * Stop Loss: Strict ₹40 INR (-105.26 pts)
  * Take Profit: Strict +₹90 INR (+236.84 pts, 1:2.25 RR "Sweet Spot")
  * Circuit Breaker: Max 2 losses (₹80) per day -> auto-halt until 00:00 UTC.
  * Profit Limit: **UNLIMITED** (win as many as the trend gives).
* **Backtest Result (1 Year / 365 Days SOL):**
  * Net Profit: **+₹2,960 INR** (+296% on ₹1,000 base capital)
  * 12 out of 13 months profitable or breakeven.

---

### 2. Strategy 1: "ELASTIC" (Archive)
* **Full Name:** 15m Elastic Mean Reversion + Reversal Candle Confirmation
* **Exchange:** Shark Exchange (`https://api.sharkexchange.in`)
* **Timeframe:** 15-Minute (`15m`)
* **Logic:** Price stretch > 1.2% from EMA 20 with RSI < 25 or > 75 + reversal candle.
* **Risk/Reward:** ₹40 SL / +₹80 TP (1:2.0 RR).

---

### 3. Strategy 2: "RANGE-48" (Archive)
* **Full Name:** 48-Hour Dynamic Box Support & Resistance Bounce
* **Exchange:** Shark Exchange (`https://api.sharkexchange.in`)
* **Timeframe:** 15-Minute (`15m`)
* **Logic:** 48h Support/Resistance bounce in outer 12% zone.
* **Risk/Reward:** ₹40 SL / +₹80 TP (1:2.0 RR).

---

### 4. Account Standard Rules
* Capital: ₹1,000 INR
* Max Open Trades: 1 at a time
* Daily Circuit Breaker: Max 2 losses (₹80) per day -> Halt until next day
* Profit Target: +₹90 per winning trade (Unlimited daily profits)
