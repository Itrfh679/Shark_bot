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
                        "volume": float(c.get("volume", 0.0) or c.get("size", 0.0) or 0.0),
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
                        "volume": float(c.get("volume", 0.0) or 0.0),
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
    def place_market_order(self, side: str, qty: float, symbol: str = None, tp_price: float = None, sl_price: float = None) -> dict:
        """
        Places market order on Shark Exchange, optionally with TP and SL.
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
        if tp_price is not None:
            payload["takeProfitPrice"] = float(tp_price)
        if sl_price is not None:
            payload["stopLossPrice"] = float(sl_price)

        body = json.dumps(payload, separators=(",", ":"))
        sig = self._sign_body(payload)
        headers = {"api-key": self.api_key, "signature": sig, "Content-Type": "application/json", "accept": "*/*"}

        try:
            r = self.session.post(f"{self.base_url}{endpoint}", data=body, headers=headers, timeout=15)
            if r.status_code in [200, 201]:
                return {"success": True, "data": r.json()}
            
            # If rejected because of takeProfitPrice/stopLossPrice, retry clean market order
            if tp_price is not None or sl_price is not None:
                log.warning(f"Retrying plain market order without bracket params: {r.text}")
                payload.pop("takeProfitPrice", None)
                payload.pop("stopLossPrice", None)
                payload["timestamp"] = str(int(time.time() * 1000))
                body2 = json.dumps(payload, separators=(",", ":"))
                sig2 = self._sign_body(payload)
                headers2 = {"api-key": self.api_key, "signature": sig2, "Content-Type": "application/json", "accept": "*/*"}
                r2 = self.session.post(f"{self.base_url}{endpoint}", data=body2, headers=headers2, timeout=15)
                if r2.status_code in [200, 201]:
                    return {"success": True, "data": r2.json(), "bracket_fallback": True}
                else:
                    return {"success": False, "error": r2.text}
            
            log.error(f"Order placement failed: {r.status_code} - {r.text}")
            return {"success": False, "error": r.text}
        except Exception as e:
            log.error(f"Order exception: {e}")
            return {"success": False, "error": str(e)}

    def place_limit_order(self, side: str, qty: float, price: float, symbol: str = None, reduce_only: bool = True) -> dict:
        """
        Places limit order (e.g. Take Profit).
        """
        if not self.is_live:
            return {"success": True}
        target_sym = symbol or self.symbol
        endpoint = "/v1/order/place-order"
        ts = str(int(time.time() * 1000))
        payload = {
            "timestamp": ts,
            "placeType": "ORDER_FORM",
            "quantity": qty,
            "side": side.upper(),
            "symbol": target_sym,
            "type": "LIMIT",
            "price": float(price),
            "reduceOnly": reduce_only,
            "marginAsset": "INR",
            "deviceType": "WEB",
            "userCategory": "EXTERNAL",
        }
        body = json.dumps(payload, separators=(",", ":"))
        sig = self._sign_body(payload)
        headers = {"api-key": self.api_key, "signature": sig, "Content-Type": "application/json", "accept": "*/*"}
        try:
            r = self.session.post(f"{self.base_url}{endpoint}", data=body, headers=headers, timeout=15)
            log.info(f"Limit order: {r.status_code} - {r.text}")
            return {"success": r.status_code in [200, 201], "data": r.text}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def place_stop_market_order(self, side: str, qty: float, stop_price: float, symbol: str = None, reduce_only: bool = True) -> dict:
        """
        Places stop market order (e.g. Stop Loss).
        """
        if not self.is_live:
            return {"success": True}
        target_sym = symbol or self.symbol
        endpoint = "/v1/order/place-order"
        ts = str(int(time.time() * 1000))
        payload = {
            "timestamp": ts,
            "placeType": "ORDER_FORM",
            "quantity": qty,
            "side": side.upper(),
            "symbol": target_sym,
            "type": "STOP_MARKET",
            "stopPrice": float(stop_price),
            "reduceOnly": reduce_only,
            "marginAsset": "INR",
            "deviceType": "WEB",
            "userCategory": "EXTERNAL",
        }
        body = json.dumps(payload, separators=(",", ":"))
        sig = self._sign_body(payload)
        headers = {"api-key": self.api_key, "signature": sig, "Content-Type": "application/json", "accept": "*/*"}
        try:
            r = self.session.post(f"{self.base_url}{endpoint}", data=body, headers=headers, timeout=15)
            log.info(f"Stop market order: {r.status_code} - {r.text}")
            return {"success": r.status_code in [200, 201], "data": r.text}
        except Exception as e:
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

    def set_split_tp_sl(self, position_id: str, tp_price: float, sl_price: float, qty: float) -> dict:
        """
        Sets Split TP and SL for an open position.
        """
        if not self.is_live:
            return {"success": True, "simulated": True}

        endpoint = "/v2/order/split-tp-sl"
        ts = str(int(time.time() * 1000))
        params = {
            "positionId": str(position_id),
            "splitTakeProfitOrders": [{
                "quantity": float(qty),
                "price": float(tp_price)
            }],
            "splitStopLossOrders": [{
                "quantity": float(qty),
                "price": float(sl_price)
            }],
            "timestamp": ts
        }
        body = json.dumps(params, separators=(",", ":"))
        sig = self._sign_body(params)
        headers = {"api-key": self.api_key, "signature": sig, "Content-Type": "application/json", "accept": "*/*"}

        try:
            r = self.session.post(f"{self.base_url}{endpoint}", data=body, headers=headers, timeout=12)
            log.info(f"Split TP/SL status: {r.status_code}, response: {r.text}")
            return {"success": r.status_code in [200, 201], "data": r.text}
        except Exception as e:
            log.error(f"Error setting split TP/SL: {e}")
            return {"success": False, "error": str(e)}

    def attach_tpsl_to_open_position(self, symbol: str = None, tp_price: float = None, sl_price: float = None) -> dict:
        """
        Finds an open position and attaches TP and SL natively on Shark Exchange.
        Uses /v2/order/split-tp-sl with fallback to native Reduce-Only LIMIT & STOP_MARKET orders.
        """
        target_sym = symbol or self.symbol
        positions = self.get_open_positions()
        target_pos = None
        pos_list = positions if isinstance(positions, list) else (positions.get("data") or positions.get("result") or [])
        if isinstance(pos_list, list):
            for p in pos_list:
                p_sym = p.get("contractPair", "") or p.get("symbol", "")
                if target_sym.replace("-", "").upper() in p_sym.replace("-", "").upper():
                    target_pos = p
                    break

        if not target_pos:
            return {"success": False, "error": f"No open position found for {target_sym}", "positions": positions}

        pos_id = str(target_pos.get("positionId") or target_pos.get("id"))
        qty = float(target_pos.get("quantity") or target_pos.get("positionAmount") or target_pos.get("size") or 0.0)
        pos_type = str(target_pos.get("positionType", "")).upper()
        entry_price = float(target_pos.get("entryPrice", 0.0))

        # Default TP & SL if not specified
        if tp_price is None or sl_price is None:
            if pos_type == "LONG":
                sl_price = sl_price or (entry_price - 49.0 if entry_price > 0 else 10079.0)
                tp_price = tp_price or (entry_price + (49.0 * 1.5) if entry_price > 0 else 10202.0)
            else:
                sl_price = sl_price or (entry_price + 49.0 if entry_price > 0 else 10177.0)
                tp_price = tp_price or (entry_price - (49.0 * 1.5) if entry_price > 0 else 10054.0)

        tp_price = round(float(tp_price), 1)
        sl_price = round(float(sl_price), 1)

        log.info(f"Attaching TP/SL to position {pos_id} ({pos_type} {qty} {target_sym}): TP={tp_price}, SL={sl_price}")
        split_res = self.set_split_tp_sl(pos_id, tp_price, sl_price, qty)
        fallback_res = {}
        if not split_res.get("success"):
            exit_side = "SELL" if pos_type == "LONG" else "BUY"
            log.warning(f"Split TP/SL API did not return 200/201. Placing fallback reduce-only orders for {target_sym}")
            r_tp = self.place_limit_order(exit_side, qty, tp_price, target_sym, reduce_only=True)
            r_sl = self.place_stop_market_order(exit_side, qty, sl_price, target_sym, reduce_only=True)
            fallback_res = {"tp_order": r_tp, "sl_order": r_sl}

        is_success = split_res.get("success") or (fallback_res.get("tp_order", {}).get("success") and fallback_res.get("sl_order", {}).get("success"))
        return {
            "success": is_success,
            "pos_id": pos_id,
            "qty": qty,
            "tp_price": tp_price,
            "sl_price": sl_price,
            "split_res": split_res,
            "fallback_res": fallback_res,
            "position": target_pos
        }

    def place_bracket_order(self, side: str, qty: float, stop_loss: float, take_profit: float, symbol: str = None) -> dict:
        """
        Places entry order and automatically attaches TP & SL to the open position on Shark Exchange.
        """
        target_sym = symbol or self.symbol
        # 1. Place Entry Market Order
        res = self.place_market_order(side, qty, symbol=target_sym)
        if not res.get("success"):
            return {
                "success": False,
                "error": res.get("error", "Market entry failed"),
                "raw": res
            }

        # 2. Wait briefly for position to register on exchange
        time.sleep(1.5)
        attach_res = self.attach_tpsl_to_open_position(target_sym, tp_price=take_profit, sl_price=stop_loss)

        return {
            "success": True,
            "side": side,
            "qty": qty,
            "sl": stop_loss,
            "tp": take_profit,
            "attach_res": attach_res,
            "raw": res,
        }

