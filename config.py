import os

# Shark Exchange Credentials (read from environment or default)
SHARK_API_KEY      = os.getenv("SHARK_API_KEY", "64b44d06a6266fbb4900db4c7c0e4f88")
SHARK_API_SECRET   = os.getenv("SHARK_API_SECRET", "93a37f2b76811da276bc7826d1104131")
SHARK_BASE_URL     = os.getenv("SHARK_BASE_URL", "https://api.sharkexchange.in")
SYMBOL             = os.getenv("SYMBOL", "SOLINR")

# Telegram Bot
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8959389105:AAGza59y2PmqfDrybiZnYJjcAvyIhKLU3w0")
TELEGRAM_CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID", "5706939133")

# Strategy Parameters
LEVERAGE           = 25
CONTRACT_QTY       = 0.40       # 0.40 SOL (~₹160 margin from ₹1,000 capital)
MAX_TRADES_PER_DAY = 2          # Strict daily limit
RISK_REWARD_RATIO  = 2.3        # 1:2.3 RR
MIN_SL_POINTS      = 40.0       # ₹16.0 min risk
MAX_SL_POINTS      = 75.0       # ₹30.0 max risk
SL_BUFFER_POINTS   = 5.0
COOLDOWN_LOSS_MINS = 45

# Timeframes & Indicators
HTF_RESOLUTION     = "15m"
EMA_HTF            = 200
EMA_HTF_MIN_SLOPE  = 0.5
EMA_HTF_DANGER_PCT = 0.12

LTF_RESOLUTION     = "5m"
EMA_FAST           = 20
EMA_SLOW           = 50
RSI_PERIOD         = 14
RSI_BUY_MIN        = 50.0
RSI_BUY_MAX        = 68.0
RSI_SELL_MIN       = 32.0
RSI_SELL_MAX       = 50.0
MIN_WICK_RATIO     = 0.35
