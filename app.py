from flask import Flask, request, jsonify, send_file, render_template_string
from flask_cors import CORS
import io
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from datetime import datetime, timedelta
import json
import os
import uuid
import math
import re
import sqlite3
from functools import wraps, lru_cache

app = Flask(__name__)
app.secret_key = os.urandom(24).hex()
CORS(app)

# ============================================
# Database setup
# ============================================

DATABASE = 'vettify.db'

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS usage (
            email TEXT PRIMARY KEY,
            count INTEGER DEFAULT 0,
            paid BOOLEAN DEFAULT 0,
            first_use TEXT
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS leads (
            id TEXT PRIMARY KEY,
            email TEXT,
            age INTEGER,
            gender TEXT,
            smoker BOOLEAN,
            income REAL,
            coverage REAL,
            term INTEGER,
            premium REAL,
            risk_score INTEGER,
            timestamp TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# ============================================
# Actuarial Core
# ============================================

GOMPERTZ_A = 0.00022
GOMPERTZ_B = 0.000027
GOMPERTZ_C = 0.092

def force_of_mortality(age: int) -> float:
    return GOMPERTZ_A + GOMPERTZ_B * math.exp(GOMPERTZ_C * age)

def smoker_multiplier(age: int) -> float:
    if age < 30: return 2.5
    elif age < 40: return 2.2
    elif age < 50: return 1.9
    elif age < 60: return 1.6
    else: return 1.4

@lru_cache(maxsize=10000)
def get_monthly_mortality(age: int, smoker: bool) -> float:
    mu = force_of_mortality(age)
    if smoker:
        mu *= smoker_multiplier(age)
    return 1 - math.exp(-mu / 12)

def calculate_epv_benefit(coverage: float, age: int, term_years: int, smoker: bool) -> float:
    v = 1 / (1 + 0.06 / 12)
    epv = 0.0
    survival = 1.0
    
    for month in range(1, term_years * 12 + 1):
        current_age = age + (month - 1) // 12
        q = get_monthly_mortality(current_age, smoker)
        prob_death = survival * q
        epv += (v ** month) * prob_death * coverage
        survival *= (1 - q)
    
    return epv

def calculate_epv_premiums(age: int, term_years: int, smoker: bool) -> float:
    v = 1 / (1 + 0.06 / 12)
    epv = 0.0
    survival = 1.0
    
    for month in range(1, term_years * 12 + 1):
        current_age = age + (month - 1) // 12
        q = get_monthly_mortality(current_age, smoker)
        epv += (v ** (month - 1)) * survival
        survival *= (1 - q)
    
    return epv

def calculate_premium(age: int, gender: str, smoker: bool, income: float, coverage: float, term_years: int) -> float:
    epv_benefit = calculate_epv_benefit(coverage, age, term_years, smoker)
    epv_premiums = calculate_epv_premiums(age, term_years, smoker)
    
    if epv_premiums <= 0:
        premium = coverage / (term_years * 12)
    else:
        premium = epv_benefit / epv_premiums
    
    if gender == "male":
        premium *= 1.12
    
    ratio = coverage / income if income > 0 else 10
    if ratio > 4:
        premium *= 1 + min(0.6, (ratio - 4) * 0.1)
    
    premium = max(premium, 80.0)
    premium = min(premium, 15000.0)
    
    return round(premium)

def calculate_risk_score(age: int, smoker: bool) -> int:
    score = 70
    if smoker:
        score -= 30
    if age > 65:
        score -= 18
    elif age > 55:
        score -= 12
    elif age > 45:
        score -= 6
    elif age < 30:
        score += 5
    return max(10, min(95, score))

# ============================================
# Database helpers
# ============================================

def get_usage(email: str):
    conn = get_db()
    result = conn.execute('SELECT count, paid FROM usage WHERE email = ?', (email,)).fetchone()
    conn.close()
    if result:
        return {'count': result['count'], 'paid': bool(result['paid'])}
    return {'count': 0, 'paid': False}

def increment_usage(email: str):
    conn = get_db()
    current = get_usage(email)
    if current['count'] == 0:
        conn.execute('INSERT INTO usage (email, count, paid, first_use) VALUES (?, ?, ?, ?)',
                     (email, 1, 0, datetime.now().isoformat()))
    else:
        conn.execute('UPDATE usage SET count = ? WHERE email = ?', (current['count'] + 1, email))
    conn.commit()
    conn.close()

# ============================================
# PDF Generation
# ============================================

def generate_pdf(data: dict, premium: float, risk_score: int, risk_level: str):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    story = []
    
    vettify_blue = colors.HexColor('#0a2540')
    
    # Header
    story.append(Paragraph("VETTIFY PRECHECK", ParagraphStyle('Title', parent=styles['Heading1'], fontSize=28, textColor=vettify_blue, alignment=1)))
    story.append(Spacer(1, 0.3*inch))
    
    # Report ID and validity
    report_id = str(uuid.uuid4())[:8]
    valid_until = (datetime.now() + timedelta(days=7)).strftime('%d %B %Y')
    story.append(Paragraph(f"Report ID: {report_id}", styles['Normal']))
    story.append(Paragraph(f"Valid Until: {valid_until}", styles['Normal']))
    story.append(Paragraph(f"Generated: {datetime.now().strftime('%d %B %Y')}", styles['Normal']))
    story.append(Spacer(1, 0.2*inch))
    
    # Risk Score
    story.append(Paragraph("RISK SCORE", styles['Heading2']))
    risk_color = "#16a34a" if risk_level == "Low" else "#ea580c" if risk_level == "Moderate" else "#dc2626"
    story.append(Paragraph(f"{risk_score}/100", ParagraphStyle('Score', parent=styles['Normal'], fontSize=48, textColor=colors.HexColor(risk_color), alignment=1)))
    story.append(Spacer(1, 0.2*inch))
    
    # Client Profile
    story.append(Paragraph("CLIENT PROFILE", styles['Heading2']))
    info = [
        ["Age", f"{data['age']} years"],
        ["Gender", data['gender'].capitalize()],
        ["Smoker", "Yes" if data['smoker'] else "No"],
        ["Annual Income", f"R{data['income']:,.0f}"],
        ["Coverage", f"R{data['coverage']:,.0f}"],
        ["Term", f"{data['term']} years"],
        ["Monthly Premium", f"R{premium:,.0f}"],
    ]
    t = Table(info, colWidths=[1.5*inch, 3*inch])
    t.setStyle(TableStyle([('FONTNAME', (0,0), (-1,-1), 'Helvetica'), ('FONTSIZE', (0,0), (-1,-1), 10)]))
    story.append(t)
    story.append(Spacer(1, 0.2*inch))
    
    # What You Get
    story.append(Paragraph("WHAT YOU GET", styles['Heading2']))
    features = [
        "• Risk Score (0-100) with classification",
        "• Monthly premium estimate with confidence range",
        "• Actuarial methodology explanation",
        "• Valid for 7 days",
        "• Professional PDF report",
        "• Insurer matching recommendations"
    ]
    for f in features:
        story.append(Paragraph(f, styles['Normal']))
        story.append(Spacer(1, 0.05*inch))
    story.append(Spacer(1, 0.2*inch))
    
    # Methodology
    story.append(Paragraph("METHODOLOGY", styles['Heading2']))
    story.append(Paragraph("Gompertz-Makeham mortality model with EPV (Expected Present Value) calculation, monthly step consistent, 6% discount rate.", styles['Normal']))
    story.append(Spacer(1, 0.2*inch))
    
    # Disclaimer
    story.append(Paragraph("DISCLAIMER", styles['Heading2']))
    story.append(Paragraph("Pre-screening only. Not a binding quote. Valid for 7 days.", ParagraphStyle('Disclaimer', parent=styles['Normal'], fontSize=7, textColor=colors.grey)))
    
    doc.build(story)
    buffer.seek(0)
    return buffer

# ============================================
# Routes
# ============================================

@app.route('/')
def home():
    return render_template_string('''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Vettify PreCheck | Actuarial Underwriting Intelligence</title>
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
        .main-container { max-width: 1280px; margin: -40px auto 48px; padding: 0 32px; display: grid; grid-template-columns: 1fr 0.8fr; gap: 32px; }
        .form-card { background: white; border-radius: 28px; box-shadow: 0 8px 30px rgba(0,0,0,0.1); overflow: hidden; }
        .form-header { padding: 28px 32px; border-bottom: 1px solid #eef2f6; }
        .form-header h2 { font-size: 22px; font-weight: 700; color: #0a2540; }
        .form-body { padding: 32px; }
        .form-group { margin-bottom: 24px; }
        label { display: block; font-weight: 600; margin-bottom: 8px; color: #1a2c3e; font-size: 13px; text-transform: uppercase; }
        input, select { width: 100%; padding: 14px 16px; border: 1.5px solid #e2e8f0; border-radius: 14px; font-size: 15px; font-family: 'Inter', sans-serif; }
        input:focus, select:focus { outline: none; border-color: #0a2540; }
        .radio-group { display: flex; gap: 32px; margin-top: 8px; }
        .radio-group label { display: flex; align-items: center; font-weight: 500; text-transform: none; gap: 10px; cursor: pointer; }
        .row-group { display: flex; gap: 16px; }
        .row-group .form-group { flex: 1; }
        .inline-group { display: flex; gap: 12px; }
        .inline-group select { flex: 2; }
        .inline-group input { flex: 1; }
        .btn-primary { width: 100%; padding: 16px; background: linear-gradient(135deg, #0a2540 0%, #1b4d3e 100%); color: white; border: none; border-radius: 16px; font-size: 16px; font-weight: 700; cursor: pointer; margin-top: 16px; }
        .btn-primary:disabled { opacity: 0.6; cursor: not-allowed; }
        .result-card { background: white; border-radius: 28px; box-shadow: 0 8px 30px rgba(0,0,0,0.1); padding: 32px; position: sticky; top: 100px; }
        .result-score { text-align: center; padding: 24px; background: #f8fafc; border-radius: 20px; margin-bottom: 24px; }
        .score-number { font-size: 64px; font-weight: 800; line-height: 1; }
        .premium-box { background: #f0fdf4; padding: 16px; border-radius: 16px; text-align: center; }
        .premium-amount { font-size: 28px; font-weight: 800; color: #16a34a; }
        .result-section { margin-bottom: 20px; }
        .result-section h4 { font-size: 14px; font-weight: 700; color: #0a2540; margin-bottom: 8px; text-transform: uppercase; letter-spacing: 0.5px; }
        .features-list { background: #f8fafc; border-radius: 16px; padding: 20px; margin: 20px 0; }
        .features-list li { margin-left: 20px; margin-bottom: 8px; color: #1a2c3e; font-size: 13px; }
        .paywall { background: #fef3c7; border-radius: 20px; padding: 24px; text-align: center; margin-top: 24px; }
        .paywall h3 { font-size: 18px; font-weight: 700; color: #92400e; margin-bottom: 12px; }
        .paywall-price { font-size: 32px; font-weight: 800; color: #0a2540; margin: 16px 0; }
        .btn-pay { width: 100%; padding: 14px; background: #0070ba; color: white; border: none; border-radius: 12px; font-weight: 700; font-size: 16px; cursor: pointer; margin-top: 12px; }
        .btn-pay:hover { background: #003087; }
        .hidden { display: none; }
        .loading { text-align: center; padding: 40px; }
        .error { color: #dc2626; padding: 12px; background: #fee2e2; border-radius: 12px; margin-top: 16px; display: none; }
        .remaining-badge { background: #e8f0fe; padding: 8px 16px; border-radius: 30px; font-size: 12px; margin-bottom: 16px; text-align: center; }
        .footer { text-align: center; padding: 48px 32px; color: #8a9bb0; border-top: 1px solid #e2e8f0; margin-top: 48px; }
        @media (max-width: 900px) { .main-container { grid-template-columns: 1fr; } .hero h1 { font-size: 32px; } }
    </style>
</head>
<body>
    <nav class="navbar">
        <div class="nav-container">
            <a href="/" class="logo">VETTIFY <span>PreCheck</span></a>
            <button class="btn-outline" onclick="alert('Contact: hello@vettifyprecheck.com\\nR1,999/month for broker access')">For Brokers →</button>
        </div>
    </nav>
    
    <div class="hero">
        <div class="hero-badge">⚡ Gompertz-Makeham Actuarial Model</div>
        <h1>Know before you apply</h1>
        <p>First 5 reports free • EPV-based pricing • Professional PDF reports</p>
    </div>
    
    <div class="main-container">
        <div class="form-card">
            <div class="form-header"><h2>Client Assessment</h2></div>
            <div class="form-body">
                <form id="assessmentForm">
                    <div class="row-group">
                        <div class="form-group"><label>Age</label><input type="number" id="age" required min="18" max="80" placeholder="35"></div>
                        <div class="form-group"><label>Gender</label><select id="gender"><option value="male">Male</option><option value="female">Female</option></select></div>
                    </div>
                    <div class="form-group"><label>Smoker</label><div class="radio-group"><label><input type="radio" name="smoker" value="yes"> Yes</label><label><input type="radio" name="smoker" value="no" checked> No</label></div></div>
                    <div class="form-group"><label>Annual Income (ZAR)</label><input type="number" id="income" required placeholder="500000"></div>
                    <div class="form-group"><label>Coverage Amount (ZAR)</label><div class="inline-group"><select id="coverage_preset"><option value="1000000">R1,000,000</option><option value="2000000">R2,000,000</option><option value="3000000">R3,000,000</option><option value="5000000">R5,000,000</option><option value="10000000">R10,000,000</option><option value="custom">Custom</option></select><input type="number" id="coverage_custom" placeholder="Enter amount" style="display:none"></div></div>
                    <div class="form-group"><label>Term (Years)</label><div class="inline-group"><select id="term_preset"><option value="10">10</option><option value="15">15</option><option value="20" selected>20</option><option value="25">25</option><option value="30">30</option><option value="custom">Custom</option></select><input type="number" id="term_custom" placeholder="Enter years" style="display:none"></div></div>
                    <div class="form-group"><label>Your Email</label><input type="email" id="email" required placeholder="broker@example.com"><small>First 5 reports free</small></div>
                    <button type="submit" class="btn-primary" id="calculateBtn">Calculate Risk Score →</button>
                </form>
                <div class="error" id="error"></div>
            </div>
        </div>
        
        <div>
            <div class="result-card" id="resultCard">
                <div id="statusContainer"></div>
                <div id="freeResult">
                    <div class="result-score"><div class="score-number" id="riskScore">—</div><div class="score-label">Risk Score (0-100)</div></div>
                    <div class="result-section"><h4>Risk Classification</h4><div id="riskLabel">Complete the form to see results</div></div>
                    <div class="result-section"><h4>Monthly Premium Estimate</h4><div id="premiumText">—</div></div>
                    
                    <div class="features-list">
                        <h4 style="margin-bottom: 12px;">📄 Full Report Includes:</h4>
                        <ul>
                            <li>Risk Score (0-100) with classification</li>
                            <li>Monthly premium estimate with confidence range</li>
                            <li>Actuarial methodology explanation</li>
                            <li>Valid for 7 days</li>
                            <li>Professional PDF report ready for clients</li>
                            <li>Insurer matching recommendations</li>
                        </ul>
                    </div>
                    
                    <div class="paywall" id="paywall">
                        <h3>🔓 Unlock Full Actuarial Report</h3>
                        <p>Get the complete professional PDF report</p>
                        <div class="paywall-price">R49</div>
                        <button class="btn-pay" id="payBtn">Unlock Full Report →</button>
                        <p style="font-size: 11px; margin-top: 12px;">One-time payment · Instant download</p>
                    </div>
                </div>
                <div id="loadingResult" class="loading hidden">⏳ Calculating...</div>
            </div>
        </div>
    </div>
    
    <div class="footer"><p>Vettify PreCheck · Gompertz-Makeham Actuarial Model · First 5 reports free</p></div>
    
    <script>
        let currentFormData = null;
        let userEmail = localStorage.getItem('vettify_email');
        let remainingFree = 5;
        
        async function checkStatus() {
            if (!userEmail) return;
            try {
                const response = await fetch(`/usage?email=${encodeURIComponent(userEmail)}`);
                const data = await response.json();
                const remaining = 5 - (data.count || 0);
                if (data.paid) {
                    document.getElementById('statusContainer').innerHTML = '<div class="remaining-badge" style="background:#16a34a; color:white;">✓ Premium Access - Unlimited Reports</div>';
                    document.getElementById('paywall').style.display = 'none';
                } else {
                    document.getElementById('statusContainer').innerHTML = `<div class="remaining-badge">✨ ${remaining} free reports remaining (first 5 free)</div>`;
                    if (remaining <= 0) {
                        document.getElementById('paywall').style.display = 'block';
                    } else {
                        document.getElementById('paywall').style.display = 'block';
                    }
                }
            } catch(e) { console.log(e); }
        }
        
        // Handle custom inputs
        const coveragePreset = document.getElementById('coverage_preset');
        const coverageCustom = document.getElementById('coverage_custom');
        const termPreset = document.getElementById('term_preset');
        const termCustom = document.getElementById('term_custom');
        
        coveragePreset.addEventListener('change', function() {
            coverageCustom.style.display = this.value === 'custom' ? 'block' : 'none';
        });
        termPreset.addEventListener('change', function() {
            termCustom.style.display = this.value === 'custom' ? 'block' : 'none';
        });
        
        document.getElementById('assessmentForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            
            const emailInput = document.getElementById('email').value.trim();
            if (!emailInput) {
                document.getElementById('error').textContent = 'Please enter your email';
                document.getElementById('error').style.display = 'block';
                return;
            }
            
            if (!userEmail) {
                userEmail = emailInput;
                localStorage.setItem('vettify_email', userEmail);
                checkStatus();
            }
            
            const calculateBtn = document.getElementById('calculateBtn');
            const loadingDiv = document.getElementById('loadingResult');
            const resultDiv = document.getElementById('freeResult');
            const errorDiv = document.getElementById('error');
            
            calculateBtn.disabled = true;
            calculateBtn.textContent = 'Calculating...';
            loadingDiv.classList.remove('hidden');
            resultDiv.classList.add('hidden');
            errorDiv.style.display = 'none';
            
            const termYears = termPreset.value === 'custom' ? parseInt(termCustom.value) : parseInt(termPreset.value);
            const coverageAmount = coveragePreset.value === 'custom' ? parseInt(coverageCustom.value) : parseInt(coveragePreset.value);
            const age = parseInt(document.getElementById('age').value);
            const income = parseInt(document.getElementById('income').value);
            
            if (age < 18 || age > 80) {
                errorDiv.textContent = 'Age must be between 18 and 80';
                errorDiv.style.display = 'block';
                calculateBtn.disabled = false;
                calculateBtn.textContent = 'Calculate Risk Score →';
                loadingDiv.classList.add('hidden');
                return;
            }
            
            const formData = {
                age: age,
                gender: document.getElementById('gender').value,
                smoker: document.querySelector('input[name="smoker"]:checked').value === 'yes',
                income_band: income,
                coverage_amount: coverageAmount,
                term_years: termYears,
                email: userEmail
            };
            currentFormData = formData;
            
            try {
                const response = await fetch('/calculate', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(formData)
                });
                const result = await response.json();
                
                document.getElementById('riskScore').innerHTML = result.risk_score;
                let riskColor = result.risk_score >= 70 ? '#16a34a' : (result.risk_score >= 40 ? '#ea580c' : '#dc2626');
                let riskText = result.risk_score >= 70 ? 'Low Risk' : (result.risk_score >= 40 ? 'Moderate Risk' : 'High Risk');
                document.getElementById('riskLabel').innerHTML = `<span style="color: ${riskColor}; font-weight: 700;">${riskText}</span><br><small>Based on age + smoker status</small>`;
                document.getElementById('premiumText').innerHTML = `<div class="premium-box"><span class="premium-amount">R${result.premium} - R${result.premium + Math.floor(result.premium*0.15)}</span><br><small>per month</small></div>`;
                
                loadingDiv.classList.add('hidden');
                resultDiv.classList.remove('hidden');
                calculateBtn.disabled = false;
                calculateBtn.textContent = 'Calculate Risk Score →';
                
            } catch(err) {
                errorDiv.textContent = 'Error calculating. Please try again.';
                errorDiv.style.display = 'block';
                calculateBtn.disabled = false;
                calculateBtn.textContent = 'Calculate Risk Score →';
                loadingDiv.classList.add('hidden');
            }
        });
        
        document.getElementById('payBtn').addEventListener('click', async () => {
            if (!currentFormData) {
                alert('Please calculate a risk score first');
                return;
            }
            
            const email = currentFormData.email;
            if (!email) {
                alert('Please enter your email');
                return;
            }
            
            const btn = document.getElementById('payBtn');
            btn.textContent = 'Generating...';
            btn.disabled = true;
            
            try {
                const response = await fetch('/generate-report', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(currentFormData)
                });
                
                if (!response.ok) {
                    const error = await response.json();
                    throw new Error(error.error || 'Failed to generate');
                }
                
                const blob = await response.blob();
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `vettify_report_${currentFormData.age}.pdf`;
                document.body.appendChild(a);
                a.click();
                window.URL.revokeObjectURL(url);
                a.remove();
                
                alert('✅ Report downloaded! Check your downloads folder.');
                btn.textContent = 'Unlock Full Report →';
                btn.disabled = false;
                
            } catch(err) {
                alert('Error: ' + err.message);
                btn.textContent = 'Unlock Full Report →';
                btn.disabled = false;
            }
        });
        
        checkStatus();
    </script>
</body>
</html>
    ''')

@app.route('/calculate', methods=['POST'])
def calculate():
    data = request.json
    email = data.get('email')
    
    # Check free limit (5 reports)
    usage = get_usage(email)
    if not usage['paid'] and usage['count'] >= 5:
        return jsonify({'error': 'Free limit reached. Please purchase the full report.'}), 403
    
    # Calculate
    premium = calculate_premium(
        data['age'], data['gender'], data['smoker'],
        data['income_band'], data['coverage_amount'], data['term_years']
    )
    risk_score = calculate_risk_score(data['age'], data['smoker'])
    
    # Increment usage (only if not paid)
    if not usage['paid']:
        increment_usage(email)
    
    return jsonify({
        'premium': premium,
        'risk_score': risk_score
    })

@app.route('/generate-report', methods=['POST'])
def generate_report():
    data = request.json
    email = data.get('email')
    
    # Check free limit (5 reports)
    usage = get_usage(email)
    if not usage['paid'] and usage['count'] >= 5:
        return jsonify({'error': 'Free limit reached. Please purchase the full report.'}), 403
    
    # Calculate
    premium = calculate_premium(
        data['age'], data['gender'], data['smoker'],
        data['income_band'], data['coverage_amount'], data['term_years']
    )
    risk_score = calculate_risk_score(data['age'], data['smoker'])
    risk_level = "Low" if risk_score >= 70 else "Moderate" if risk_score >= 40 else "High"
    
    # Generate PDF
    pdf_buffer = generate_pdf({
        'age': data['age'],
        'gender': data['gender'],
        'smoker': data['smoker'],
        'income': data['income_band'],
        'coverage': data['coverage_amount'],
        'term': data['term_years']
    }, premium, risk_score, risk_level)
    
    # Save lead
    conn = get_db()
    lead_id = str(uuid.uuid4())
    conn.execute('INSERT OR REPLACE INTO leads (id, email, age, gender, smoker, income, coverage, term, premium, risk_score, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                 (lead_id, email, data['age'], data['gender'], 1 if data['smoker'] else 0,
                  data['income_band'], data['coverage_amount'], data['term_years'], premium, risk_score, datetime.now().isoformat()))
    conn.commit()
    conn.close()
    
    # Increment usage
    if not usage['paid']:
        increment_usage(email)
    
    return send_file(pdf_buffer, mimetype='application/pdf', as_attachment=True, download_name=f'vettify_report_{data["age"]}.pdf')

@app.route('/usage', methods=['GET'])
def usage():
    email = request.args.get('email')
    usage = get_usage(email)
    return jsonify({'count': usage['count'], 'paid': usage['paid']})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)
