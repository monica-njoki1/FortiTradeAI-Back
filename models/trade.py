from datetime import datetime
from models import db

class Trade(db.Model):
    __tablename__ = "trades"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    symbol = db.Column(db.String(20), nullable=False)
    side = db.Column(db.String(4), nullable=False)  # "buy" or "sell"
    quantity = db.Column(db.Float, nullable=False)
    price = db.Column(db.Float, nullable=False)

    risk_score = db.Column(db.Integer, default=0)
    risk_decision = db.Column(db.String(20), default="approved")  # approved/flagged/blocked
    triggered_factors = db.Column(db.JSON, default=list)

    binance_order_id = db.Column(db.String(64), nullable=True)
    execution_status = db.Column(db.String(20), default="pending")  # pending/executed/failed/simulated

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @staticmethod
    def create(user, trade_request, risk_score=0, decision="approved", factors=None,
               binance_order_id=None, execution_status="pending"):
        trade = Trade(
            user_id=user.id,
            symbol=trade_request["symbol"],
            side=trade_request["side"],
            quantity=trade_request["quantity"],
            price=trade_request["price"],
            risk_score=risk_score,
            risk_decision=decision,
            triggered_factors=factors or [],
            binance_order_id=binance_order_id,
            execution_status=execution_status,
        )
        db.session.add(trade)
        db.session.commit()
        return trade

    def to_dict(self):
        return {
            "id": self.id,
            "symbol": self.symbol,
            "side": self.side,
            "quantity": self.quantity,
            "price": self.price,
            "risk_score": self.risk_score,
            "risk_decision": self.risk_decision,
            "triggered_factors": self.triggered_factors,
            "binance_order_id": self.binance_order_id,
            "execution_status": self.execution_status,
            "created_at": self.created_at.isoformat(),
        }