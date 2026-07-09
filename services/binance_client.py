import time
import hmac
import hashlib
import requests
from flask import current_app

TESTNET_BASE = "https://testnet.binance.vision"


def _sign(params: dict, secret: str) -> str:
    query_string = "&".join(f"{k}={v}" for k, v in params.items())
    return hmac.new(secret.encode(), query_string.encode(), hashlib.sha256).hexdigest()


def _headers():
    return {"X-MBX-APIKEY": current_app.config["BINANCE_API_KEY"]}


def get_price(symbol: str) -> float:
    """Public endpoint, no signing needed."""
    resp = requests.get(f"{TESTNET_BASE}/api/v3/ticker/price", params={"symbol": symbol}, timeout=10)
    resp.raise_for_status()
    return float(resp.json()["price"])


def get_klines(symbol: str, interval: str = "15m", limit: int = 50):
    """Historical candles, used by the strategy for moving averages."""
    resp = requests.get(
        f"{TESTNET_BASE}/api/v3/klines",
        params={"symbol": symbol, "interval": interval, "limit": limit},
        timeout=10,
    )
    resp.raise_for_status()
    # each kline: [open_time, open, high, low, close, volume, ...]
    return [float(k[4]) for k in resp.json()]  # closing prices


def place_order(symbol: str, side: str, quantity: float, order_type: str = "MARKET"):
    secret = current_app.config["BINANCE_API_SECRET"]
    params = {
        "symbol": symbol,
        "side": side.upper(),
        "type": order_type,
        "quantity": quantity,
        "timestamp": int(time.time() * 1000),
    }
    params["signature"] = _sign(params, secret)

    resp = requests.post(f"{TESTNET_BASE}/api/v3/order", headers=_headers(), params=params, timeout=10)
    resp.raise_for_status()
    return resp.json()