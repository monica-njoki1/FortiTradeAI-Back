import os
from datetime import timedelta
from typing import Optional


def _as_bool(value: Optional[str], default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dev-jwt-secret-change-me")
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=int(os.getenv("JWT_ACCESS_TOKEN_HOURS", "1")))

    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///fortitrade.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    FIREWORKS_API_KEY = os.getenv("FIREWORKS_API_KEY")
    GEMMA_MODEL_ID = os.getenv("GEMMA_MODEL_ID")

    BINANCE_API_KEY = os.getenv("BINANCE_API_KEY")
    BINANCE_API_SECRET = os.getenv("BINANCE_API_SECRET")
    # Testnet is deliberately the only default. A live order needs three independent
    # opt-ins: this setting, LIVE_TRADING_ENABLED, and a per-request confirmation.
    BINANCE_ENV = os.getenv("BINANCE_ENV", "testnet").strip().lower()
    LIVE_TRADING_ENABLED = _as_bool(os.getenv("LIVE_TRADING_ENABLED"))
    OPERATOR_USER_EMAIL = os.getenv("OPERATOR_USER_EMAIL", "").strip().lower()
    MAX_ORDER_NOTIONAL_USDT = float(os.getenv("MAX_ORDER_NOTIONAL_USDT", "100"))
    ORDER_TIMEOUT_SECONDS = float(os.getenv("ORDER_TIMEOUT_SECONDS", "10"))

    CORS_ORIGINS = os.getenv("CORS_ORIGINS", "https://fortitrade-ai.vercel.app").split(",")


def validate_runtime_config(app):
    """Refuse unsafe live-trading configuration at startup, before any order path runs."""
    environment = app.config["BINANCE_ENV"]
    if environment not in {"testnet", "live"}:
        raise RuntimeError("BINANCE_ENV must be either 'testnet' or 'live'.")
    if app.config["MAX_ORDER_NOTIONAL_USDT"] <= 0:
        raise RuntimeError("MAX_ORDER_NOTIONAL_USDT must be greater than zero.")
    if environment == "live":
        if not app.config["LIVE_TRADING_ENABLED"]:
            raise RuntimeError("Live Binance requires LIVE_TRADING_ENABLED=true.")
        if not app.config["OPERATOR_USER_EMAIL"]:
            raise RuntimeError("Live Binance requires OPERATOR_USER_EMAIL to prevent shared-account trading.")
        if not app.config["BINANCE_API_KEY"] or not app.config["BINANCE_API_SECRET"]:
            raise RuntimeError("Live Binance requires BINANCE_API_KEY and BINANCE_API_SECRET.")
        insecure = {"dev-secret-change-me", "dev-jwt-secret-change-me"}
        if app.config["SECRET_KEY"] in insecure or app.config["JWT_SECRET_KEY"] in insecure:
            raise RuntimeError("Live Binance requires strong SECRET_KEY and JWT_SECRET_KEY values.")
