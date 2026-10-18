"""
=============================================================
  SHARK EXCHANGE CLIENT MODULE (NATIVE LIVE INTEGRATION)
  Handles Market Data, Order Execution, Positions & Balances.
=============================================================
"""

import time
import json
import hmac
import hashlib
import logging
import socket
import urllib.parse
import requests

import config
from config import SHARK_API_KEY, SHARK_API_SECRET, SHARK_BASE_URL, SYMBOL

# Enforce IPv4 on all socket lookups (Prevents carrier IPv6 whitelisting errors)
_orig_getaddrinfo = socket.getaddrinfo
def _ipv4_getaddrinfo(*args, **kwargs):
    res = _orig_getaddrinfo(*args, **kwargs)
    return [r for r in res if r[0] == socket.AF_INET]
socket.getaddrinfo = _ipv4_getaddrinfo

log = logging.getLogger("SharkAPI")

class SharkClient:
    def __init__(self):
        self.api_key = SHARK_API_KEY
        self.api_secret = SHARK_API_SECRET
        self.base_url = SHARK_BASE_URL
        self.symbol = SYMBOL
        self.is_live = bool(self.api_key and self.api_secret and len(self.api_key) > 10)
        self.proxy_url = getattr(config, "PROXY_URL", "")
        self.session = requests.Session()
        if self.proxy_url:
            self.session.proxies = {"http": self.proxy_url, "https": self.proxy_url}

    def _sign_query(self, params: dict) -> str:
        qs = urllib.parse.urlencode(params)
        return hmac.new(
            self.api_secret.encode("utf-8"),
            qs.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()

    def _sign_body(self, payload: dict) -> str:
        body = json.dumps(payload, separators=(",", ":"))
        return hmac.new(
            self.api_secret.encode("utf-8"),
            body.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()

    # ─────────────────────────────────────────────────────────
    #  MARKET DATA (Native Shark Exchange Candles)
    # ─────────────────────────────────────────────────────────
    def get_candles(self, resolution: str = "5m", limit: int = 210) -> list:
        """
        Fetches live historical candles directly from Shark Exchange.
        Returns chronologically sorted candle list: [ {time, open, high, low, close}, ... ]
        """
        try:
            url = f"{self.base_url}/v1/market/klines"
            payload = {"pair": self.symbol, "interval": resolution, "limit": limit}
            r = self.session.post(url, json=payload, timeout=8)
            if r.status_code == 201:
                raw = r.json()
                candles = [
                    {
                        "time": int(c["startTime"]) // 1000,
                        "open": float(c["open"]),
                        "high": float(c["high"]),
                        "low": float(c["low"]),
                        "close": float(c["close"]),
                    }
                    for c in raw
                ]
                candles.sort(key=lambda x: x["time"])
                return candles
        except Exception as e:
            log.warning(f"Shark candles error: {e}")

        # Fallback to Delta INR conversion if Shark market endpoint is ever degraded
        try:
            end = int(time.time())
            res_secs = 900 if resolution == "15m" else 300
            start = end - (limit * res_secs)
            url_delta = "https://api.india.delta.exchange/v2/history/candles"
            r_d = self.session.get(url_delta, params={"resolution": resolution, "symbol": "BTCUSD", "start": start, "end": end}, timeout=8)
            if r_d.status_code == 200:
                raw_d = r_d.json().get("result", [])
                candles = [
                    {
                        "time": c["time"],
                        "open": float(c["open"]) * 88.0,
                        "high": float(c["high"]) * 88.0,
                        "low": float(c["low"]) * 88.0,
                        "close": float(c["close"]) * 88.0,
                    }
                    for c in raw_d
                ]
                candles.sort(key=lambda x: x["time"])
                return candles
        except Exception as e2:
            log.error(f"Fallback candle fetch error: {e2}")

        return []

    # ─────────────────────────────────────────────────────────
    #  ACCOUNT & WALLET
    # ─────────────────────────────────────────────────────────
    def get_wallet_balance(self) -> float:
        """
        Returns available INR balance in futures wallet.
        """
        if not self.is_live:
            return 1000.0

        endpoint = "/v1/wallet/futures-wallet/details"
        ts = str(int(time.time() * 1000))
        params = {"timestamp": ts}
        sig = self._sign_query(params)
        headers = {"api-key": self.api_key, "signature": sig, "accept": "*/*"}
        url = f"{self.base_url}{endpoint}?{urllib.parse.urlencode(params)}"

        try:
            r = self.session.get(url, headers=headers, timeout=10)
            if r.status_code == 200:
                data = r.json()
                return float(data.get("walletBalance", 0.0))
        except Exception as e:
            log.error(f"Error fetching wallet balance: {e}")
        return 0.0

    def get_open_positions(self) -> list:
        """
        Returns list of open futures positions.
        """
        if not self.is_live:
            return []

        endpoint = "/v1/positions/OPEN"
        ts = str(int(time.time() * 1000))
        params = {"sortOrder": "desc", "pageSize": "10", "timestamp": ts}
        sig = self._sign_query(params)
        headers = {"api-key": self.api_key, "signature": sig, "accept": "*/*"}
        url = f"{self.base_url}{endpoint}?{urllib.parse.urlencode(params)}"

        try:
            r = self.session.get(url, headers=headers, timeout=10)
            if r.status_code == 200:
                return r.json()
        except Exception as e:
            log.error(f"Error fetching open positions: {e}")
        return []

    def set_leverage(self, leverage: int = 25, symbol: str = None) -> bool:
        """
        Updates leverage for a contract on Shark Exchange.
        """
        if not self.is_live:
            return True

        target_sym = symbol or self.symbol
        endpoint = "/v1/exchange/update/leverage"
        ts = str(int(time.time() * 1000))
        payload = {
            "leverage": leverage,
            "contractName": target_sym,
            "timestamp": ts,
        }
        body = json.dumps(payload, separators=(",", ":"))
        sig = self._sign_body(payload)
        headers = {"api-key": self.api_key, "signature": sig, "Content-Type": "application/json", "accept": "*/*"}

        try:
            r = self.session.post(f"{self.base_url}{endpoint}", data=body, headers=headers, timeout=10)
            return r.status_code in [200, 201]
        except Exception as e:
            log.error(f"Error updating leverage: {e}")
            return False

    # ─────────────────────────────────────────────────────────
    #  ORDER EXECUTION
    # ─────────────────────────────────────────────────────────
    def place_market_order(self, side: str, qty: float, symbol: str = None) -> dict:
        """
        Places market order on Shark Exchange.
        side: 'BUY' or 'SELL'
        qty: e.g. 4.5
        """
        if not self.is_live:
            return {"success": True, "order_id": f"sim_{int(time.time())}"}

        target_sym = symbol or self.symbol
        endpoint = "/v1/order/place-order"
        ts = str(int(time.time() * 1000))
        payload = {
            "timestamp": ts,
            "placeType": "ORDER_FORM",
            "quantity": qty,
            "side": side.upper(),
            "symbol": target_sym,
            "type": "MARKET",
            "reduceOnly": False,
            "marginAsset": "INR",
            "deviceType": "WEB",
            "userCategory": "EXTERNAL",
        }
        body = json.dumps(payload, separators=(",", ":"))
        sig = self._sign_body(payload)
        headers = {"api-key": self.api_key, "signature": sig, "Content-Type": "application/json", "accept": "*/*"}

        try:
            r = self.session.post(f"{self.base_url}{endpoint}", data=body, headers=headers, timeout=15)
            if r.status_code in [200, 201]:
                return {"success": True, "data": r.json()}
            else:
                log.error(f"Order placement failed: {r.status_code} - {r.text}")
                return {"success": False, "error": r.text}
        except Exception as e:
            log.error(f"Order exception: {e}")
            return {"success": False, "error": str(e)}

    def close_all_positions(self) -> bool:
        """
        Emergency close all open positions on Shark Exchange.
        """
        if not self.is_live:
            return True

        endpoint = "/v1/positions/close-all-positions"
        ts = str(int(time.time() * 1000))
        payload = {"timestamp": ts}
        body = json.dumps(payload, separators=(",", ":"))
        sig = self._sign_body(payload)
        headers = {"api-key": self.api_key, "signature": sig, "Content-Type": "application/json", "accept": "*/*"}

        try:
            r = self.session.delete(f"{self.base_url}{endpoint}", data=body, headers=headers, timeout=12)
            return r.status_code == 200
        except Exception as e:
            log.error(f"Error closing all positions: {e}")
            return False

    def place_bracket_order(self, side: str, qty: float, stop_loss: float, take_profit: float) -> dict:
        """
        Places the entry order and tracks the bracket.
        """
        res = self.place_market_order(side, qty)
        return {
            "success": res.get("success", False),
            "side": side,
            "qty": qty,
            "sl": stop_loss,
            "tp": take_profit,
            "raw": res,
        }
