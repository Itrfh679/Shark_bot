import re
import logging

log = logging.getLogger("SignalParser")

# Mapping of coin names to CoinDCX Futures Pairs
COINDCX_PAIR_MAP = {
    "BTC": "B-BTC_USDT",
    "ETH": "B-ETH_USDT",
    "SOL": "B-SOL_USDT",
    "XRP": "B-XRP_USDT",
    "DOGE": "B-DOGE_USDT",
    "BNB": "B-BNB_USDT",
    "ADA": "B-ADA_USDT",
    "AVAX": "B-AVAX_USDT",
    "NEAR": "B-NEAR_USDT",
    "SUI": "B-SUI_USDT",
    "PEPE": "B-1000PEPE_USDT",
    "SHIB": "B-1000SHIB_USDT",
}

def clean_num(val_str: str) -> float:
    """Removes commas and symbols and converts to float"""
    if not val_str:
        return 0.0
    clean = re.sub(r"[^\d.]", "", val_str)
    try:
        return float(clean)
    except Exception:
        return 0.0

def parse_signal(text: str) -> dict:
    """
    Parses Expert Picks text or notification string.
    Returns structured dictionary with:
    {
        'coin': 'ETH',
        'pair': 'B-ETH_USDT',
        'side': 'sell',
        'leverage': 15,
        'entry_min': 2391.75,
        'entry_max': 2414.9,
        'entry_avg': 2403.32,
        'take_profit': 2365.61,
        'stop_loss': 2432.16,
        'raw': text
    }
    """
    if not text:
        return None

    text_upper = text.upper()

    # 1. Detect Coin
    detected_coin = None
    for coin in COINDCX_PAIR_MAP.keys():
        # Match standalone coin symbol or word boundary
        if re.search(r"\b" + coin + r"\b", text_upper):
            detected_coin = coin
            break

    if not detected_coin:
        log.warning(f"Could not identify coin from text: {text}")
        return None

    # 2. Detect Side (Long / Short / Buy / Sell)
    side = "buy"
    if "SHORT" in text_upper or "SELL" in text_upper:
        side = "sell"
    elif "LONG" in text_upper or "BUY" in text_upper:
        side = "buy"

    # 3. Detect Leverage (e.g. 15x, 10x, 20x)
    lev_match = re.search(r"(\d+)\s*[xX]", text)
    leverage = int(lev_match.group(1)) if lev_match else 15

    # 4. Detect Entry Range (e.g., "2,414.9 - 2,391.75" or "80,694.9 - 81,510")
    entry_min, entry_max, entry_avg = 0.0, 0.0, 0.0
    entry_range_match = re.search(r"(?:ENTRY\s*(?:RANGE)?|BUY\s*AT|AT)?\s*[:\-]?\s*([0-9,.]+)\s*(?:-|TO)\s*([0-9,.]+)", text_upper)
    if entry_range_match:
        n1 = clean_num(entry_range_match.group(1))
        n2 = clean_num(entry_range_match.group(2))
        entry_min = min(n1, n2)
        entry_max = max(n1, n2)
        entry_avg = (entry_min + entry_max) / 2.0
    else:
        # Single entry price match
        single_entry = re.search(r"ENTRY\s*(?:PRICE)?\s*[:\-]?\s*([0-9,.]+)", text_upper)
        if single_entry:
            entry_avg = clean_num(single_entry.group(1))
            entry_min = entry_avg
            entry_max = entry_avg

    # 5. Detect Take Profit (Target)
    tp_match = re.search(r"(?:TAKE\s*PROFIT|TARGET|TP)\s*[:\-]?\s*([0-9,.]+)", text_upper)
    take_profit = clean_num(tp_match.group(1)) if tp_match else 0.0

    # 6. Detect Stop Loss
    sl_match = re.search(r"(?:STOP\s*LOSS|SL)\s*[:\-]?\s*([0-9,.]+)", text_upper)
    stop_loss = clean_num(sl_match.group(1)) if sl_match else 0.0

    return {
        "coin": detected_coin,
        "pair": COINDCX_PAIR_MAP[detected_coin],
        "side": side,
        "leverage": leverage,
        "entry_min": entry_min,
        "entry_max": entry_max,
        "entry_avg": entry_avg,
        "take_profit": take_profit,
        "stop_loss": stop_loss,
        "raw": text
    }
