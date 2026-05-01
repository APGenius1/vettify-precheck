from flask import Flask, request, jsonify, send_file, render_template_string
from flask_cors import CORS
import io
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
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
    if age < 30: return 2.5
    elif age < 40: return 2.2
    elif age < 50: return 1.9
    elif age < 60: return 1.6
    else: return 1.4

def qx(age, smoker):
    mu = force_mortality(age)
    if smoker: mu *= smoker_mult(age)
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
    if gender == "male": p *= 1.12
    ratio = coverage / income if income else 10
    if ratio > 4: p *= 1 + min(0.6, (ratio - 4) * 0.1)
    return max(80, min(15000, round(p)))

# ================= UNDERWRITING ENGINE =================
def risk_explanation(score):
    if score >= 70:
        return "This profile would typically proceed through standard underwriting with preferred rates. No significant mortality risk factors identified."
    elif score >= 40:
        return "This profile qualifies for standard underwriting, though additional medical disclosure may be requested depending on final documentation."
    return "This profile requires specialist underwriting. Expect medical evidence requirements and possible loading."

def insurer_match(score, smoker):
    if smoker:
        return ["Momentum", "BrightRock"], "Specialist underwriting applies. Smoker-specific pricing."
    if score >= 70:
        return ["Discovery", "Momentum", "Old Mutual", "Sanlam"], "Preferred underwriting bands available. Straight-through approval likely."
    if score >= 40:
        return ["Old Mutual", "Momentum"], "Standard underwriting expected with normal processing."
    return ["Hollard", "BrightRock"], "Non-standard underwriting. Medical evidence required."

def underwriting_summary(premium, risk, age, coverage, income):
    ratio = coverage / income if income else 0
    return {
        "risk_score": risk["score"],
        "risk_level": risk["level"],
        "risk_explanation": risk_explanation(risk["score"]),
        "premium": premium,
        "confidence_range": {"low": int(premium * 0.88), "high": int(premium * 1.12), "confidence": "±12%"},
        "coverage_ratio": f"{round(ratio, 1)}x income",
        "coverage_interpretation": "Within industry norms" if ratio <= 4 else "Above guideline threshold" if ratio <= 8 else "Significantly above guidelines"
    }

def risk_score(age, smoker, coverage, income, term):
    score = 70
    drivers = []
    if smoker:
        score -= 30
        drivers.append({"factor": "Tobacco Use", "impact": -30, "explanation": "Smoking increases mortality risk by approximately 2x-2.5x depending on age"})
    if age > 55:
        score -= 12
        drivers.append({"factor": f"Age {age}", "impact": -12, "explanation": "Advanced age increases baseline mortality according to Gompertz-Makeham curve"})
    elif age < 30:
        score += 5
        drivers.append({"factor": f"Age {age}", "impact": 5, "explanation": "Young age provides favourable baseline mortality"})
    ratio = coverage / income if income else 0
    if ratio > 8:
        score -= 15
        drivers.append({"factor": "High Coverage/Income", "impact": -15, "explanation": f"Coverage is {ratio:.1f}x income — exceeds typical industry guidelines of 5x"})
    elif ratio > 6:
        score -= 10
        drivers.append({"factor": "Elevated Coverage/Income", "impact": -10, "explanation": f"Coverage is {ratio:.1f}x income — may trigger anti-selection review"})
    elif ratio > 4:
        score -= 5
        drivers.append({"factor": "Moderate Coverage/Income", "impact": -5, "explanation": f"Coverage is {ratio:.1f}x income — near industry guideline threshold"})
    if term > 25:
        score -= 5
        drivers.append({"factor": "Extended Term", "impact": -5, "explanation": "Term exceeding 25 years adds long-term mortality uncertainty"})
    score = max(10, min(95, score))
    level = "Low" if score >= 70 else "Moderate" if score >= 40 else "High"
    return {"score": score, "level": level, "drivers": drivers}

