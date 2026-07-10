from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from models import db

class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, default="")
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)

    profile_pic = db.Column(db.Text, nullable=True)  # base64 data URL (image or gif)

    avg_trade_size = db.Column(db.Float, default=0.0)
    known_devices = db.Column(db.JSON, default=list)
    last_known_location = db.Column(db.String(120), nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    trades = db.relationship("Trade", backref="user", lazy=True, cascade="all, delete-orphan")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "profile_pic": self.profile_pic,
            "avg_trade_size": self.avg_trade_size,
            "known_devices": self.known_devices,
            "last_known_location": self.last_known_location,
        }