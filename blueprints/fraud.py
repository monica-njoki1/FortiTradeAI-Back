from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from models.trade import Trade

fraud_bp = Blueprint("fraud", __name__, url_prefix="/api/fraud")


@fraud_bp.route("/alerts", methods=["GET"])
@jwt_required()
def get_alerts():
    user_id = int(get_jwt_identity())
    flagged = Trade.query.filter(
        Trade.user_id == user_id,
        Trade.risk_decision.in_(["flagged", "blocked"])
    ).order_by(Trade.created_at.desc()).all()

    return jsonify([t.to_dict() for t in flagged]), 200