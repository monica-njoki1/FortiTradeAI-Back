import os
from datetime import timedelta

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dev-jwt-secret-change-me")
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=12)

    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///fortitrade.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    FIREWORKS_API_KEY = os.getenv("FIREWORKS_API_KEY")
    GEMMA_MODEL_ID = os.getenv("GEMMA_MODEL_ID")

    BINANCE_API_KEY = os.getenv("BINANCE_API_KEY")
    BINANCE_API_SECRET = os.getenv("BINANCE_API_SECRET")

    CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")