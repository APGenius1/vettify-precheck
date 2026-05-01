from flask import Flask, request, jsonify, send_file, render_template_string
from flask_cors import CORS
import io
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from datetime import datetime, timedelta
import os
import uuid
import math
import sqlite3

app = Flask(__name__)
app.secret_key = os.urandom(24).hex()
CORS(app)

DATABASE = "vettify.db"

# ================= DB =================
def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.execute("""CREATE TABLE IF NOT EXISTS usage (
        email TEXT PRIMARY KEY,
        count INTEGER DEFAULT 0,
        paid BOOLEAN DEFAULT 0,
        first_use TEXT
    )""")
    conn.commit()
    conn.close()

init_db()

# ================= ACTUARIAL CORE =================
G_A, G_B, G_C = 0.00022, 0.000027, 0.092

def force_mortality(age):
    return G_A + G_B * math.exp(G_C * age)

def smoker_mult(age):
    if age < 30:
        return 2.5
    elif age < 40:
        return 2.2
    elif age < 50:
        return 1.9
    elif age < 60:
        return 1.6
    else:
        return 1.4

def qx(age, smoker):
    mu = force_mortality(age)
    if smoker:
        mu *= smoker_mult(age)
    return 1 - math.exp(-mu / 12)

def epv_benefit(cov, age, term, smoker):
    v = 1 / (1 + 0.06 / 12)
    epv, surv = 0, 1
    for m in range(term * 12):
        a = age + m // 12
        epv += (v ** (m+1)) * surv * qx(a, smoker) * cov
        surv *= (1 - qx(a, smoker))
    return epv

def epv_prem(age, term, smoker):
    v = 1 / (1 + 0.06 / 12)
    epv, surv = 0, 1
    for m in range(term * 12):
        a = age + m // 12
        epv += (v ** m) * surv
        surv *= (1 - qx(a, smoker))
    return epv

def premium_calc(age, gender, smoker, income, coverage, term):
    p = epv_benefit(coverage, age, term, smoker) / max(epv_prem(age, term, smoker), 1)

    if gender == "male":
        p *= 1.12

    ratio = coverage / income if income else 10
    if ratio > 4:
        p *= 1 + min(0.6, (ratio - 4) * 0.1)

    return max(80, min(15000, round(p)))

# ================= UNDERWRITING ENGINE =================
def risk_explanation(score):
    if score >= 70:
        return "Strong profile: standard mortality, minimal underwriting friction, likely straight-through approval."
    elif score >= 40:
        return "Moderate profile: expect underwriting questions and possible loadings."
    return "High-risk profile: specialist underwriting required, possible medical evidence."

def insurer_match(score, smoker):
    if smoker:
        return ["Momentum", "BrightRock"], "Smoker pricing applies; specialist underwriting required."
    if score >= 70:
        return ["Discovery", "Momentum", "Old Mutual", "Sanlam"], "Top-tier underwriting bands."
    if score >= 40:
        return ["Old Mutual", "Momentum"], "Standard underwriting expected."
    return ["Hollard", "BrightRock"], "Restricted underwriting pool."

def underwriting_summary(premium, risk, age, coverage, income):
    ratio = coverage / income if income else 0
    return {
        "risk_score": risk["score"],
        "risk_level": risk["level"],
        "risk_explanation": risk_explanation(risk["score"]),
        "premium": premium,
        "confidence_range": {
            "low": int(premium * 0.88),
            "high": int(premium * 1.12),
            "confidence": "±12%"
        },
        "coverage_ratio": f"{round(ratio, 1)}x income",
        "coverage_interpretation": "Within norms" if ratio <= 4 else "Elevated risk" if ratio <= 8 else "High strain loading expected"
    }

