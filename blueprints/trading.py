from datetime import datetime
from uuid import uuid4
from flask import Blueprint, current_app, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from models import db
from models.user import User
from models.trade import Trade
from services.fraud_engine import evaluate_trade
from services.fireworks_client import analyze_trade_risk
from services.trading_strategy import generate_signal
from services.binance_client import BinanceError, place_order, get_price, validate_market_order

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

    trade_request["symbol"] = str(trade_request["symbol"]).upper().strip()
    trade_request["side"] = str(trade_request["side"]).upper().strip()
    if trade_request["side"] not in {"BUY", "SELL"}:
        return jsonify({"error": "side must be BUY or SELL"}), 400

    is_live = current_app.config["BINANCE_ENV"] == "live"
    if is_live:
        # This backend deliberately supports one operator account only. Never let
        # arbitrary application users trade a pooled exchange account.
        if user.email.lower() != current_app.config["OPERATOR_USER_EMAIL"]:
            return jsonify({"error": "Live execution is restricted to the configured operator account."}), 403
        if trade_request.get("confirm_live_trade") is not True:
            return jsonify({"error": "Set confirm_live_trade to true to submit a real-money order."}), 400

    # Always use the live Binance price rather than trusting a client-supplied price
    try:
        live_price = get_price(trade_request["symbol"])
    except BinanceError as e:
        return jsonify({"error": str(e)}), 502
    trade_request["price"] = live_price
    try:
        normalized_quantity = validate_market_order(
            trade_request["symbol"], trade_request["quantity"], live_price
        )
        trade_request["quantity"] = float(normalized_quantity)
    except BinanceError as e:
        return jsonify({"error": str(e)}), 400

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
        blocked_trade = Trade.create(
            user, trade_request, risk_score=risk_result["score"],
            decision=risk_result["decision"], factors=risk_result["triggered_factors"],
            execution_status="blocked",
        )
        return jsonify({"status": "blocked", "trade": blocked_trade.to_dict(), "risk": risk_result}), 403

    explanation = None
    if risk_result["decision"] == "flagged":
        explanation = analyze_trade_risk(trade_request, risk_result)

    # Persist a unique client order id *before* the network call. If the response
    # times out, support can reconcile the exact order with Binance safely.
    trade = Trade.create(
        user, trade_request,
        risk_score=risk_result["score"], decision=risk_result["decision"],
        factors=risk_result["triggered_factors"], execution_status="pending",
    )
    trade.binance_client_order_id = f"fta-{trade.id}-{uuid4().hex[:16]}"
    db.session.commit()

    # Step 2: execute only after all controls have passed.
    try:
        order = place_order(
            symbol=trade_request["symbol"],
            side=trade_request["side"],
            quantity=normalized_quantity,
            client_order_id=trade.binance_client_order_id,
        )
        trade.binance_order_id = str(order.get("orderId"))
        trade.execution_status = str(order.get("status", "submitted")).lower()
    except BinanceError as e:
        # Do not claim no order exists: a timed-out request can still have reached
        # the exchange. The client order id is the reconciliation key.
        trade.execution_status = "needs_reconciliation"
        db.session.commit()
        return jsonify({
            "status": "needs_reconciliation", "trade": trade.to_dict(),
            "error": str(e),
            "message": "Do not retry this order until its client order ID is checked on Binance.",
        }), 502
    db.session.commit()

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
