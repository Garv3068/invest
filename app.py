from flask import Flask, request, jsonify
from flask_cors import CORS
import numpy as np
import yfinance as yf
import requests
from groq import Groq
import scipy.stats as stats

app = Flask(__name__)
CORS(app)

# 1. CONFIGURATION
GROQ_API_KEY = "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"
client = Groq(api_key=GROQ_API_KEY)

ASSET_STDS = {"equity": 0.18, "gold": 0.12, "bond": 0.03}
CORRELATIONS = {
    ("equity", "gold"): 0.10,
    ("equity", "bond"): -0.20,
    ("gold", "bond"): 0.15,
}


# 2. DATA FETCHING FUNCTIONS
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
    try:
        # We replace the [...] with the actual messages list
        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": "You are a wealth mentor for an Indian investment simulator. Focus on historical data and math."
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
        return "Simulation complete. Ready for your questions!"

# 3. CORE API ENDPOINTS
# 3. CORE API ENDPOINT
@app.route('/simulate', methods=['POST'])
def simulate():
    try:
        data = request.json
        # 1. Gather Inputs
        initial = float(data.get('initial', 100000))
        sip = float(data.get('sip', 5000))
        years = int(data.get('years', 10))
        num_sims = int(data.get('numSims', 200))

        # 2. Get Live Market Stats
        live_returns = get_live_market_data()
        inflation = get_india_inflation()

        # 3. Allocation Weights
        eq_w = float(data.get('equity', 50)) / 100
        gd_w = float(data.get('gold', 20)) / 100
        bd_w = float(data.get('bond', 30)) / 100

        # 4. Calculate Portfolio Mean and Volatility
        mean_annual = (eq_w * live_returns['equity'] + gd_w * live_returns['gold'] + bd_w * live_returns['bond'])

        # Calculate Variance (Simplified version)
        vol_annual = np.sqrt((eq_w * 0.18) ** 2 + (gd_w * 0.12) ** 2 + (bd_w * 0.05) ** 2)

        # 5. Monte Carlo Engine
        months = years * 12
        m_mean = (1 + mean_annual) ** (1 / 12) - 1
        m_vol = vol_annual / np.sqrt(12)

        # Generate random returns for all simulations
        daily_returns = np.random.normal(m_mean, m_vol, (num_sims, months))
        paths = np.zeros((num_sims, months + 1))
        paths[:, 0] = initial

        for m in range(1, months + 1):
            # Previous balance * return + monthly SIP
            paths[:, m] = paths[:, m - 1] * (1 + daily_returns[:, m - 1]) + sip

        # 6. Prepare Data for Frontend
        final_vals = paths[:, -1]

        # Calculate invested path (straight line)
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
            "total_invested": float(initial + (sip * months)),  # FIXES NaN
            "loss_prob": float(stats.norm.cdf((0 - mean_annual * years) / (vol_annual * np.sqrt(years))) * 100),
            "ai_advice": get_ai_insight(eq_w * 100, gd_w * 100, bd_w * 100, years, np.percentile(final_vals, 50),
                                        inflation, live_returns)
        })

    except Exception as e:
        print(f"Server Error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 400

@app.route('/chat', methods=['POST'])
def chat():
    try:
        data = request.json
        user_q = data.get('question')

        # FIX: Ensure no '...' are left in this list
        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": "You are the InvestNova Mentor. Use the user's portfolio data to provide educational insights about market history and risk."
                },
                {
                    "role": "user",
                    "content": f"Portfolio: {data['equity']}% Equity, {data['gold']}% Gold. Current Median: {data['median']}. Question: {user_q}"
                }
            ],
            model="llama-3.1-8b-instant",
        )
        answer = chat_completion.choices[0].message.content
        return jsonify({"answer": answer})
    except Exception as e:
        # This will print the error to your PyCharm console for easier debugging
        print(f"Chat Error: {e}")
        return jsonify({"answer": f"Error: {str(e)}"})
if __name__ == '__main__':
    app.run()