# ================= RISK SCORE =================
def risk_score(age, smoker, coverage, income, term):
    score = 70
    drivers = []

    if smoker:
        score -= 30
        drivers.append({"factor": "Smoker", "impact": -30, "explanation": "Increased mortality risk"})

    if age > 55:
        score -= 12
        drivers.append({"factor": f"Age {age}", "impact": -12, "explanation": "Higher mortality at advanced age"})
    elif age < 30:
        score += 5
        drivers.append({"factor": f"Age {age}", "impact": 5, "explanation": "Young age - favorable mortality"})

    ratio = coverage / income if income else 0
    if ratio > 8:
        score -= 15
        drivers.append({"factor": "High coverage/income", "impact": -15, "explanation": f"Coverage {ratio:.1f}x income exceeds guidelines"})
    elif ratio > 6:
        score -= 10
        drivers.append({"factor": "Elevated coverage/income", "impact": -10, "explanation": f"Coverage {ratio:.1f}x income may trigger review"})
    elif ratio > 4:
        score -= 5
        drivers.append({"factor": "Moderate coverage/income", "impact": -5, "explanation": f"Coverage {ratio:.1f}x income near guideline"})

    if term > 25:
        score -= 5
        drivers.append({"factor": "Long term", "impact": -5, "explanation": "Policy term >25 years adds uncertainty"})

    score = max(10, min(95, score))
    level = "Low" if score >= 70 else "Moderate" if score >= 40 else "High"

    return {"score": score, "level": level, "drivers": drivers}

# ================= MARKET =================
def market(premium, age):
    return {
        "min": round(premium * 0.88),
        "max": round(premium * 1.12),
        "percentile": 45 if age < 30 else 55 if age < 45 else 48,
        "confidence": 12
    }

# ================= API ROUTES =================
@app.route("/calculate", methods=["POST"])
def calculate():
    d = request.json
    prem = premium_calc(d["age"], d["gender"], d["smoker"], d["income"], d["coverage"], d["term"])
    risk = risk_score(d["age"], d["smoker"], d["coverage"], d["income"], d["term"])
    market_data = market(prem, d["age"])
    insurers, note = insurer_match(risk["score"], d["smoker"])
    under = underwriting_summary(prem, risk, d["age"], d["coverage"], d["income"])

    return jsonify({
        "premium": prem,
        "risk": risk,
        "market": market_data,
        "insurers": insurers,
        "insurer_note": note,
        "underwriting": under
    })

@app.route("/generate-report", methods=["POST"])
def report():
    d = request.json

    prem = premium_calc(d["age"], d["gender"], d["smoker"], d["income"], d["coverage"], d["term"])
    risk = risk_score(d["age"], d["smoker"], d["coverage"], d["income"], d["term"])
    insurers, note = insurer_match(risk["score"], d["smoker"])
    under = underwriting_summary(prem, risk, d["age"], d["coverage"], d["income"])

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph("VETTIFY UNDERWRITING REPORT", styles["Title"]))
    story.append(Spacer(1, 0.2*inch))

    story.append(Paragraph(f"<b>Risk Score:</b> {under['risk_score']} / 100", styles["Normal"]))
    story.append(Paragraph(f"<b>Insight:</b> {under['risk_explanation']}", styles["Normal"]))
    story.append(Spacer(1, 0.1*inch))

    story.append(Paragraph(f"<b>Premium Estimate:</b> R{prem} / month", styles["Normal"]))
    story.append(Paragraph(f"Range: R{under['confidence_range']['low']} – R{under['confidence_range']['high']} ({under['confidence_range']['confidence']})", styles["Normal"]))
    story.append(Spacer(1, 0.1*inch))

    story.append(Paragraph(f"<b>Coverage Ratio:</b> {under['coverage_ratio']}", styles["Normal"]))
    story.append(Paragraph(under["coverage_interpretation"], styles["Normal"]))
    story.append(Spacer(1, 0.2*inch))

    story.append(Paragraph("<b>Recommended Insurers:</b> " + ", ".join(insurers), styles["Normal"]))
    story.append(Paragraph(note, styles["Normal"]))
    story.append(Spacer(1, 0.2*inch))

    story.append(Paragraph("This report expires in 7 days. Not a binding quote.", styles["Italic"]))

    doc.build(story)
    buffer.seek(0)

    return send_file(buffer, as_attachment=True, download_name=f"vettify_report_{d['age']}.pdf")

