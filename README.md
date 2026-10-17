# 🦈 Shark Exchange 24x7 Cloud Trading Bot

Automated trading bot for **Solana (`SOLINR`)** on **Shark Exchange** with Telegram controls.

### 📊 Strategy
- **HTF Trend**: 15m EMA 200
- **LTF Pullback**: 5m EMA 20/50 + Candle Rejection + RSI Filter
- **Risk Management**: Strictly ₹15 - ₹30 SL (40-75 pts), Target 1:2.3 RR (₹50 - ₹70 TP)
- **Daily Limit**: Max 2 trades/day

### 📱 Telegram Commands
- `/status` - Live SOL price, strategy trend & active position
- `/balance` - Shark Exchange wallet balance
- `/start` - Start / resume 24x7 cloud trading
- `/stop` - Pause cloud trading
- `/close` - Emergency close active position
