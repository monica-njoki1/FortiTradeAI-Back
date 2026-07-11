from datetime import datetime
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from models import db
from models.user import User
from models.trade import Trade
from services.fraud_engine import evaluate_trade
from services.fireworks_client import analyze_trade_risk
from services.trading_strategy import generate_signal
from services.binance_client import place_order, get_price

trading_bp = Blueprint("trading", __name__, url_prefix="/api/trades")


@trading_bp.route("/signal", methods=["GET"])
@jwt_required()
def get_signal():
    """Ask the strategy engine what it currently thinks, without executing anything."""
    symbol = request.args.get("symbol", "BTCUSDT")
    try:
        signal = generate_signal(symbol)
        return jsonify(signal), 200
    except Exception as e:
        return jsonify({"error": f"Could not fetch signal: {str(e)}"}), 502


@trading_bp.route("", methods=["POST"])
@jwt_required()
def create_trade():
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    trade_request = request.get_json(silent=True) or {}
    required = {"symbol", "side", "quantity"}
    if not required.issubset(trade_request):
        return jsonify({"error": f"Missing fields, need: {required}"}), 400

    # Always use the live Binance price rather than trusting a client-supplied price
    try:
        live_price = get_price(trade_request["symbol"])
    except Exception as e:
        return jsonify({"error": f"Could not reach Binance testnet: {str(e)}"}), 502
    trade_request["price"] = live_price

    request_meta = {
        "ip": request.remote_addr,
        "device_fingerprint": request.headers.get("X-Device-Fingerprint", "unknown"),
        "timestamp": datetime.utcnow(),
        "geo": request.headers.get("X-Geo"),
    }

    # Step 1: fraud check gate
    risk_result = evaluate_trade(user, trade_request, request_meta)

    # Remember this device going forward — a device only counts as "new"
    # the first time it's ever used, not on every single trade
    fp = request_meta["device_fingerprint"]
    if fp and fp not in (user.known_devices or []):
        user.known_devices = (user.known_devices or []) + [fp]
        db.session.commit()

    if risk_result["decision"] == "blocked":
        return jsonify({"status": "blocked", "risk": risk_result}), 403

    explanation = None
    if risk_result["decision"] == "flagged":
        explanation = analyze_trade_risk(trade_request, risk_result)

    # Step 2: execute on Binance testnet (only reached if not blocked)
    binance_order_id = None
    execution_status = "simulated"
    try:
        order = place_order(
            symbol=trade_request["symbol"],
            side=trade_request["side"],
            quantity=trade_request["quantity"],
        )
        binance_order_id = str(order.get("orderId"))
        execution_status = "executed"
    except Exception as e:
        execution_status = "failed"

    trade = Trade.create(
        user, trade_request,
        risk_score=risk_result["score"],
        decision=risk_result["decision"],
        factors=risk_result["triggered_factors"],
        binance_order_id=binance_order_id,
        execution_status=execution_status,
    )

    return jsonify({
        "status": "success",
        "trade": trade.to_dict(),
        "risk": risk_result,
        "gemma_explanation": explanation,
    }), 201


@trading_bp.route("", methods=["GET"])
@jwt_required()
def list_trades():
    user_id = int(get_jwt_identity())
    trades = Trade.query.filter_by(user_id=user_id).order_by(Trade.created_at.desc()).all()
    return jsonify([t.to_dict() for t in trades]), 200


@trading_bp.route("/<int:trade_id>", methods=["DELETE"])
@jwt_required()
def delete_trade(trade_id):
    user_id = int(get_jwt_identity())
    trade = Trade.query.filter_by(id=trade_id, user_id=user_id).first()
    if not trade:
        return jsonify({"error": "Trade not found"}), 404

    db.session.delete(trade)
    db.session.commit()
    return jsonify({"status": "success"}), 200