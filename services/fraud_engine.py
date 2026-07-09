from datetime import datetime, timedelta
from models.trade import Trade

RISK_WEIGHTS = {
    "rapid_fire": 25,
    "volume_spike": 20,
    "off_hours": 10,
    "new_device": 20,
    "location_mismatch": 25,
    "rapid_liquidation": 30,
}

RISK_THRESHOLD_FLAG = 40
RISK_THRESHOLD_BLOCK = 70


def score_trade(user, trade_request, request_meta):
    score = 0
    triggered = []

    recent_trades = Trade.query.filter(
        Trade.user_id == user.id,
        Trade.created_at >= datetime.utcnow() - timedelta(minutes=10)
    ).all()

    if len(recent_trades) >= 5:
        score += RISK_WEIGHTS["rapid_fire"]
        triggered.append("rapid_fire")

    if user.avg_trade_size and trade_request["quantity"] * trade_request["price"] > user.avg_trade_size * 5:
        score += RISK_WEIGHTS["volume_spike"]
        triggered.append("volume_spike")

    hour = request_meta["timestamp"].hour
    if hour in range(1, 5):
        score += RISK_WEIGHTS["off_hours"]
        triggered.append("off_hours")

    if request_meta.get("device_fingerprint") not in (user.known_devices or []):
        score += RISK_WEIGHTS["new_device"]
        triggered.append("new_device")

    if user.last_known_location and request_meta.get("geo") and request_meta.get("geo") != user.last_known_location:
        score += RISK_WEIGHTS["location_mismatch"]
        triggered.append("location_mismatch")

    if trade_request["side"] == "sell":
        recent_buy = next((t for t in recent_trades
                            if t.symbol == trade_request["symbol"] and t.side == "buy"), None)
        if recent_buy:
            score += RISK_WEIGHTS["rapid_liquidation"]
            triggered.append("rapid_liquidation")

    return score, triggered


def evaluate_trade(user, trade_request, request_meta):
    score, triggered = score_trade(user, trade_request, request_meta)

    decision = "approved"
    if score >= RISK_THRESHOLD_BLOCK:
        decision = "blocked"
    elif score >= RISK_THRESHOLD_FLAG:
        decision = "flagged"

    return {
        "score": score,
        "triggered_factors": triggered,
        "decision": decision,
    }