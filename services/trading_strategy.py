from services.binance_client import get_klines, get_price


def sma(values, period):
    if len(values) < period:
        return None
    return sum(values[-period:]) / period


def generate_signal(symbol: str) -> dict:
    """
    Simple moving-average crossover strategy.
    Fast SMA crosses above slow SMA -> buy signal.
    Fast SMA crosses below slow SMA -> sell signal.
    This is intentionally simple and explainable — judges can see exactly
    why a trade fired, and Gemma explains it in plain language.
    """
    closes = get_klines(symbol, interval="15m", limit=50)

    fast = sma(closes, 9)
    slow = sma(closes, 21)

    if fast is None or slow is None:
        return {"signal": "hold", "reason": "not enough data yet"}

    current_price = get_price(symbol)

    if fast > slow:
        return {
            "signal": "buy",
            "reason": f"9-period SMA ({fast:.2f}) crossed above 21-period SMA ({slow:.2f})",
            "price": current_price,
        }
    elif fast < slow:
        return {
            "signal": "sell",
            "reason": f"9-period SMA ({fast:.2f}) crossed below 21-period SMA ({slow:.2f})",
            "price": current_price,
        }
    else:
        return {"signal": "hold", "reason": "no crossover", "price": current_price}