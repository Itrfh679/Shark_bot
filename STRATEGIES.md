# 🦈 Shark Exchange Trading Strategies (Permanent Record)

### 1. Strategy 4: "QUAD-SCREEN MTF TREND-RIDER" (Current Live Bot)
* **Full Name:** Quad-Screen Multi-Timeframe Trend-Rider (1D Macro ➡️ 4H Swing ➡️ 1H Pullback ➡️ 15M Momentum Shield)
* **Exchange:** Shark Exchange (`https://api.sharkexchange.in`)
* **Pair:** `SOLINR` (Solana INR Perpetual)
* **Timeframes & Roles:**
  * **Screen 1: 1-Day (`1d`) EMA 20** — Determines Macro Trend direction (Bullish or Bearish).
  * **Screen 2: 4-Hour (`4h`) EMA 20** — Swing Confirmation (Must agree with 1D, else No Trade).
  * **Screen 3: 1-Hour (`1h`) EMA 20 & 50** — Pullback Value Zone + Solid Rejection Candle (≥ 20 pts).
  * **Screen 4: 15-Minute (`15m`) Anti-Pump & Anti-Dump Shield** — Execution Timing & Momentum Protection.
* **Execution Rules:**
  * **🔴 SHORT (SELL) Conditions:**
    1. 1-Day < 20 EMA (Bearish)
    2. 4-Hour < 20 EMA (Bearish)
    3. 1-Hour: Price pulled back to 20 EMA, rejected with a solid Red candle (Body ≥ 20 pts) below 50 EMA.
    4. **15-Minute Anti-Pump Shield**: 15m candle MUST be Red (`close < open`) AND price must be $\le$ 15m 20 EMA. If 15m is Green or pumping above 20 EMA ➡️ **SHORT IS 100% BLOCKED**.
  * **🟢 LONG (BUY) Conditions:**
    1. 1-Day > 20 EMA (Bullish)
    2. 4-Hour > 20 EMA (Bullish)
    3. 1-Hour: Price pulled back to 20 EMA, bounced with a solid Green candle (Body ≥ 20 pts) above 50 EMA.
    4. **15-Minute Anti-Dump Shield**: 15m candle MUST be Green (`close > open`) AND price must be $\ge$ 15m 20 EMA. If 15m is Red or dumping below 20 EMA ➡️ **LONG IS 100% BLOCKED**.
  * If 1D & 4H disagree: **NO TRADE** (Chop protection).
* **Risk & Capital Management:**
  * Margin per Trade: **₹150 INR** (25× leverage, 0.38 SOL)
  * Stop Loss: Strict **₹40 INR** (-105.26 pts)
  * Take Profit: Strict **+₹90 INR** (+236.84 pts, 1:2.25 Risk-to-Reward Ratio)
  * Daily Circuit Breaker: **Max 2 Losses** (₹80 loss limit) per day ➡️ auto-locks until 00:00 UTC.
  * Daily Profit Limit: **UNLIMITED** (win as many as the trend gives).
  * Cooldown: 30-min patience pause after any loss.

---

### 2. Strategy 3: "MTF-20" (Triple-Screen Prototype)
* **Logic:** 1D + 4H + 1H without 15m momentum shield.
* **Flaw Identified:** Entered short at 2:32 AM during an active 15m recovery pump, leading to Stop Loss hit at 5:03 AM.
* **Status:** Upgraded to Strategy 4 (Quad-Screen).

---

### 3. Strategy 1: "ELASTIC" (Archive)
* **Full Name:** 15m Elastic Mean Reversion + Reversal Candle Confirmation
* **Logic:** Price stretch > 1.2% from EMA 20 with RSI < 25 or > 75.

---

### 4. Strategy 2: "RANGE-48" (Archive)
* **Full Name:** 48-Hour Dynamic Box Support & Resistance Bounce
* **Logic:** 48h Support/Resistance bounce in outer 12% zone.
