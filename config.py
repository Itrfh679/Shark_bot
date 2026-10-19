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

# Strategy & Risk Management: 15m Elastic Mean Reversion (₹150 Margin, ₹40 Risk / ₹80 Profit)
LEVERAGE                   = 25
CONTRACT_QTY               = 0.38       # Exactly ₹150 Margin at 25x (~₹3,800 trade value)
MARGIN_REQUIRED            = 150.0      # ₹150 INR margin per trade
MAX_LOSS_PER_TRADE_INR     = 40.0       # Exact ₹40 Max Loss per trade
MAX_PROFIT_PER_TRADE_INR   = 80.0       # Exact +₹80 Max Profit per trade (1:2.0 RR)
MAX_LOSSES_PER_DAY         = 2          # Daily Circuit Breaker: 2 Losses Max (Stops at ₹80 loss)
MAX_TRADES_PER_DAY         = 5          # Winning Mode: up to 5 trades if winning
COOLDOWN_LOSS_MINS         = 30         # 30-min patience pause after any loss

# 15-Minute Elastic Mean Reversion Rules
RESOLUTION                 = "15m"      # Clean 15-Minute timeframe (zero 5m noise)
EMA_PERIOD                 = 20         # 15m EMA 20 (Average equilibrium price)
RSI_PERIOD                 = 14         # 15m RSI 14
RSI_OVERSOLD               = 25.0       # Extreme panic dump (Buy trigger)
RSI_OVERBOUGHT             = 75.0       # Extreme greed peak (Sell trigger)
EMA_STRETCH_PCT            = 1.2        # Minimum 1.2% stretch from EMA 20

