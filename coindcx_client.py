import hmac
import hashlib
import json
import time
import logging
import requests

from config import (
    COINDCX_API_KEY, COINDCX_API_SECRET, COINDCX_BASE_URL,
    MAX_MARGIN_PER_TRADE_INR, DEFAULT_LEVERAGE
)

log = logging.getLogger("CoinDCXClient")

class CoinDCXClient:
    def __init__(self, api_key: str = None, api_secret: str = None):
        self.api_key = api_key or COINDCX_API_KEY
        self.api_secret = api_secret or COINDCX_API_SECRET
        self.base_url = COINDCX_BASE_URL
        self.session = requests.Session()
        self.usd_inr_rate = 88.5  # Estimated USD to INR exchange rate

    def _sign_payload(self, payload: dict) -> tuple:
        """
        Signs the payload with HMAC-SHA256 using the API Secret.
        Returns (json_body, headers)
        """
        json_body = json.dumps(payload, separators=(',', ':'))
        secret_bytes = bytes(self.api_secret, encoding="utf-8")
        signature = hmac.new(secret_bytes, json_body.encode("utf-8"), hashlib.sha256).hexdigest()

        headers = {
            "Content-Type": "application/json",
            "X-AUTH-APIKEY": self.api_key,
            "X-AUTH-SIGNATURE": signature
        }
        return json_body, headers

    def get_balances(self) -> list:
        """
        Fetches all asset balances from CoinDCX.
        """
        endpoint = "/exchange/v1/users/balances"
        payload = {"timestamp": int(round(time.time() * 1000))}
        json_body, headers = self._sign_payload(payload)

        try:
            r = self.session.post(f"{self.base_url}{endpoint}", data=json_body, headers=headers, timeout=10)
            if r.status_code == 200:
                return r.json()
            log.error(f"Error fetching balances: {r.status_code} - {r.text}")
        except Exception as e:
            log.error(f"Balances request error: {e}")
        return []

    def get_futures_positions(self) -> list:
        """
        Fetches active and recent futures positions.
        """
        endpoint = "/exchange/v1/derivatives/futures/positions"
        payload = {
            "timestamp": int(round(time.time() * 1000)),
            "page": "1",
            "size": "20",
            "margin_currency_short_name": ["USDT", "INR"]
        }
        json_body, headers = self._sign_payload(payload)

        try:
            r = self.session.post(f"{self.base_url}{endpoint}", data=json_body, headers=headers, timeout=10)
            if r.status_code == 200:
                return r.json()
            log.error(f"Error fetching futures positions: {r.status_code} - {r.text}")
        except Exception as e:
            log.error(f"Futures positions request error: {e}")
        return []

    def get_active_positions(self) -> list:
        """
        Returns only positions where active_pos != 0.
        """
        all_positions = self.get_futures_positions()
        return [p for p in all_positions if abs(float(p.get("active_pos", 0.0))) > 0.0]

    def get_ticker(self, pair: str = None) -> dict:
        """
        Fetches public live prices for futures.
        """
        endpoint = "/exchange/ticker"
        try:
            r = self.session.get(f"{self.base_url}{endpoint}", timeout=8)
            if r.status_code == 200:
                data = r.json()
                if pair:
                    for item in data:
                        if item.get("market") == pair:
                            return item
                return data
        except Exception as e:
            log.error(f"Ticker error: {e}")
        return {}

    def calculate_quantity(self, pair: str, entry_price: float, margin_inr: float = MAX_MARGIN_PER_TRADE_INR, leverage: int = DEFAULT_LEVERAGE) -> float:
        """
        Calculates exact contract quantity so margin strictly equals margin_inr (e.g. ₹150).
        Total position value (in USD) = (margin_inr / usd_inr_rate) * leverage
        Quantity = total_value_usd / entry_price
        """
        if entry_price <= 0:
            return 0.0

        margin_usd = margin_inr / self.usd_inr_rate
        total_notional_usd = margin_usd * leverage
        raw_qty = total_notional_usd / entry_price

        # Standard precision formatting per coin
        pair_upper = pair.upper()
        if "BTC" in pair_upper:
            return round(raw_qty, 4)  # e.g. 0.0003 BTC
        elif "ETH" in pair_upper:
            return round(raw_qty, 3)  # e.g. 0.011 ETH
        elif "SOL" in pair_upper:
            return round(raw_qty, 2)  # e.g. 0.24 SOL
        elif "XRP" in pair_upper:
            return round(raw_qty, 1)  # e.g. 30.5 XRP
        return round(raw_qty, 2)

    def place_futures_order(self, pair: str, side: str, order_type: str = "market_order",
                            price: float = None, quantity: float = None,
                            leverage: int = DEFAULT_LEVERAGE) -> dict:
        """
        Places a futures order on CoinDCX.
        pair: e.g. 'B-BTC_USDT', 'B-SOL_USDT'
        side: 'buy' or 'sell'
        order_type: 'market_order' or 'limit_order'
        """
        endpoint = "/exchange/v1/derivatives/futures/orders/create"

        order_data = {
            "side": side.lower(),
            "pair": pair,
            "order_type": order_type,
            "total_quantity": float(quantity),
            "leverage": int(leverage),
            "notification": "no_notification",
            "hidden": False,
            "post_only": False
        }

        if order_type == "limit_order" and price is not None:
            order_data["price"] = float(price)
            order_data["time_in_force"] = "good_till_cancel"

        payload = {
            "timestamp": int(round(time.time() * 1000)),
            "order": order_data
        }

        json_body, headers = self._sign_payload(payload)

        try:
            r = self.session.post(f"{self.base_url}{endpoint}", data=json_body, headers=headers, timeout=12)
            log.info(f"Order placement response ({r.status_code}): {r.text}")
            if r.status_code in [200, 201]:
                return {"success": True, "data": r.json()}
            return {"success": False, "error": r.text, "status_code": r.status_code}
        except Exception as e:
            log.error(f"Order placement error: {e}")
            return {"success": False, "error": str(e)}

    def cancel_all_open_orders(self, pair: str = None) -> bool:
        """
        Cancels open futures orders.
        """
        endpoint = "/exchange/v1/derivatives/futures/orders/cancel_all"
        payload = {"timestamp": int(round(time.time() * 1000))}
        if pair:
            payload["pair"] = pair
        json_body, headers = self._sign_payload(payload)

        try:
            r = self.session.post(f"{self.base_url}{endpoint}", data=json_body, headers=headers, timeout=10)
            return r.status_code in [200, 201]
        except Exception as e:
            log.error(f"Cancel all error: {e}")
            return False
