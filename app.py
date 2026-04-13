from flask import Flask, request, jsonify
from flask_cors import CORS
import numpy as np
import yfinance as yf
import requests
import os
from groq import Groq
import scipy.stats as stats

app = Flask(__name__)
CORS(app)

# ===================== CONFIG =====================
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

client = None
if GROQ_API_KEY:
    client = Groq(api_key=GROQ_API_KEY)

ASSET_STDS = {"equity": 0.18, "gold": 0.12, "bond": 0.03}

# ===================== DATA FUNCTIONS =====================

def get_india_inflation():
    try:
        url = "https://api.worldbank.org/v2/country/IND/indicator/FP.CPI.TOTL.ZG?format=json"
        response = requests.get(url, timeout=5).json()
        for entry in response[1]:
            if entry['value'] is not None:
                return float(entry['value']) / 100
        return 0.06
    except:
        return 0.06


def get_live_market_data():
    tickers = {"equity": "^NSEI", "gold": "GC=F", "bond": "^IRX"}
    live_returns = {}

    try:
        for asset, sym in tickers.items():
            hist = yf.Ticker(sym).history(period="1y")
            if not hist.empty:
                ret = (hist['Close'].iloc[-1] - hist['Close'].iloc[0]) / hist['Close'].iloc[0]
                live_returns[asset] = ret
            else:
                live_returns[asset] = 0.10
        return live_returns
    except:
        return {"equity": 0.12, "gold": 0.09, "bond": 0.07}


def get_ai_insight(eq, gd, bd, years, final_amt, inflation, live_returns):
    if not client:
        return "AI insights unavailable (missing API key)."

    try:
        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": "You are a wealth mentor for an Indian investment simulator. Keep answers short and insightful."
                },
                {
                    "role": "user",
                    "content": f"Analyze: Equity {eq}%, Gold {gd}%, Bonds {bd}%. Inflation: {inflation*100:.1f}%. Nifty Return: {live_returns['equity']*100:.1f}%. Does ₹{final_amt:,.0f} beat inflation? Answer in 2 short sentences."
                }
            ],
            model="llama-3.1-8b-instant",
        )
        return chat_completion.choices[0].message.content

    except Exception as e:
        print(f"Insight Error: {e}")
        return "Simulation complete. AI insight unavailable."


# ===================== ROUTES =====================

@app.route("/")
def home():
    return "Flask API is running 🚀"


@app.route('/simulate', methods=['POST'])
def simulate():
    try:
        data = request.json

        # Inputs
        initial = float(data.get('initial', 100000))
        sip = float(data.get('sip', 5000))
        years = int(data.get('years', 10))
        num_sims = int(data.get('numSims', 200))

        # Market data
        live_returns = get_live_market_data()
        inflation = get_india_inflation()

        # Allocation
        eq_w = float(data.get('equity', 50)) / 100
        gd_w = float(data.get('gold', 20)) / 100
        bd_w = float(data.get('bond', 30)) / 100

        # Mean & Volatility
        mean_annual = (
            eq_w * live_returns['equity'] +
            gd_w * live_returns['gold'] +
            bd_w * live_returns['bond']
        )

        vol_annual = np.sqrt(
            (eq_w * 0.18) ** 2 +
            (gd_w * 0.12) ** 2 +
            (bd_w * 0.05) ** 2
        )

        # Monte Carlo
        months = years * 12
        m_mean = (1 + mean_annual) ** (1 / 12) - 1
        m_vol = vol_annual / np.sqrt(12)

        returns = np.random.normal(m_mean, m_vol, (num_sims, months))
        paths = np.zeros((num_sims, months + 1))
        paths[:, 0] = initial

        for m in range(1, months + 1):
            paths[:, m] = paths[:, m - 1] * (1 + returns[:, m - 1]) + sip

        final_vals = paths[:, -1]

        invested_path = [initial + (sip * m) for m in range(months + 1)]

        return jsonify({
            "status": "success",
            "median_path": np.percentile(paths, 50, axis=0).tolist(),
            "upper_path": np.percentile(paths, 95, axis=0).tolist(),
            "lower_path": np.percentile(paths, 5, axis=0).tolist(),
            "invested_path": invested_path,
            "best": float(np.percentile(final_vals, 95)),
            "median": float(np.percentile(final_vals, 50)),
            "worst": float(np.percentile(final_vals, 5)),
            "total_invested": float(initial + (sip * months)),
            "loss_prob": float(
                stats.norm.cdf((0 - mean_annual * years) / (vol_annual * np.sqrt(years))) * 100
            ),
            "ai_advice": get_ai_insight(
                eq_w * 100, gd_w * 100, bd_w * 100,
                years, np.percentile(final_vals, 50),
                inflation, live_returns
            )
        })

    except Exception as e:
        print(f"Server Error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 400


@app.route('/chat', methods=['POST'])
def chat():
    try:
        if not client:
            return jsonify({"answer": "AI service not configured."})

        data = request.json
        user_q = data.get('question')

        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": "You are an investment mentor. Be concise and helpful."
                },
                {
                    "role": "user",
                    "content": f"Portfolio: {data['equity']}% Equity, {data['gold']}% Gold. Median: {data['median']}. Question: {user_q}"
                }
            ],
            model="llama-3.1-8b-instant",
        )

        return jsonify({
            "answer": chat_completion.choices[0].message.content
        })

    except Exception as e:
        print(f"Chat Error: {e}")
        return jsonify({"answer": f"Error: {str(e)}"})


# ===================== RUN =====================

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