# ================= API ROUTES =================
@app.route("/calculate", methods=["POST"])
def calculate():
    d = request.json
    prem = premium_calc(d["age"], d["gender"], d["smoker"], d["income"], d["coverage"], d["term"])
    risk = risk_score(d["age"], d["smoker"], d["coverage"], d["income"], d["term"])
    insurers, note = insurer_match(risk["score"], d["smoker"])
    under = underwriting_summary(prem, risk, d["age"], d["coverage"], d["income"])
    return jsonify({"premium": prem, "risk": risk, "insurers": insurers, "insurer_note": note, "underwriting": under})

@app.route("/generate-report", methods=["POST"])
def report():
    d = request.json
    prem = premium_calc(d["age"], d["gender"], d["smoker"], d["income"], d["coverage"], d["term"])
    risk = risk_score(d["age"], d["smoker"], d["coverage"], d["income"], d["term"])
    insurers, note = insurer_match(risk["score"], d["smoker"])
    under = underwriting_summary(prem, risk, d["age"], d["coverage"], d["income"])
    
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=72, bottomMargin=72)
    styles = getSampleStyleSheet()
    story = []
    
    # Professional Header
    story.append(Paragraph("VETTIFY PRECHECK", ParagraphStyle('Title', parent=styles['Title'], fontSize=24, textColor=colors.HexColor('#0a2540'), alignment=1, spaceAfter=6)))
    story.append(Paragraph("Pre-Underwriting Intelligence Report", ParagraphStyle('Subtitle', parent=styles['Normal'], fontSize=10, textColor=colors.grey, alignment=1)))
    story.append(Spacer(1, 0.2*inch))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#0a2540')))
    story.append(Spacer(1, 0.2*inch))
    
    # Executive Summary
    story.append(Paragraph("EXECUTIVE SUMMARY", styles['Heading2']))
    story.append(Paragraph(f"This actuarial assessment indicates a {risk['level'].lower()} risk profile with a score of {risk['score']}/100. {under['risk_explanation']}", styles['Normal']))
    story.append(Spacer(1, 0.15*inch))
    
    # Risk Score
    story.append(Paragraph("RISK ASSESSMENT", styles['Heading2']))
    risk_color = colors.HexColor('#16a34a' if risk['score'] >= 70 else '#ea580c' if risk['score'] >= 40 else '#dc2626')
    story.append(Paragraph(f"{risk['score']}<font size=10>/100</font>", ParagraphStyle('Score', parent=styles['Normal'], fontSize=48, textColor=risk_color, alignment=0, spaceAfter=6)))
    story.append(Spacer(1, 0.1*inch))
    
    # Premium
    story.append(Paragraph("PREMIUM ESTIMATE", styles['Heading2']))
    story.append(Paragraph(f"<b>R{prem} - R{round(prem * 1.12)} per month</b>", styles['Normal']))
    story.append(Paragraph(f"Confidence interval: ±12% (R{under['confidence_range']['low']} – R{under['confidence_range']['high']})", styles['Normal']))
    story.append(Paragraph("Estimate assumes standard underwriting with disclosed risk factors.", styles['Italic']))
    story.append(Spacer(1, 0.15*inch))
    
    # Risk Drivers
    story.append(Paragraph("UNDERWRITING FACTORS", styles['Heading2']))
    for d in risk['drivers']:
        story.append(Paragraph(f"• <b>{d['factor']}</b>: {d['explanation']}", styles['Normal']))
        story.append(Spacer(1, 0.05*inch))
    story.append(Spacer(1, 0.1*inch))
    
    # Insurer Recommendations
    story.append(Paragraph("INSURER RECOMMENDATIONS", styles['Heading2']))
    story.append(Paragraph(f"<b>Recommended:</b> {', '.join(insurers)}", styles['Normal']))
    story.append(Paragraph(f"<b>Underwriting Expectation:</b> {note}", styles['Normal']))
    story.append(Spacer(1, 0.15*inch))
    
    # Methodology
    story.append(Paragraph("METHODOLOGY", styles['Heading2']))
    story.append(Paragraph("Assessment uses Gompertz-Makeham mortality model (μ(x) = A + B·e^(C·x)), calibrated to South African mortality tables. Expected Present Value (EPV) calculation with 6% discount rate, monthly step consistency.", ParagraphStyle('Method', parent=styles['Normal'], fontSize=8, textColor=colors.grey)))
    story.append(Spacer(1, 0.15*inch))
    
    # Disclaimer
    story.append(Paragraph("DISCLAIMER", styles['Heading2']))
    story.append(Paragraph("This report is for informational purposes only and does not constitute a binding offer. Valid for 7 days from generation date. Full underwriting required for final approval.", ParagraphStyle('Disclaimer', parent=styles['Normal'], fontSize=7, textColor=colors.grey)))
    story.append(Spacer(1, 0.1*inch))
    story.append(Paragraph(f"Report ID: {str(uuid.uuid4())[:8]} | Expires: {(datetime.now() + timedelta(days=7)).strftime('%d %B %Y')}", ParagraphStyle('Footer', parent=styles['Normal'], fontSize=7, textColor=colors.grey, alignment=1)))
    
    doc.build(story)
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name=f"vettify_intelligence_report.pdf")

