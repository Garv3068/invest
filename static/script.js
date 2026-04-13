// ===== 1. GLOBAL STATE & UI HELPERS =====
let state = { equity: 50, gold: 20, bond: 30 };
let myChart = null;

// Format numbers to Indian Rupee style (e.g., ₹1,00,000)
const fmt = (n) => "₹" + Math.round(n).toLocaleString('en-IN');

// Update labels when sliders move
document.getElementById('timeHorizon').addEventListener('input', function() {
    document.getElementById('horizonLabel').textContent = this.value + ' years';
    document.getElementById('horizonValue').textContent = this.value + 'Y';
});

document.getElementById('numSims').addEventListener('input', function() {
    document.getElementById('simLabel').textContent = this.value;
    document.getElementById('simValue').textContent = this.value;
});

// ===== 2. ASSET ALLOCATION LOGIC =====
function updateAllocation() {
    state.equity = parseInt(document.getElementById('eqSlider').value);
    state.gold = parseInt(document.getElementById('goldSlider').value);
    state.bond = parseInt(document.getElementById('bondSlider').value);
    
    // Sync text labels
    document.getElementById('eqLabel').textContent = state.equity + '%';
    document.getElementById('goldLabel').textContent = state.gold + '%';
    document.getElementById('bondLabel').textContent = state.bond + '%';
    
    // Update the visual color bar
    document.getElementById('barEq').style.width = state.equity + '%';
    document.getElementById('barGold').style.width = state.gold + '%';
    document.getElementById('barBond').style.width = state.bond + '%';

    // Remove active class from preset buttons if user manually slides
    document.querySelectorAll('.tab-pill').forEach(t => t.classList.remove('active'));
}

function setPreset(name, btn) {
    const presets = {
        conservative: { eq: 30, gold: 20, bond: 50 },
        balanced: { eq: 50, gold: 20, bond: 30 },
        aggressive: { eq: 80, gold: 10, bond: 10 }
    };
    const p = presets[name];
    document.getElementById('eqSlider').value = p.eq;
    document.getElementById('goldSlider').value = p.gold;
    document.getElementById('bondSlider').value = p.bond;
    
    updateAllocation();
    btn.classList.add('active');
}


async function runSimulation() {
    const btn = document.getElementById('runBtn');
    btn.innerHTML = '<i class="ph-bold ph-spinner"></i> Python Processing...';
    btn.disabled = true;

    const payload = {
        initial: parseFloat(document.getElementById('initialAmount').value),
        sip: parseFloat(document.getElementById('monthlySIP').value),
        years: parseInt(document.getElementById('timeHorizon').value),
        numSims: parseInt(document.getElementById('numSims').value),
        equity: state.equity,
        gold: state.gold,
        bond: state.bond
    };

    try {
        const response = await fetch('http://127.0.0.1:5000/simulate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        const data = await response.json();

        if (data.status === "success") {
            renderChart(data);
            updateUIStats(data);

            // ===== ADDED: RISK METER UPDATE LOGIC =====
            const lossProb = data.loss_prob; // Value from Python backend
            const lossBar = document.getElementById('lossBar');
            const lossText = document.getElementById('lossText');

            if (lossBar && lossText) {
                // Update the bar width and text
                lossBar.style.width = lossProb + "%";
                lossText.innerText = `Loss Probability: ${lossProb.toFixed(1)}%`;

                // Update color based on risk level
                if (lossProb > 20) {
                    lossBar.style.backgroundColor = "#ff4d4d"; // Red for high risk
                } else if (lossProb > 10) {
                    lossBar.style.backgroundColor = "#f1c40f"; // Yellow for medium
                } else {
                    lossBar.style.backgroundColor = "#2ecc71"; // Green for safe
                }
            }
            // ==========================================
            
            if (data.ai_advice) {
                showAIMessage(data.ai_advice);
            }
        }

    } catch (error) {
        console.error("Connection failed:", error);
        showAIMessage("Connection Error: Is the PyCharm server running?");
    } finally {
        btn.innerHTML = '<i class="ph-bold ph-play"></i> Run Simulation';
        btn.disabled = false;
    }
}

// ===== 4. CHART & STAT UPDATES =====
// Replace your existing renderChart function with this:
function renderChart(data) {
    const ctx = document.getElementById('mcChart').getContext('2d');
    const labels = Array.from({ length: data.median_path.length }, (_, i) => i % 12 === 0 ? `Y${i/12}` : '');

    if (myChart) myChart.destroy();

    myChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [
                { 
                    label: 'Median (Expected)', 
                    data: data.median_path, 
                    borderColor: '#4f6ef7', 
                    borderWidth: 3, 
                    pointRadius: 0, 
                    fill: false, 
                    tension: 0.4 
                },
                { 
                    label: 'Best Case (95th)', 
                    data: data.upper_path, // Updated from best_path to upper_path
                    borderColor: '#10b981', 
                    borderDash: [5, 5], 
                    borderWidth: 1.5, 
                    pointRadius: 0, 
                    fill: false 
                },
                { 
                    label: 'Worst Case (5th)', 
                    data: data.lower_path, // Updated from worst_path to lower_path
                    borderColor: '#ef4444', 
                    borderDash: [5, 5], 
                    borderWidth: 1.5, 
                    pointRadius: 0, 
                    fill: false 
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: { 
                y: { 
                    ticks: { callback: (v) => fmt(v) }, 
                    grid: { color: '#edf0f7' } 
                },
                x: { grid: { display: false } }
            }
        }
    });
}