# ================= FRONTEND =================
@app.route('/')
def home():
    return render_template_string('''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Vettify PreCheck | Decision Intelligence System</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Inter', sans-serif; background: #f8fafc; }
        .navbar { background: white; border-bottom: 1px solid #e2e8f0; padding: 16px 0; position: sticky; top: 0; z-index: 100; }
        .nav-container { max-width: 1280px; margin: 0 auto; padding: 0 32px; display: flex; justify-content: space-between; align-items: center; }
        .logo { font-size: 24px; font-weight: 800; color: #0a2540; text-decoration: none; }
        .logo span { font-weight: 400; color: #5b6e8c; }
        .btn-outline { padding: 8px 20px; border: 1.5px solid #0a2540; border-radius: 30px; background: transparent; color: #0a2540; font-weight: 600; cursor: pointer; }
        .hero { background: linear-gradient(135deg, #0a2540 0%, #1b4d3e 100%); color: white; padding: 60px 32px; text-align: center; }
        .hero h1 { font-size: 48px; font-weight: 800; margin-bottom: 16px; }
        .hero p { font-size: 18px; opacity: 0.9; max-width: 600px; margin: 0 auto; }
        .hero-badge { background: rgba(255,255,255,0.2); display: inline-block; padding: 4px 12px; border-radius: 30px; font-size: 12px; margin-bottom: 24px; }
        .main-container { max-width: 1280px; margin: -40px auto 48px; padding: 0 32px; display: grid; grid-template-columns: 1fr 0.9fr; gap: 32px; }
        .form-card { background: white; border-radius: 28px; box-shadow: 0 8px 30px rgba(0,0,0,0.1); overflow: hidden; }
        .form-header { padding: 28px 32px; border-bottom: 1px solid #eef2f6; }
        .form-header h2 { font-size: 22px; font-weight: 700; color: #0a2540; }
        .form-body { padding: 32px; }
        .form-group { margin-bottom: 24px; }
        label { display: block; font-weight: 600; margin-bottom: 8px; color: #1a2c3e; font-size: 13px; text-transform: uppercase; }
        input, select { width: 100%; padding: 14px 16px; border: 1.5px solid #e2e8f0; border-radius: 14px; font-size: 15px; }
        .radio-group { display: flex; gap: 32px; margin-top: 8px; }
        .radio-group label { display: flex; align-items: center; font-weight: 500; gap: 10px; cursor: pointer; }
        .row-group { display: flex; gap: 16px; }
        .row-group .form-group { flex: 1; }
        .inline-group { display: flex; gap: 12px; }
        .inline-group select { flex: 2; }
        .inline-group input { flex: 1; }
        .btn-primary { width: 100%; padding: 16px; background: linear-gradient(135deg, #0a2540 0%, #1b4d3e 100%); color: white; border: none; border-radius: 16px; font-weight: 700; cursor: pointer; margin-top: 16px; }
        .result-card { background: white; border-radius: 28px; padding: 32px; position: sticky; top: 100px; }
        .result-score { text-align: center; padding: 24px; background: #f8fafc; border-radius: 20px; margin-bottom: 24px; }
        .score-number { font-size: 64px; font-weight: 800; }
        .premium-box { background: #f0fdf4; padding: 16px; border-radius: 16px; text-align: center; }
        .premium-amount { font-size: 28px; font-weight: 800; color: #16a34a; }
        .drivers-list { background: #f8fafc; border-radius: 16px; padding: 20px; margin: 16px 0; }
        .driver-item { display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #ddd; }
        .driver-impact-neg { color: #dc2626; font-weight: 600; }
        .driver-impact-pos { color: #16a34a; font-weight: 600; }
        .paywall { background: #fef3c7; border-radius: 20px; padding: 24px; text-align: center; margin-top: 24px; }
        .paywall-price { font-size: 32px; font-weight: 800; margin: 16px 0; }
        .btn-pay { width: 100%; padding: 14px; background: #0070ba; color: white; border: none; border-radius: 12px; font-weight: 700; cursor: pointer; }
        .value-badge { background: #e8f0fe; border-radius: 12px; padding: 12px; margin: 16px 0; text-align: center; }
        .hidden { display: none; }
        .loading { text-align: center; padding: 40px; }
        .error { color: #dc2626; padding: 12px; background: #fee2e2; border-radius: 12px; margin-top: 16px; display: none; }
        .footer { text-align: center; padding: 48px; color: #8a9bb0; border-top: 1px solid #e2e8f0; margin-top: 48px; }
        @media (max-width: 900px) { .main-container { grid-template-columns: 1fr; } .hero h1 { font-size: 32px; } }
    </style>
</head>
<body>
    <nav class="navbar"><div class="nav-container"><a href="/" class="logo">VETTIFY <span>PreCheck</span></a><button class="btn-outline" onclick="alert('Broker Access: R1,999/month\\nContact: hello@vettifyprecheck.com')">For Brokers →</button></div></nav>
    <div class="hero"><div class="hero-badge">⚡ Decision Intelligence System</div><h1>Know before you apply</h1><p>Risk breakdown • Insurer matching • Market benchmarks</p></div>
    <div class="main-container">
        <div class="form-card">
            <div class="form-header"><h2>Client Assessment</h2></div>
            <div class="form-body">
                <form id="assessmentForm">
                    <div class="row-group"><div class="form-group"><label>Age</label><input type="number" id="age" required min="18" max="80" placeholder="35"></div><div class="form-group"><label>Gender</label><select id="gender"><option value="male">Male</option><option value="female">Female</option></select></div></div>
                    <div class="form-group"><label>Smoker</label><div class="radio-group"><label><input type="radio" name="smoker" value="yes"> Yes</label><label><input type="radio" name="smoker" value="no" checked> No</label></div></div>
                    <div class="form-group"><label>Annual Income (ZAR)</label><input type="number" id="income" required placeholder="500000"></div>
                    <div class="form-group"><label>Coverage Amount (ZAR)</label><div class="inline-group"><select id="coverage_preset"><option value="1000000">R1,000,000</option><option value="2000000">R2,000,000</option><option value="3000000">R3,000,000</option><option value="5000000">R5,000,000</option><option value="10000000">R10,000,000</option><option value="custom">Custom</option></select><input type="number" id="coverage_custom" placeholder="Enter amount" style="display:none"></div></div>
                    <div class="form-group"><label>Term (Years)</label><div class="inline-group"><select id="term_preset"><option value="10">10</option><option value="15">15</option><option value="20" selected>20</option><option value="25">25</option><option value="30">30</option><option value="custom">Custom</option></select><input type="number" id="term_custom" placeholder="Enter years" style="display:none"></div></div>
                    <div class="form-group"><label>Your Email</label><input type="email" id="email" required placeholder="broker@example.com"></div>
                    <button type="submit" class="btn-primary" id="calculateBtn">Analyze Risk Profile →</button>
                </form>
                <div class="error" id="error"></div>
            </div>
        </div>
        <div class="result-card" id="resultCard">
            <div id="freeResult">
                <div class="result-score"><div class="score-number" id="riskScore">—</div><div class="score-label">Risk Score (0-100)</div><div id="riskExplanation" style="margin-top: 8px; font-size: 13px;"></div></div>
                <div><h4>Risk Drivers</h4><div id="driversContainer" class="drivers-list">Complete the form to see analysis</div></div>
                <div><h4>Premium Estimate</h4><div id="premiumText">—</div><div id="confidenceRange" style="font-size: 12px;"></div></div>
                <div><h4>Insurer Matching</h4><div id="insurerText">—</div><div id="insurerNote" style="font-size: 12px;"></div></div>
                <div><h4>Coverage Ratio</h4><div id="coverageRatio">—</div><div id="coverageInterpretation" style="font-size: 12px;"></div></div>
                <div class="value-badge" id="valueBadge" style="display:none;">💰 Market Value: R500 - R1,500<br>You're getting this for only R49</div>
                <div class="paywall" id="paywall"><h3>🔓 Unlock Full Intelligence Report</h3><div class="paywall-price">R49</div><button class="btn-pay" id="payBtn">Download Full Report →</button></div>
            </div>
            <div id="loadingResult" class="loading hidden">⏳ Analyzing...</div>
        </div>
    </div>
    <div class="footer"><p>Vettify PreCheck · Gompertz-Makeham Actuarial Model</p></div>
    <script>
        let currentFormData = null;
        const coveragePreset = document.getElementById('coverage_preset');
        const coverageCustom = document.getElementById('coverage_custom');
        const termPreset = document.getElementById('term_preset');
        const termCustom = document.getElementById('term_custom');
        coveragePreset.addEventListener('change', function() { coverageCustom.style.display = this.value === 'custom' ? 'block' : 'none'; });
        termPreset.addEventListener('change', function() { termCustom.style.display = this.value === 'custom' ? 'block' : 'none'; });
        document.getElementById('assessmentForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            const email = document.getElementById('email').value.trim();
            if (!email) { showError('Please enter your email'); return; }
            const btn = document.getElementById('calculateBtn');
            btn.disabled = true;
            btn.textContent = 'Analyzing...';
            document.getElementById('loadingResult').classList.remove('hidden');
            document.getElementById('freeResult').classList.add('hidden');
            const termYears = termPreset.value === 'custom' ? parseInt(termCustom.value) : parseInt(termPreset.value);
            const coverageAmount = coveragePreset.value === 'custom' ? parseInt(coverageCustom.value) : parseInt(coveragePreset.value);
            const formData = { age: parseInt(document.getElementById('age').value), gender: document.getElementById('gender').value, smoker: document.querySelector('input[name="smoker"]:checked').value === 'yes', income: parseInt(document.getElementById('income').value), coverage: coverageAmount, term: termYears, email: email };
            currentFormData = formData;
            try {
                const res = await fetch('/calculate', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(formData) });
                const data = await res.json();
                document.getElementById('riskScore').innerHTML = data.risk.score;
                document.getElementById('riskScore').style.color = data.risk.score >= 70 ? '#16a34a' : (data.risk.score >= 40 ? '#ea580c' : '#dc2626');
                document.getElementById('riskExplanation').innerHTML = data.underwriting.risk_explanation;
                let driversHtml = '';
                for (let d of data.risk.drivers) { driversHtml += `<div class="driver-item"><span>${d.factor}</span><span class="${d.impact < 0 ? 'driver-impact-neg' : (d.impact > 0 ? 'driver-impact-pos' : '')}">${d.impact > 0 ? '+' : ''}${d.impact}</span></div><div style="font-size: 11px; color: #666; margin-bottom: 8px;">${d.explanation}</div>`; }
                document.getElementById('driversContainer').innerHTML = driversHtml || 'No significant risk factors';
                document.getElementById('premiumText').innerHTML = `<div class="premium-box"><span class="premium-amount">R${data.premium} - R${Math.round(data.premium * 1.12)}</span><br><small>/ month</small></div>`;
                document.getElementById('confidenceRange').innerHTML = `Confidence: ${data.underwriting.confidence_range.confidence} (R${data.underwriting.confidence_range.low} - R${data.underwriting.confidence_range.high})`;
                document.getElementById('insurerText').innerHTML = data.insurers.join(', ');
                document.getElementById('insurerNote').innerHTML = data.insurer_note;
                document.getElementById('coverageRatio').innerHTML = data.underwriting.coverage_ratio;
                document.getElementById('coverageInterpretation').innerHTML = data.underwriting.coverage_interpretation;
                document.getElementById('valueBadge').style.display = 'block';
                document.getElementById('freeResult').classList.remove('hidden');
                btn.disabled = false;
                btn.textContent = 'Analyze Risk Profile →';
                document.getElementById('loadingResult').classList.add('hidden');
            } catch(err) { showError('Error analyzing. Please try again.'); resetButton(btn); }
            function showError(msg) { const errDiv = document.getElementById('error'); errDiv.textContent = msg; errDiv.style.display = 'block'; setTimeout(() => errDiv.style.display = 'none', 4000); }
            function resetButton(btn) { btn.disabled = false; btn.textContent = 'Analyze Risk Profile →'; document.getElementById('loadingResult').classList.add('hidden'); }
        });
        document.getElementById('payBtn').addEventListener('click', async () => {
            if (!currentFormData) { alert('Please calculate a risk profile first'); return; }
            const btn = document.getElementById('payBtn');
            btn.textContent = 'Generating...';
            btn.disabled = true;
            try {
                const res = await fetch('/generate-report', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(currentFormData) });
                if (!res.ok) throw new Error('Failed');
                const blob = await res.blob();
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `vettify_report_${currentFormData.age}.pdf`;
                a.click();
                URL.revokeObjectURL(url);
                alert('✅ Report downloaded!');
            } catch(err) { alert('Error: ' + err.message); }
            btn.textContent = 'Download Full Report →';
            btn.disabled = false;
        });
    </script>
</body>
</html>
    ''')

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=5000)
