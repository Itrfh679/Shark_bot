import os

# Shark Exchange Credentials (read from environment or default)
SHARK_API_KEY      = os.getenv("SHARK_API_KEY", "64b44d06a6266fbb4900db4c7c0e4f88")
SHARK_API_SECRET   = os.getenv("SHARK_API_SECRET", "93a37f2b76811da276bc7826d1104131")
SHARK_BASE_URL     = os.getenv("SHARK_BASE_URL", "https://api.sharkexchange.in")
SYMBOL             = os.getenv("SYMBOL", "SOLINR")
RENDER_DEPLOY_HOOK = os.getenv("RENDER_DEPLOY_HOOK", "https://api.render.com/deploy/srv-db98nq6q1p3s739k2eug?key=RXG7VjbtkiE")


# Telegram Bot
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "7319679215:AAFO1F_mCJ03bh62BT3QobTdeUWflX1D5HY")
TELEGRAM_CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID", "5706939133")

# Strategy & Risk Management: Triple-Screen MTF Trend-Rider (₹150 Margin, ₹40 Risk / ₹90 Profit)
LEVERAGE                   = 25
CONTRACT_QTY               = 0.38       # Exactly ₹150 Margin at 25x (~₹3,700 trade value)
MARGIN_REQUIRED            = 150.0      # ₹150 INR margin per trade
MAX_LOSS_PER_TRADE_INR     = 40.0       # Exact ₹40 Max Loss per trade
MAX_PROFIT_PER_TRADE_INR   = 90.0       # Sweet Spot: +₹90 Max Profit per trade (1:2.25 RR)
MAX_LOSSES_PER_DAY         = 2          # Daily Circuit Breaker: 2 Losses Max (Stops at ₹80 loss)
MAX_TRADES_PER_DAY         = 20         # Unlimited Wins Mode: restricted only by 2 daily losses
COOLDOWN_LOSS_MINS         = 30         # 30-min patience pause after any loss

# Multi-Timeframe Trend & Pullback Rejection Parameters
RESOLUTION_1D              = "1d"       # Screen 1: Daily Macro Trend
RESOLUTION_4H              = "4h"       # Screen 2: 4-Hour Trend Confirmation
RESOLUTION_1H              = "1h"       # Screen 3: 1-Hour Pullback Entry
EMA_TREND_PERIOD           = 20         # 20 EMA for 1D, 4H, and 1H
EMA_FILTER_PERIOD          = 50         # 50 EMA for 1H alignment
MIN_REJECTION_BODY_PTS     = 20.0       # Minimum 20 pts solid candle body for pullback rejection

