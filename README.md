# FortiTrade AI — Backend

A fraud-aware trading bot backend that screens every trade for risk before it executes, using a rule-based fraud engine, Gemma AI (via Fireworks) for plain-language risk explanations, and real order execution on Binance Spot Testnet.

Built for the **AMD Developer Hackathon: ACT II — Unicorn Track**.

## Live deployment

Backend: `https://fortitradeai.onrender.com`

## What this does

1. A lightweight strategy engine reads live Binance price data and generates a buy/sell/hold signal (SMA crossover)
2. Every trade request is scored against fraud risk factors (rapid-fire trading, volume spikes, new devices, location mismatches, rapid liquidation patterns)
3. Flagged trades get a plain-language risk explanation from Gemma AI via Fireworks
4. Only approved/flagged (non-blocked) trades are executed on Binance Spot Testnet by default
5. Everything is logged with full audit trail (risk score, factors, execution status)

## Tech stack

- **Flask** + **Flask-SQLAlchemy** — API and ORM
- **Flask-JWT-Extended** — authentication
- **Flask-Migrate** (Alembic) — database migrations
- **Flask-CORS** — cross-origin support for the frontend
- **Binance Spot Testnet API** — real (paper) trade execution
- **Fireworks AI** — LLM inference for fraud risk explanations
- **PostgreSQL / SQLite** — via `SQLALCHEMY_DATABASE_URI`

## Project structure

```
├── app.py                     # App factory, blueprint registration
├── config.py                  # Environment-based configuration
├── start.sh                   # Migration + gunicorn startup script (used by Docker)
├── Dockerfile
├── requirements.txt
├── models/
│   ├── user.py                 # User model (auth, profile pic, device history)
│   └── trade.py                # Trade model (risk score, execution status)
├── blueprints/
│   ├── auth.py                 # Register, login, profile pic, account deletion
│   ├── trading.py              # Trade signal, trade execution, trade history
│   └── fraud.py                # Fraud alert retrieval
├── services/
│   ├── fraud_engine.py         # Rule-based risk scoring
│   ├── fireworks_client.py     # Gemma AI risk explanation calls
│   ├── binance_client.py       # Binance Testnet price/order calls
│   └── trading_strategy.py     # SMA crossover signal generation
└── migrations/                 # Alembic migration history
```

## Setup — local development

### 1. Clone and create a virtual environment

```bash
git clone https://github.com/monica-njoki1/FortiTradeAI-Back.git
cd FortiTradeAI-Back
python3 -m venv venv
source venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment variables

```bash
cp .env.example .env
```

Then fill in `.env` with real values:

| Variable | Description | Where to get it |
|---|---|---|
| `SECRET_KEY` | Flask session secret | Generate: `python3 -c "import secrets; print(secrets.token_hex(32))"` |
| `JWT_SECRET_KEY` | JWT signing secret | Same command, different output |
| `DATABASE_URL` | Database connection string | `sqlite:///fortitrade.db` for local dev |
| `CORS_ORIGINS` | Allowed frontend origin(s) | e.g. `http://localhost:5173` |
| `FIREWORKS_API_KEY` | Fireworks AI API key | [app.fireworks.ai/settings/users/api-keys](https://app.fireworks.ai/settings/users/api-keys) |
| `GEMMA_MODEL_ID` | Fireworks model identifier | e.g. `accounts/fireworks/models/llama4-maverick-instruct-basic` |
| `BINANCE_API_KEY` | Binance Testnet API key | [testnet.binance.vision](https://testnet.binance.vision) (log in with GitHub, generate key) |
| `BINANCE_API_SECRET` | Binance Testnet API secret | Same as above |
| `FLASK_APP` | Entry point for Flask CLI | `app` |

### 4. Run database migrations

```bash
flask db upgrade
```

### 5. Start the server

```bash
python app.py
```

Backend runs at `http://localhost:5000`. Confirm it's up:

```bash
curl http://localhost:5000/api/health
```

## Running with Docker

```bash
docker build -t fortitrade-backend .
docker run -p 5000:5000 --env-file .env fortitrade-backend
```

The container runs `start.sh`, which applies migrations before starting gunicorn.

## API endpoints

### Auth (`/api/auth`)
| Method | Path | Description |
|---|---|---|
| POST | `/register` | Create account (name, email, password) |
| POST | `/login` | Log in, returns JWT |
| GET | `/me` | Get current user profile *(auth required)* |
| PATCH | `/profile-pic` | Upload profile picture (base64, image/gif) *(auth required)* |
| DELETE | `/profile-pic` | Remove profile picture *(auth required)* |
| DELETE | `/account` | Permanently delete account *(auth required)* |

### Trading (`/api/trades`)
| Method | Path | Description |
|---|---|---|
| GET | `/signal?symbol=BTCUSDT` | Get current AI strategy signal *(auth required)* |
| POST | `` | Submit a trade — fraud-checked, then executed on Binance Testnet *(auth required)* |
| GET | `` | List your trade history *(auth required)* |
| DELETE | `/<id>` | Delete a trade record *(auth required)* |

### Fraud (`/api/fraud`)
| Method | Path | Description |
|---|---|---|
| GET | `/alerts` | List all flagged/blocked trades for the current user *(auth required)* |

## Deployment notes

- Deployed on **Render** (Frankfurt region — Binance Testnet blocks requests from US-region servers with HTTP 451)
- Migrations run automatically on every deploy via `start.sh`
- SQLite is used for the hackathon deployment; swap `DATABASE_URL` to a PostgreSQL connection string for production use, since Render's filesystem is ephemeral

## Real-money trading: operator-only pilot

This repository is now safe-by-default: `BINANCE_ENV=testnet` is the default and **no setting silently switches to live money**. It is suitable for a single-operator pilot only, not a multi-customer exchange product. The server holds one Binance API credential, so allowing arbitrary app users to submit orders would pool control of that account.

To enable a carefully limited Spot pilot, configure a PostgreSQL database and these production-only variables:

```env
BINANCE_ENV=live
LIVE_TRADING_ENABLED=true
OPERATOR_USER_EMAIL=the-binance-account-owner@example.com
MAX_ORDER_NOTIONAL_USDT=25
SECRET_KEY=<unique-long-random-value>
JWT_SECRET_KEY=<different-unique-long-random-value>
```

The matching user must also send `"confirm_live_trade": true` with each order. Every order is checked against Binance's current symbol quantity and minimum-notional rules, capped by `MAX_ORDER_NOTIONAL_USDT`, and assigned a unique client order ID before it is submitted. If the exchange call times out, the order is marked `needs_reconciliation`; do not retry it until its client order ID is checked on Binance.

Before launch, keep the API key withdrawal permission disabled, use Binance's trusted-IP restriction for the deploy's fixed egress IP, complete your jurisdiction/compliance review, publish risk disclosures and support contacts, add independent security review plus monitoring/alerting, and run a sustained Testnet pilot. For a customer-facing product, redesign custody and key management: users must connect their own exchange account through an approved OAuth/broker flow or a dedicated encrypted-secret/KMS system with consent and revocation—not share one app-held trading key.
