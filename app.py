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
import json

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
    conn.execute("""CREATE TABLE IF NOT EXISTS applications (
        id TEXT PRIMARY KEY,
        full_name TEXT,
        email TEXT,
        linkedin_url TEXT,
        visibility_level TEXT,
        risk_description TEXT,
        status TEXT DEFAULT 'pending',
        submitted_at TEXT
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

def risk_score(age, smoker, coverage, income, term):
    score = 70
    drivers = []
    if smoker:
        score -= 30
        drivers.append({"factor": "Tobacco Use", "impact": -30, "explanation": "Increases mortality risk by approximately 2x-2.5x"})
    if age > 55:
        score -= 12
        drivers.append({"factor": f"Age {age}", "impact": -12, "explanation": "Advanced age increases baseline mortality"})
    elif age < 30:
        score += 5
        drivers.append({"factor": f"Age {age}", "impact": 5, "explanation": "Young age provides favourable mortality"})
    ratio = coverage / income if income else 0
    if ratio > 8:
        score -= 15
        drivers.append({"factor": "High Coverage/Income", "impact": -15, "explanation": f"Coverage is {ratio:.1f}x income — exceeds guidelines"})
    elif ratio > 6:
        score -= 10
        drivers.append({"factor": "Elevated Coverage/Income", "impact": -10, "explanation": f"Coverage is {ratio:.1f}x income — may trigger review"})
    if term > 25:
        score -= 5
        drivers.append({"factor": "Extended Term", "impact": -5, "explanation": "Term >25 years adds long-term uncertainty"})
    score = max(10, min(95, score))
    level = "Low" if score >= 70 else "Moderate" if score >= 40 else "High"
    return {"score": score, "level": level, "drivers": drivers}

# ================= LUXURY ROUTES =================
@app.route('/')
def home():
    return render_template_string('''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Vettify | Private Reputation Intelligence</title>
    <link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@300;400;500;600;700&family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --gold: #c9a03d;
            --gold-light: #e8d5a3;
            --dark: #0a1628;
            --charcoal: #1a2a3a;
            --cream: #faf8f5;
            --paper: #f5f2eb;
        }
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Inter', sans-serif; background: var(--cream); color: var(--dark); line-height: 1.5; }
        
        /* Luxury Elements */
        .container { max-width: 1280px; margin: 0 auto; padding: 0 48px; }
        .gold-text { color: var(--gold); }
        .gold-border { border-bottom: 2px solid var(--gold); display: inline-block; padding-bottom: 4px; }
        
        /* Navigation */
        .navbar { padding: 32px 0; border-bottom: 1px solid rgba(0,0,0,0.05); }
        .navbar .container { display: flex; justify-content: space-between; align-items: center; }
        .logo { font-family: 'Cormorant Garamond', serif; font-size: 28px; font-weight: 600; letter-spacing: 2px; color: var(--dark); text-decoration: none; }
        .logo span { font-weight: 300; color: var(--gold); }
        .nav-links { display: flex; gap: 48px; align-items: center; }
        .nav-links a { text-decoration: none; color: var(--dark); font-size: 13px; letter-spacing: 1px; text-transform: uppercase; font-weight: 500; }
        .badge { background: var(--gold-light); color: var(--dark); padding: 4px 12px; border-radius: 30px; font-size: 10px; letter-spacing: 1px; }
        
        /* Hero */
        .hero { padding: 120px 0 80px 0; text-align: center; background: linear-gradient(135deg, #faf8f5 0%, #f5f2eb 100%); }
        .hero-badge { display: inline-block; color: var(--gold); font-size: 11px; letter-spacing: 3px; text-transform: uppercase; margin-bottom: 24px; }
        .hero h1 { font-family: 'Cormorant Garamond', serif; font-size: 64px; font-weight: 500; line-height: 1.2; max-width: 800px; margin: 0 auto 24px; letter-spacing: -0.5px; }
        .hero p { font-size: 18px; color: #4a5a6a; max-width: 600px; margin: 0 auto 32px; font-weight: 300; }
        .btn-primary { background: var(--dark); color: white; border: none; padding: 16px 40px; font-size: 14px; letter-spacing: 2px; text-transform: uppercase; font-weight: 500; cursor: pointer; transition: all 0.3s; border-radius: 0; }
        .btn-primary:hover { background: var(--gold); color: var(--dark); }
        .btn-outline { background: transparent; border: 1px solid var(--dark); color: var(--dark); padding: 14px 36px; font-size: 13px; letter-spacing: 2px; text-transform: uppercase; cursor: pointer; transition: all 0.3s; margin-left: 16px; border-radius: 0; }
        .trust-strip { margin-top: 64px; display: flex; justify-content: center; gap: 48px; flex-wrap: wrap; }
        .trust-strip span { font-size: 11px; text-transform: uppercase; letter-spacing: 2px; color: #8a9bb0; }
        
        /* Problem Section */
        .problem { background: var(--paper); padding: 100px 0; text-align: center; }
        .problem h2 { font-family: 'Cormorant Garamond', serif; font-size: 42px; font-weight: 500; margin-bottom: 40px; }
        .problem p { max-width: 700px; margin: 0 auto; font-size: 18px; color: #4a5a6a; line-height: 1.7; }
        
        /* Pricing Cards */
        .pricing { padding: 100px 0; background: var(--cream); }
        .pricing h2 { text-align: center; font-family: 'Cormorant Garamond', serif; font-size: 42px; font-weight: 500; margin-bottom: 16px; }
        .pricing-sub { text-align: center; color: #8a9bb0; margin-bottom: 60px; font-size: 14px; letter-spacing: 1px; }
        .pricing-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 24px; }
        .pricing-card { background: white; padding: 40px 28px; border: 1px solid #e2e8f0; transition: all 0.3s; }
        .pricing-card:hover { transform: translateY(-4px); box-shadow: 0 20px 40px rgba(0,0,0,0.08); border-color: var(--gold); }
        .pricing-tier { font-size: 11px; letter-spacing: 2px; text-transform: uppercase; color: var(--gold); margin-bottom: 16px; }
        .pricing-price { font-family: 'Cormorant Garamond', serif; font-size: 36px; font-weight: 600; margin-bottom: 24px; }
        .pricing-price small { font-size: 12px; font-weight: 300; color: #8a9bb0; }
        .pricing-features { list-style: none; margin-bottom: 32px; }
        .pricing-features li { padding: 8px 0; font-size: 13px; color: #4a5a6a; border-bottom: 1px solid #f0f0f0; }
        .btn-card { width: 100%; background: transparent; border: 1px solid var(--dark); padding: 12px; font-size: 11px; letter-spacing: 2px; text-transform: uppercase; cursor: pointer; transition: all 0.3s; }
        .btn-card:hover { background: var(--dark); color: white; }
        .card-premium { border-top: 3px solid var(--gold); background: linear-gradient(135deg, white 0%, #fefcf8 100%); }
        
        /* CTA */
        .cta { background: var(--dark); color: white; padding: 80px 0; text-align: center; }
        .cta h2 { font-family: 'Cormorant Garamond', serif; font-size: 42px; font-weight: 500; margin-bottom: 16px; }
        .cta p { color: #8a9bb0; margin-bottom: 32px; }
        .btn-cta { background: var(--gold); color: var(--dark); border: none; padding: 16px 48px; font-size: 13px; letter-spacing: 2px; text-transform: uppercase; font-weight: 600; cursor: pointer; }
        
        /* Footer */
        .footer { padding: 48px 0; text-align: center; border-top: 1px solid #e2e8f0; color: #8a9bb0; font-size: 11px; letter-spacing: 1px; }
        
        @media (max-width: 900px) { .container { padding: 0 24px; } .hero h1 { font-size: 42px; } .pricing-grid { grid-template-columns: 1fr; max-width: 400px; margin: 0 auto; } .trust-strip { gap: 24px; } }
    </style>
</head>
<body>
    <nav class="navbar">
        <div class="container">
            <a href="/" class="logo">VETTIFY <span>INTELLIGENCE</span></a>
            <div class="nav-links">
                <span class="badge">Private Client Access Only</span>
            </div>
        </div>
    </nav>

    <section class="hero">
        <div class="container">
            <div class="hero-badge">PERCEPTION INTELLIGENCE</div>
            <h1>Know exactly how you'll be perceived — before the world does.</h1>
            <p>Vettify is a private intelligence system for founders, executives, and public-facing individuals who cannot afford to be misjudged.</p>
            <div>
                <button class="btn-primary" onclick="openApplication()">Request Private Access</button>
                <button class="btn-outline" onclick="showSample()">View Sample Report</button>
            </div>
            <div class="trust-strip">
                <span>PRIVATE CLIENT ONBOARDING ONLY</span>
                <span>LIMITED TO 20 ACTIVE CLIENTS</span>
                <span>USED BY FOUNDERS & EXECUTIVES</span>
            </div>
        </div>
    </section>

    <section class="problem">
        <div class="container">
            <h2>One misstep in public perception costs more than money.</h2>
            <p>Most people only discover how they are perceived after it's too late. After a pitch fails. After a hiring rejection. After credibility is already questioned. Vettify exists to prevent that moment.</p>
        </div>
    </section>

    <section class="pricing">
        <div class="container">
            <h2>Private Intelligence Architecture</h2>
            <div class="pricing-sub">Applications reviewed manually</div>
            <div class="pricing-grid">
                <div class="pricing-card">
                    <div class="pricing-tier">PRIVATE REPORT</div>
                    <div class="pricing-price">R2,500</div>
                    <ul class="pricing-features">
                        <li>Single perception audit</li>
                        <li>Risk score & analysis</li>
                        <li>Strategic recommendations</li>
                        <li>One-time delivery</li>
                    </ul>
                    <button class="btn-card" onclick="openApplication()">Request Access</button>
                </div>
                <div class="pricing-card">
                    <div class="pricing-tier">PROFESSIONAL INTELLIGENCE</div>
                    <div class="pricing-price">R7,500<span style="font-size:12px;">/month</span></div>
                    <ul class="pricing-features">
                        <li>Monthly reputation audit</li>
                        <li>Profile optimisation advice</li>
                        <li>Competitor benchmarking</li>
                        <li>Risk alerts</li>
                    </ul>
                    <button class="btn-card" onclick="openApplication()">Request Access</button>
                </div>
                <div class="pricing-card card-premium">
                    <div class="pricing-tier">EXECUTIVE ADVISORY</div>
                    <div class="pricing-price">R45,000<span style="font-size:12px;">/month</span></div>
                    <ul class="pricing-features">
                        <li>Weekly reputation analysis</li>
                        <li>Crisis risk simulation</li>
                        <li>Human advisory layer</li>
                        <li>Priority response</li>
                    </ul>
                    <button class="btn-card" onclick="openApplication()">Request Access</button>
                </div>
                <div class="pricing-card card-premium">
                    <div class="pricing-tier">CONCIERGE INTELLIGENCE</div>
                    <div class="pricing-price">R120,000<span style="font-size:12px;">/month</span></div>
                    <ul class="pricing-features">
                        <li>Daily monitoring</li>
                        <li>Human + AI hybrid advisory</li>
                        <li>Direct access line</li>
                        <li>Bespoke strategy reports</li>
                    </ul>
                    <button class="btn-card" onclick="openApplication()">Request Access</button>
                </div>
            </div>
        </div>
    </section>

    <section class="cta">
        <div class="container">
            <h2>Applications are reviewed manually to ensure client fit.</h2>
            <p>Limited to 20 active clients</p>
            <button class="btn-cta" onclick="openApplication()">Request Private Access →</button>
        </div>
    </section>

    <footer class="footer">
        <div class="container">
            <p>VETTIFY INTELLIGENCE — PRIVATE PERCEPTION ADVISORY</p>
            <p style="margin-top: 12px;">Not a public tool. By application only.</p>
        </div>
    </footer>

    <script>
        function openApplication() {
            window.location.href = '/apply';
        }
        function showSample() {
            alert('Sample report available upon request. Please contact concierge@vettify.com');
        }
    </script>
</body>
</html>
    ''')

@app.route('/apply')
def apply():
    return render_template_string('''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Vettify | Private Client Application</title>
    <link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@300;400;500;600;700&family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Inter', sans-serif; background: #faf8f5; color: #0a1628; }
        .container { max-width: 800px; margin: 0 auto; padding: 60px 32px; }
        .logo { font-family: 'Cormorant Garamond', serif; font-size: 28px; font-weight: 600; text-align: center; margin-bottom: 48px; text-decoration: none; color: #0a1628; display: block; }
        .logo span { color: #c9a03d; }
        .form-card { background: white; padding: 48px; border: 1px solid #e2e8f0; }
        h1 { font-family: 'Cormorant Garamond', serif; font-size: 32px; font-weight: 500; margin-bottom: 8px; }
        .sub { color: #8a9bb0; margin-bottom: 32px; font-size: 13px; }
        .form-group { margin-bottom: 24px; }
        label { display: block; font-size: 11px; letter-spacing: 1px; text-transform: uppercase; margin-bottom: 8px; font-weight: 600; }
        input, select, textarea { width: 100%; padding: 14px 16px; border: 1px solid #e2e8f0; font-size: 15px; background: white; font-family: 'Inter', sans-serif; }
        input:focus, select:focus, textarea:focus { outline: none; border-color: #c9a03d; }
        .btn-submit { width: 100%; background: #0a1628; color: white; border: none; padding: 16px; font-size: 13px; letter-spacing: 2px; text-transform: uppercase; font-weight: 500; cursor: pointer; margin-top: 16px; }
        .note { font-size: 11px; color: #8a9bb0; text-align: center; margin-top: 24px; }
        @media (max-width: 600px) { .container { padding: 32px 20px; } .form-card { padding: 28px; } }
    </style>
</head>
<body>
    <div class="container">
        <a href="/" class="logo">VETTIFY <span>INTELLIGENCE</span></a>
        <div class="form-card">
            <h1>Private Client Application</h1>
            <div class="sub">Applications are reviewed manually. Limited to 20 active clients.</div>
            <form id="applicationForm">
                <div class="form-group"><label>Full Name</label><input type="text" id="full_name" required></div>
                <div class="form-group"><label>Email Address</label><input type="email" id="email" required></div>
                <div class="form-group"><label>LinkedIn / Profile URL</label><input type="url" id="linkedin_url" placeholder="linkedin.com/in/..."></div>
                <div class="form-group"><label>Visibility Level</label><select id="visibility_level"><option value="low">Low (private individual)</option><option value="medium">Medium (professional / founder)</option><option value="high">High (public-facing executive)</option><option value="public">Public Figure / Media Frequent</option></select></div>
                <div class="form-group"><label>What is at stake if perception is wrong?</label><textarea id="risk_description" rows="3" placeholder="Please describe..."></textarea></div>
                <button type="submit" class="btn-submit">Submit Application →</button>
                <div class="note">Your application will be reviewed within 24 hours. Selected clients will receive onboarding details.</div>
            </form>
        </div>
    </div>
    <script>
        document.getElementById('applicationForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            const btn = e.target.querySelector('.btn-submit');
            btn.textContent = 'Submitting...';
            btn.disabled = true;
            const formData = {
                full_name: document.getElementById('full_name').value,
                email: document.getElementById('email').value,
                linkedin_url: document.getElementById('linkedin_url').value,
                visibility_level: document.getElementById('visibility_level').value,
                risk_description: document.getElementById('risk_description').value
            };
            try {
                const res = await fetch('/submit-application', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(formData) });
                if (res.ok) {
                    alert('Application received. We will review and respond within 24 hours.');
                    window.location.href = '/';
                } else {
                    alert('Error submitting application. Please try again.');
                }
            } catch(err) { alert('Error submitting'); }
            btn.textContent = 'Submit Application →';
            btn.disabled = false;
        });
    </script>
</body>
</html>
    ''')

@app.route('/submit-application', methods=['POST'])
def submit_application():
    data = request.json
    conn = get_db()
    app_id = str(uuid.uuid4())[:8]
    conn.execute('INSERT INTO applications (id, full_name, email, linkedin_url, visibility_level, risk_description, submitted_at) VALUES (?, ?, ?, ?, ?, ?, ?)',
                 (app_id, data['full_name'], data['email'], data['linkedin_url'], data['visibility_level'], data['risk_description'], datetime.now().isoformat()))
    conn.commit()
    conn.close()
    return jsonify({'status': 'received'})

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=5000)
