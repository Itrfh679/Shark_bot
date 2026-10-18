import os

# Shark Exchange Credentials (read from environment or default)
SHARK_API_KEY      = os.getenv("SHARK_API_KEY", "64b44d06a6266fbb4900db4c7c0e4f88")
SHARK_API_SECRET   = os.getenv("SHARK_API_SECRET", "93a37f2b76811da276bc7826d1104131")
SHARK_BASE_URL     = os.getenv("SHARK_BASE_URL", "https://api.sharkexchange.in")
SYMBOL             = os.getenv("SYMBOL", "SOLINR")

# Telegram Bot
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8959389105:AAGza59y2PmqfDrybiZnYJjcAvyIhKLU3w0")
TELEGRAM_CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID", "5706939133")

# Strategy & Dynamic Risk Management (Realistic 1:2 RR | ₹150 Margin)
LEVERAGE           = 25
RISK_PER_TRADE_INR = 40.0       # Realistic ₹38-₹40 loss per trade (Safely inside ₹50 budget)
MIN_CONTRACT_QTY   = 0.20       # Minimum quantity boundary
MAX_CONTRACT_QTY   = 0.40       # Max quantity (~₹150 margin at 25x with ₹10k SOL)
CONTRACT_QTY       = 0.38       # Target trade size (~₹150 margin)
MAX_TRADES_PER_DAY = 2          # Strict daily limit (Max 2 trades/day)
RISK_REWARD_RATIO  = 2.0        # Practical 1:2 RR (2.0% move = +₹76-₹80 profit!)
MIN_SL_POINTS      = 50.0       # 50 pts min SL (~0.50%)
MAX_SL_POINTS      = 110.0      # 110 pts max SL (~1.10% safe room against wicks)
SL_BUFFER_POINTS   = 12.0       # 12pt buffer against Solana stop-hunt wicks
COOLDOWN_LOSS_MINS = 60         # 1-hour patience cooldown after any loss

# Timeframes & Indicators
HTF_RESOLUTION     = "15m"
EMA_HTF            = 200
EMA_HTF_MIN_SLOPE  = 0.6        # Balanced momentum slope (Rejects flat markets while catching smooth trends)
EMA_HTF_DANGER_PCT = 0.20       # Minimum distance from EMA 200 to confirm trend breakout

LTF_RESOLUTION     = "5m"
EMA_FAST           = 20
EMA_SLOW           = 50
RSI_PERIOD         = 14
RSI_BUY_MIN        = 50.0
RSI_BUY_MAX        = 66.0
RSI_SELL_MIN       = 34.0
RSI_SELL_MAX       = 50.0
MIN_WICK_RATIO     = 0.30       # Realistic 30%+ Rejection Wick (Captures solid institutional bounces)

# Pushkar Raj Thakur Course Enhancements
VOLUME_MA_PERIOD     = 20       # 20-period Volume Moving Average
VOLUME_THRESHOLD_PCT = 1.00     # 1.0x (100%) - Trigger candle volume >= 20-period SMA
ENABLE_BREAK_EVEN    = True     # Auto shift SL to entry at 1:1 Risk-Reward