// Replace your existing updateUIStats function with this:
function updateUIStats(data) {
    // We use || 0 to prevent NaN if the value is missing
    document.getElementById('statBest').innerText = fmt(data.best || 0);
    document.getElementById('statMedian').innerText = fmt(data.median || 0);
    document.getElementById('statWorst').innerText = fmt(data.worst || 0);
    document.getElementById('statInvested').innerText = fmt(data.total_invested || 0);
    
    document.getElementById('simCountText').innerText = document.getElementById('numSims').value;
}

// ===== 5. AI EXPLAINER LOGIC =====
function showAIMessage(text) {
    const chat = document.getElementById('aiChat');
    const msg = document.createElement('div');
    msg.className = 'ai-msg';
    msg.innerHTML = `
        <div class="ai-avatar"><i class="ph-bold ph-robot"></i></div>
        <div class="ai-bubble">
            <div class="tip-tag">AI Mentor Analysis</div>
            <p>${text}</p>
        </div>
    `;
    chat.prepend(msg); // Newest analysis (Live API data) goes to the top
    chat.scrollTop = 0;
}

function askAI(topic) {
    // We grab the values currently visible in your stat cards to make the manual buttons feel 'aware'
    const medianWealth = document.getElementById('statMedian').innerText;
    const invested = document.getElementById('statInvested').innerText;

    const responses = {
        risk: `With your current mix, we're projecting a median wealth of ${medianWealth}. Your risk is buffered by Gold and Bonds, but Equity drives that growth.`,
        sip: `Your ${invested} total investment is being optimized by Rupee Cost Averaging. You're buying more units when the market dips!`,
        crash: "Crashes are temporary. Even in the 'Worst Case' scenario shown on your chart, historical data shows that markets eventually trend upward.",
        diversification: "By splitting your money between Nifty 50, Gold, and Bonds, you've ensured that a crash in one asset won't destroy your entire portfolio.",
        beginner: "The math is clear: time in the market beats timing the market. Start your SIP today to hit that growth curve early."
    };
    
    showAIMessage(responses[topic] || "How can I help you with your portfolio today?");
}

// Handles Enter key in the chat input
function handleKeyPress(e) {
    if (e.key === 'Enter') askCustomQuestion();
}

async function askCustomQuestion() {
    const input = document.getElementById('userQuery');
    const query = input.value.trim();
    if (!query) return;

    // 1. Display the user's message in the chat
    input.value = '';
    const chat = document.getElementById('aiChat');
    const userMsg = document.createElement('div');
    userMsg.className = 'ai-msg user-msg';
    userMsg.innerHTML = `<div class="ai-bubble user"><p>${query}</p></div>`;
    chat.prepend(userMsg);

    // 2. Request custom answer from Python Backend
    try {
        const response = await fetch('http://127.0.0.1:5000/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                question: query,
                equity: state.equity,
                gold: state.gold,
                bond: state.bond,
                median: document.getElementById('statMedian').innerText
            })
        });
        const data = await response.json();
        showAIMessage(data.answer); // Reuse existing helper to show AI response
    } catch (error) {
        showAIMessage("I'm having a bit of trouble thinking... is the backend server running?");
    }
}


// Initialize on page load
document.getElementById('runBtn').addEventListener('click', runSimulation);
window.onload = runSimulation;