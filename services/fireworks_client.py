import requests
import json
from flask import current_app

FIREWORKS_URL = "https://api.fireworks.ai/inference/v1/chat/completions"

FRAUD_EXPLANATION_SYSTEM_PROMPT = """You are a financial fraud risk analyst embedded in a trading platform.
You will be given a trade's risk factors and score. Respond ONLY with valid JSON, no markdown, no preamble.

JSON schema:
{
  "summary": "one sentence, plain language, for the end user",
  "severity": "low" | "medium" | "high",
  "recommended_action": "allow" | "confirm_with_user" | "block_and_review",
  "reasoning": "2-3 sentences explaining WHY this pattern is risky, referencing the specific factors given"
}"""


def analyze_trade_risk(trade_request: dict, risk_result: dict) -> dict:
    api_key = current_app.config["FIREWORKS_API_KEY"]
    model_id = current_app.config["GEMMA_MODEL_ID"]

    user_prompt = f"""Trade details:
- Symbol: {trade_request['symbol']}
- Side: {trade_request['side']}
- Quantity: {trade_request['quantity']}
- Price: {trade_request['price']}

Risk score: {risk_result['score']}/100
Triggered factors: {', '.join(risk_result['triggered_factors']) or 'none'}

Analyze this and respond with the required JSON."""

    try:
        resp = requests.post(
            FIREWORKS_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": model_id,
                "messages": [
                    {"role": "system", "content": FRAUD_EXPLANATION_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                "max_tokens": 250,
                "temperature": 0.3,
            },
            timeout=15,
        )
        resp.raise_for_status()
        raw = resp.json()["choices"][0]["message"]["content"]

        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            cleaned = raw.strip().strip("```json").strip("```").strip()
            return json.loads(cleaned)

    except Exception as e:
        # Fail safe: don't let a Gemma outage block trading entirely
        return {
            "summary": "Automated risk analysis unavailable — manual review recommended.",
            "severity": "medium",
            "recommended_action": "confirm_with_user",
            "reasoning": f"Explanation service error: {str(e)}",
        }