@app.route('/')
def home():
    return render_template_string('''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Vettify PreCheck | Pre-Underwriting Intelligence</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
    <style>
        :root { --primary: #0a2540; --secondary: #1b4d3e; --accent: #0070ba; --gold: #c9a03d; }
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Inter', sans-serif; background: #f5f7fa; color: #1a2c3e; }
        
        /* Premium Navbar */
        .navbar { background: white; border-bottom: 1px solid rgba(0,0,0,0.05); padding: 20px 0; position: sticky; top: 0; z-index: 100; backdrop-filter: blur(10px); }
        .nav-container { max-width: 1280px; margin: 0 auto; padding: 0 32px; display: flex; justify-content: space-between; align-items: center; }
        .logo { font-size: 22px; font-weight: 700; color: var(--primary); text-decoration: none; letter-spacing: -0.3px; }
        .logo span { font-weight: 400; color: #5b6e8c; }
        .trust-badge { background: #f0fdf4; color: #16a34a; padding: 6px 14px; border-radius: 40px; font-size: 11px; font-weight: 600; }
        
        /* Hero Section */
        .hero { background: linear-gradient(135deg, #0a2540 0%, #1b4d3e 100%); color: white; padding: 80px 32px; text-align: center; position: relative; }
        .hero-badge { background: rgba(255,255,255,0.12); backdrop-filter: blur(4px); display: inline-block; padding: 6px 16px; border-radius: 40px; font-size: 12px; font-weight: 500; margin-bottom: 24px; letter-spacing: 0.5px; }
        .hero h1 { font-size: 56px; font-weight: 700; margin-bottom: 20px; letter-spacing: -1px; line-height: 1.2; }
        .hero p { font-size: 18px; opacity: 0.85; max-width: 600px; margin: 0 auto; line-height: 1.6; }
        .hero-meta { margin-top: 32px; display: flex; justify-content: center; gap: 32px; flex-wrap: wrap; }
        .hero-meta span { font-size: 13px; opacity: 0.7; }
        
        /* Main Layout */
        .main-container { max-width: 1280px; margin: -50px auto 60px; padding: 0 32px; display: grid; grid-template-columns: 1fr 0.85fr; gap: 40px; }
        
        /* Form Card - Professional */
        .form-card { background: white; border-radius: 28px; box-shadow: 0 20px 40px rgba(0,0,0,0.08); overflow: hidden; }
        .form-header { padding: 28px 32px; border-bottom: 1px solid #eef2f6; background: white; }
        .form-header h2 { font-size: 20px; font-weight: 600; color: var(--primary); }
        .form-header p { font-size: 13px; color: #5b6e8c; margin-top: 6px; }
        .form-body { padding: 32px; }
        .form-group { margin-bottom: 24px; }
        label { display: block; font-weight: 600; margin-bottom: 8px; color: #1a2c3e; font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px; }
        input, select { width: 100%; padding: 14px 16px; border: 1.5px solid #e2e8f0; border-radius: 14px; font-size: 15px; transition: all 0.2s; background: white; }
        input:focus, select:focus { outline: none; border-color: var(--primary); box-shadow: 0 0 0 3px rgba(10,37,64,0.08); }
        .radio-group { display: flex; gap: 32px; margin-top: 8px; }
        .radio-group label { display: flex; align-items: center; font-weight: 500; text-transform: none; gap: 10px; cursor: pointer; }
        .row-group { display: flex; gap: 16px; }
        .row-group .form-group { flex: 1; }
        .inline-group { display: flex; gap: 12px; }
        .inline-group select { flex: 2; }
        .inline-group input { flex: 1; }
        .form-note { font-size: 11px; color: #8a9bb0; margin-top: 6px; }
        .btn-primary { width: 100%; padding: 16px; background: linear-gradient(135deg, #0a2540 0%, #1b4d3e 100%); color: white; border: none; border-radius: 16px; font-size: 15px; font-weight: 600; cursor: pointer; margin-top: 8px; transition: all 0.2s; }
        .btn-primary:hover { transform: translateY(-1px); box-shadow: 0 8px 20px rgba(10,37,64,0.2); }
        
        /* Result Card - Premium */
        .result-card { background: white; border-radius: 28px; box-shadow: 0 20px 40px rgba(0,0,0,0.08); padding: 32px; position: sticky; top: 100px; }
        .risk-score-container { text-align: center; padding: 28px; background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%); border-radius: 24px; margin-bottom: 28px; }
        .risk-score-number { font-size: 72px; font-weight: 800; line-height: 1; }
        .risk-score-label { font-size: 13px; color: #5b6e8c; margin-top: 8px; text-transform: uppercase; letter-spacing: 1px; }
        .section-title { font-size: 13px; font-weight: 700; color: var(--primary); text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 16px; border-left: 3px solid var(--gold); padding-left: 12px; }
        .premium-box { background: #f0fdf4; padding: 20px; border-radius: 20px; text-align: center; margin: 20px 0; border: 1px solid #d1fae5; }
        .premium-amount { font-size: 32px; font-weight: 800; color: #16a34a; }
        .driver-item { display: flex; justify-content: space-between; padding: 12px 0; border-bottom: 1px solid #f0f4f8; }
        .driver-impact-neg { color: #dc2626; font-weight: 600; }
        .driver-impact-pos { color: #16a34a; font-weight: 600; }
        
        /* Paywall - Premium */
        .paywall { background: linear-gradient(135deg, #fef9e6 0%, #fef3c7 100%); border-radius: 20px; padding: 28px; text-align: center; margin-top: 28px; border: 1px solid #fde68a; }
        .paywall h3 { font-size: 18px; font-weight: 700; color: #92400e; margin-bottom: 12px; }
        .paywall-price { font-size: 36px; font-weight: 800; color: var(--primary); margin: 16px 0; }
        .btn-pay { width: 100%; padding: 14px; background: var(--accent); color: white; border: none; border-radius: 12px; font-weight: 700; font-size: 15px; cursor: pointer; transition: all 0.2s; }
        .btn-pay:hover { background: #003087; transform: translateY(-1px); }
        
        .footer { text-align: center; padding: 48px 32px; color: #8a9bb0; border-top: 1px solid #e2e8f0; margin-top: 60px; font-size: 13px; }
        .hidden { display: none; }
        .loading { text-align: center; padding: 60px; background: #f8fafc; border-radius: 24px; }
        .error { color: #dc2626; padding: 12px; background: #fee2e2; border-radius: 12px; margin-top: 16px; display: none; font-size: 13px; }
        
        @media (max-width: 900px) { .main-container { grid-template-columns: 1fr; } .hero h1 { font-size: 36px; } .hero { padding: 50px 24px; } }
    </style>
</head>
<body>
    <nav class="navbar">
        <div class="nav-container">
            <a href="/" class="logo">VETTIFY <span>PreCheck</span></a>
            <div class="trust-badge">⚡ Actuarial Model: Gompertz-Makeham</div>
        </div>
    </nav>

    <div class="hero">
        <div class="hero-badge">UNDERWRITING INTELLIGENCE</div>
        <h1>Know before you submit</h1>
        <p>Actuarial-grade pre-screening using South Africa's mortality benchmarks. Get insurer-matching, risk analysis, and professional underwriting reports.</p>
        <div class="hero-meta"><span>✓ Gompertz-Makeham Mortality Model</span><span>✓ SA Life Tables Calibrated</span><span>✓ 20 Free Assessments</span></div>
    </div>

    <div class="main-container">
        <div class="form-card">
            <div class="form-header"><h2>Client Assessment</h2><p>This assessment simulates insurer underwriting logic using actuarial mortality modelling.</p></div>
            <div class="form-body">
                <form id="assessmentForm">
                    <div class="row-group"><div class="form-group"><label>Age</label><input type="number" id="age" required min="18" max="80" placeholder="35"></div><div class="form-group"><label>Gender</label><select id="gender"><option value="male">Male</option><option value="female">Female</option></select></div></div>
                    <div class="form-group"><label>Smoker Status</label><div class="radio-group"><label><input type="radio" name="smoker" value="yes"> Yes</label><label><input type="radio" name="smoker" value="no" checked> No</label></div><div class="form-note">Tobacco use significantly impacts mortality risk (+80-150% premium loading)</div></div>
                    <div class="form-group"><label>Annual Income (ZAR)</label><input type="number" id="income" required placeholder="500000"><div class="form-note">Used for coverage-to-income ratio analysis (industry guideline: ≤5x annual income)</div></div>
                    <div class="form-group"><label>Coverage Amount (ZAR)</label><div class="inline-group"><select id="coverage_preset"><option value="1000000">R1,000,000</option><option value="2000000">R2,000,000</option><option value="3000000">R3,000,000</option><option value="5000000">R5,000,000</option><option value="10000000">R10,000,000</option><option value="custom">Custom Amount</option></select><input type="number" id="coverage_custom" placeholder="Enter amount" style="display:none"></div></div>
                    <div class="form-group"><label>Term (Years)</label><div class="inline-group"><select id="term_preset"><option value="10">10 years</option><option value="15">15 years</option><option value="20" selected>20 years</option><option value="25">25 years</option><option value="30">30 years</option><option value="custom">Custom Term</option></select><input type="number" id="term_custom" placeholder="Enter years" style="display:none"></div></div>
                    <div class="form-group"><label>Email Address</label><input type="email" id="email" required placeholder="broker@example.com"><div class="form-note">Your report will be sent here ⸱ First 5 assessments free</div></div>
                    <button type="submit" class="btn-primary" id="calculateBtn">Generate Underwriting Assessment →</button>
                </form>
                <div class="error" id="error"></div>
            </div>
        </div>

        <div class="result-card" id="resultCard">
            <div id="freeResult">
                <div class="risk-score-container"><div class="risk-score-number" id="riskScore">—</div><div class="risk-score-label">Risk Score (0-100)</div><div id="riskExplanation" style="margin-top: 12px; font-size: 13px; color: #5b6e8c; line-height: 1.5;"></div></div>
                <div><div class="section-title">Underwriting Factors</div><div id="driversContainer" class="drivers-list" style="margin-bottom: 20px;">Complete assessment to see analysis</div></div>
                <div><div class="section-title">Premium Estimate</div><div id="premiumText">—</div><div id="confidenceRange" style="font-size: 12px; color: #5b6e8c; margin-top: 4px;"></div></div>
                <div><div class="section-title">Insurer Matching</div><div id="insurerText" style="font-weight: 500;">—</div><div id="insurerNote" style="font-size: 12px; color: #5b6e8c; margin-top: 6px;"></div></div>
                <div class="paywall" id="paywall"><h3>📄 Full Underwriting Report</h3><p>Actuarial methodology • Risk drivers • Insurer recommendations • Professional PDF</p><div class="paywall-price">R49</div><button class="btn-pay" id="payBtn">Download Intelligence Report →</button><p style="font-size: 11px; margin-top: 12px;">One-time payment · Instant download · Valid for 7 days</p></div>
            </div>
            <div id="loadingResult" class="loading hidden">⏳ Running actuarial assessment...</div>
        </div>
    </div>

    <div class="footer"><p>Vettify PreCheck · Gompertz-Makeham Actuarial Model · Calibrated to South African Mortality Tables</p><p style="margin-top: 8px;">Independent pre-underwriting intelligence — not a binding offer</p></div>

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
            if (!email) { showError('Please enter your email address'); return; }
            const btn = document.getElementById('calculateBtn');
            btn.disabled = true;
            btn.textContent = 'Analyzing...';
            document.getElementById('loadingResult').classList.remove('hidden');
            document.getElementById('freeResult').classList.add('hidden');
            const termYears = termPreset.value === 'custom' ? parseInt(termCustom.value) : parseInt(termPreset.value);
            const coverageAmount = coveragePreset.value === 'custom' ? parseInt(coverageCustom.value) : parseInt(coveragePreset.value);
            const age = parseInt(document.getElementById('age').value);
            if (age < 18 || age > 80) { showError('Age must be between 18 and 80'); resetButton(btn); return; }
            const formData = { age: age, gender: document.getElementById('gender').value, smoker: document.querySelector('input[name="smoker"]:checked').value === 'yes', income: parseInt(document.getElementById('income').value), coverage: coverageAmount, term: termYears, email: email };
            currentFormData = formData;
            try {
                const res = await fetch('/calculate', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(formData) });
                const data = await res.json();
                const riskColor = data.risk.score >= 70 ? '#16a34a' : (data.risk.score >= 40 ? '#ea580c' : '#dc2626');
                document.getElementById('riskScore').innerHTML = data.risk.score;
                document.getElementById('riskScore').style.color = riskColor;
                document.getElementById('riskExplanation').innerHTML = data.underwriting.risk_explanation;
                let driversHtml = '';
                for (let d of data.risk.drivers) { driversHtml += `<div class="driver-item"><span>${d.factor}</span><span class="${d.impact < 0 ? 'driver-impact-neg' : (d.impact > 0 ? 'driver-impact-pos' : '')}">${d.impact > 0 ? '+' : ''}${d.impact}</span></div><div style="font-size: 11px; color: #5b6e8c; margin-top: -6px; margin-bottom: 12px;">${d.explanation}</div>`; }
                document.getElementById('driversContainer').innerHTML = driversHtml;
                document.getElementById('premiumText').innerHTML = `<div class="premium-box"><span class="premium-amount">R${data.premium} - R${Math.round(data.premium * 1.12)}</span><br><small>per month</small></div>`;
                document.getElementById('confidenceRange').innerHTML = `Confidence interval: ±12% (R${data.underwriting.confidence_range.low} – R${data.underwriting.confidence_range.high})`;
                document.getElementById('insurerText').innerHTML = data.insurers.join(' • ');
                document.getElementById('insurerNote').innerHTML = data.insurer_note;
                document.getElementById('freeResult').classList.remove('hidden');
                btn.disabled = false;
                btn.textContent = 'Generate Underwriting Assessment →';
                document.getElementById('loadingResult').classList.add('hidden');
            } catch(err) { showError('Error analyzing risk profile'); resetButton(btn); }
            function showError(msg) { const errDiv = document.getElementById('error'); errDiv.textContent = msg; errDiv.style.display = 'block'; setTimeout(() => errDiv.style.display = 'none', 4000); }
            function resetButton(btn) { btn.disabled = false; btn.textContent = 'Generate Underwriting Assessment →'; document.getElementById('loadingResult').classList.add('hidden'); }
        });
        
        document.getElementById('payBtn').addEventListener('click', async () => {
            if (!currentFormData) { alert('Please complete an assessment first'); return; }
            const btn = document.getElementById('payBtn');
            btn.textContent = 'Generating Report...';
            btn.disabled = true;
            try {
                const res = await fetch('/generate-report', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(currentFormData) });
                if (!res.ok) throw new Error('Failed');
                const blob = await res.blob();
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `vettify_intelligence_report.pdf`;
                a.click();
                URL.revokeObjectURL(url);
                alert('✅ Intelligence report downloaded successfully');
            } catch(err) { alert('Error generating report: ' + err.message); }
            btn.textContent = 'Download Intelligence Report →';
            btn.disabled = false;
        });
    </script>
</body>
</html>
    ''')

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=5000)
