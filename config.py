import os

# Shark Exchange Credentials (read from environment or default)
SHARK_API_KEY      = os.getenv("SHARK_API_KEY", "64b44d06a6266fbb4900db4c7c0e4f88")
SHARK_API_SECRET   = os.getenv("SHARK_API_SECRET", "93a37f2b76811da276bc7826d1104131")
SHARK_BASE_URL     = os.getenv("SHARK_BASE_URL", "https://api.sharkexchange.in")
SYMBOL             = os.getenv("SYMBOL", "SOLINR")

# Telegram Bot
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8959389105:AAGza59y2PmqfDrybiZnYJjcAvyIhKLU3w0")
TELEGRAM_CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID", "5706939133")

# Strategy & Dynamic Risk Management (Strict 2.5% Capital Rule)
LEVERAGE           = 25
RISK_PER_TRADE_INR = 25.0       # Strictly ₹25 fixed loss per trade (2.5% of ₹1,000)
MIN_CONTRACT_QTY   = 0.20       # Minimum quantity boundary
MAX_CONTRACT_QTY   = 0.50       # Maximum quantity (~₹200 margin at 25x from ₹1,000 capital)
CONTRACT_QTY       = 0.35       # Default fallback
MAX_TRADES_PER_DAY = 2          # Strict daily limit (Max 2 trades/day)
RISK_REWARD_RATIO  = 2.6        # 1:2.6 RR (Guarantees +₹65 gross profit to easily beat fees)
MIN_SL_POINTS      = 45.0       # 45 pts min SL
MAX_SL_POINTS      = 95.0       # 95 pts max SL
SL_BUFFER_POINTS   = 12.0       # Strong 12pt buffer against Solana stop-hunt wicks
COOLDOWN_LOSS_MINS = 60         # 1-hour patience cooldown after any loss

# Timeframes & Indicators
HTF_RESOLUTION     = "15m"
EMA_HTF            = 200
EMA_HTF_MIN_SLOPE  = 1.2        # Rejects flat/choppy 15m markets (Only trades clear momentum)
EMA_HTF_DANGER_PCT = 0.20       # Minimum distance from EMA 200 to confirm trend breakout

LTF_RESOLUTION     = "5m"
EMA_FAST           = 20
EMA_SLOW           = 50
RSI_PERIOD         = 14
RSI_BUY_MIN        = 50.0
RSI_BUY_MAX        = 66.0
RSI_SELL_MIN       = 34.0
RSI_SELL_MAX       = 50.0
MIN_WICK_RATIO     = 0.45       # Institutional 45%+ Rejection Wick (Rejects weak fakeouts)
