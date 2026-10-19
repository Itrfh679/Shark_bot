import os

# Shark Exchange Credentials (read from environment or default)
SHARK_API_KEY      = os.getenv("SHARK_API_KEY", "64b44d06a6266fbb4900db4c7c0e4f88")
SHARK_API_SECRET   = os.getenv("SHARK_API_SECRET", "93a37f2b76811da276bc7826d1104131")
SHARK_BASE_URL     = os.getenv("SHARK_BASE_URL", "https://api.sharkexchange.in")
SYMBOL             = os.getenv("SYMBOL", "SOLINR")
RENDER_DEPLOY_HOOK = os.getenv("RENDER_DEPLOY_HOOK", "https://api.render.com/deploy/srv-db98nq6q1p3s739k2eug?key=RXG7VjbtkiE")


# Telegram Bot
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8959389105:AAGza59y2PmqfDrybiZnYJjcAvyIhKLU3w0")
TELEGRAM_CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID", "5706939133")

# Strategy & Dynamic Risk Management (Sniper Sweet Spot | ~₹240 Margin)
LEVERAGE           = 25
RISK_PER_TRADE_INR = 65.0       # Max ₹65 loss per trade (Capped for ₹1,000 capital safety)
MIN_CONTRACT_QTY   = 0.30       # Minimum quantity boundary
MAX_CONTRACT_QTY   = 0.65       # Max quantity (~₹260 margin at 25x with ₹10k SOL)
CONTRACT_QTY       = 0.60       # Target trade size (~₹240 margin)
MAX_TRADES_PER_DAY = 2          # Strict daily limit (Max 2 trades/day)
RISK_REWARD_RATIO  = 2.2        # Solid 1:2.2 RR (+₹145 to +₹150 profit target per trade!)
MIN_SL_POINTS      = 12.0       # 12 pts min SL (~0.12% - allows tight risk setups)
MAX_SL_POINTS      = 110.0      # 110 pts max SL (~1.10% safe room against wicks)
SL_BUFFER_POINTS   = 10.0       # 10pt buffer against Solana stop-hunt wicks
COOLDOWN_LOSS_MINS = 60         # 1-hour patience cooldown after any loss

# Timeframes & Indicators
# NOTE: User Strategy Preset:
# Current Active: Sniper Ultra-Strict Mode (Ultra-Safe institutional setup)
HTF_RESOLUTION     = "15m"
EMA_HTF            = 200        # 15m EMA 200 Bada Bhai
EMA_HTF_MIN_SLOPE  = 1.2        # Ultra-strict momentum slope (100% blocks choppy/flat days)
EMA_HTF_DANGER_PCT = 0.20       # Minimum distance from EMA 200 to confirm trend breakout

LTF_RESOLUTION     = "5m"
EMA_FAST           = 20
EMA_SLOW           = 50
RSI_PERIOD         = 14
RSI_BUY_MIN        = 50.0
RSI_BUY_MAX        = 66.0
RSI_SELL_MIN       = 34.0
RSI_SELL_MAX       = 50.0
MIN_WICK_RATIO     = 0.45       # Institutional 45%+ Rejection Wick (Rejects all weak fakeouts)

# Pushkar Raj Thakur Course Enhancements
VOLUME_MA_PERIOD     = 20       # 20-period Volume Moving Average
VOLUME_THRESHOLD_PCT = 0.75     # 0.75x (75% volume confirmation)
ENABLE_VOLUME_FILTER = True     # Turned ON to filter low-volume traps
ENABLE_BREAK_EVEN    = True     # Auto shift SL to entry at 1:1 Risk-Reward (100% risk-free trade!)
