"""Small, deliberately conservative Binance Spot REST client."""
import hashlib
import hmac
import time
from decimal import Decimal, InvalidOperation
from urllib.parse import urlencode

import requests
from flask import current_app

TESTNET_BASE = "https://testnet.binance.vision"
LIVE_BASE = "https://api.binance.com"


class BinanceError(Exception):
    """A safe error suitable for returning to API callers."""


def _base_url():
    return LIVE_BASE if current_app.config["BINANCE_ENV"] == "live" else TESTNET_BASE


def _sign(params: dict, secret: str) -> str:
    return hmac.new(secret.encode(), urlencode(params).encode(), hashlib.sha256).hexdigest()


def _headers():
    api_key = current_app.config["BINANCE_API_KEY"]
    if not api_key:
        raise BinanceError("Binance API key is not configured.")
    return {"X-MBX-APIKEY": api_key}


def _request(method: str, path: str, *, params=None, signed=False):
    params = dict(params or {})
    if signed:
        secret = current_app.config["BINANCE_API_SECRET"]
        if not secret:
            raise BinanceError("Binance API secret is not configured.")
        params["timestamp"] = int(time.time() * 1000)
        params["recvWindow"] = 5000
        params["signature"] = _sign(params, secret)
    try:
        response = requests.request(method, f"{_base_url()}{path}", params=params,
                                    headers=_headers() if signed else None,
                                    timeout=current_app.config["ORDER_TIMEOUT_SECONDS"])
    except requests.RequestException as exc:
        raise BinanceError("Binance is unreachable; order status is unknown. Check the exchange before retrying.") from exc
    if not response.ok:
        try:
            detail = response.json().get("msg", "Unexpected Binance response")
        except ValueError:
            detail = "Unexpected Binance response"
        raise BinanceError(f"Binance rejected the request: {detail}")
    return response.json()


def _decimal(value, field="value", allow_zero=False) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise BinanceError(f"{field} must be a positive decimal number.") from exc
    if not result.is_finite() or result < 0 or (not allow_zero and result == 0):
        raise BinanceError(f"{field} must be a positive decimal number.")
    return result


def get_price(symbol: str) -> float:
    return float(_request("GET", "/api/v3/ticker/price", params={"symbol": symbol})["price"])


def get_klines(symbol: str, interval: str = "15m", limit: int = 50):
    data = _request("GET", "/api/v3/klines", params={"symbol": symbol, "interval": interval, "limit": limit})
    return [float(k[4]) for k in data]


def validate_market_order(symbol: str, quantity, price) -> str:
    """Validate against Binance's current symbol filters before submitting an order."""
    if not isinstance(symbol, str) or not symbol.isalnum() or symbol != symbol.upper() or len(symbol) > 20:
        raise BinanceError("symbol must be an uppercase Binance Spot symbol, for example BTCUSDT.")
    quantity, price = _decimal(quantity, "quantity"), _decimal(price, "price")
    info = _request("GET", "/api/v3/exchangeInfo", params={"symbol": symbol})
    symbols = info.get("symbols", [])
    if len(symbols) != 1 or symbols[0].get("status") != "TRADING":
        raise BinanceError("This symbol is not currently available for Spot trading.")
    filters = {item["filterType"]: item for item in symbols[0].get("filters", [])}
    lot = filters.get("MARKET_LOT_SIZE") or filters.get("LOT_SIZE")
    if lot:
        minimum, maximum, step = (
            _decimal(lot["minQty"], allow_zero=True),
            _decimal(lot["maxQty"], allow_zero=True),
            _decimal(lot["stepSize"], allow_zero=True),
        )
        if (minimum > 0 and quantity < minimum) or (maximum > 0 and quantity > maximum):
            raise BinanceError(f"quantity must be between {minimum} and {maximum}.")
        if step > 0 and quantity % step != 0:
            raise BinanceError(f"quantity must be in increments of {step}.")
    notional = quantity * price
    notional_filter = filters.get("NOTIONAL") or filters.get("MIN_NOTIONAL")
    if notional_filter and notional < _decimal(notional_filter["minNotional"], allow_zero=True):
        raise BinanceError("Order value is below Binance's minimum notional.")
    cap = Decimal(str(current_app.config["MAX_ORDER_NOTIONAL_USDT"]))
    if notional > cap:
        raise BinanceError(f"Order value ({notional}) exceeds this app's limit of {cap} USDT.")
    return format(quantity, "f")


def place_order(symbol: str, side: str, quantity: str, client_order_id: str):
    if side not in {"BUY", "SELL"}:
        raise BinanceError("side must be BUY or SELL.")
    return _request("POST", "/api/v3/order", signed=True, params={
        "symbol": symbol, "side": side, "type": "MARKET", "quantity": quantity,
        "newClientOrderId": client_order_id, "newOrderRespType": "FULL",
    })
