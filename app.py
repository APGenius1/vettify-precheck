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
        position TEXT,
        funding_amount TEXT,
        visibility_goal TEXT,
        status TEXT DEFAULT 'pending',
        submitted_at TEXT
    )""")
    conn.commit()
    conn.close()

init_db()

# ================= LUXURY INTELLIGENCE HOMEPAGE =================
@app.route('/')
def home():
    return render_template_string('''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Vettify | Private Perception Intelligence</title>
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
        
        .container { max-width: 1280px; margin: 0 auto; padding: 0 48px; }
        .gold-text { color: var(--gold); }
        
        .navbar { padding: 32px 0; border-bottom: 1px solid rgba(0,0,0,0.05); }
        .navbar .container { display: flex; justify-content: space-between; align-items: center; }
        .logo { font-family: 'Cormorant Garamond', serif; font-size: 28px; font-weight: 600; letter-spacing: 2px; color: var(--dark); text-decoration: none; }
        .logo span { font-weight: 300; color: var(--gold); }
        .badge { background: var(--gold-light); color: var(--dark); padding: 4px 12px; border-radius: 30px; font-size: 10px; letter-spacing: 1px; }
        
        /* Hero - Consequence-driven */
        .hero { padding: 100px 0 60px 0; text-align: center; background: linear-gradient(135deg, #faf8f5 0%, #f5f2eb 100%); }
        .hero-badge { display: inline-block; color: var(--gold); font-size: 11px; letter-spacing: 3px; text-transform: uppercase; margin-bottom: 24px; }
        .hero h1 { font-family: 'Cormorant Garamond', serif; font-size: 64px; font-weight: 500; line-height: 1.2; max-width: 900px; margin: 0 auto 24px; letter-spacing: -0.5px; }
        .hero p { font-size: 18px; color: #4a5a6a; max-width: 600px; margin: 0 auto 32px; font-weight: 300; }
        .btn-primary { background: var(--dark); color: white; border: none; padding: 16px 40px; font-size: 13px; letter-spacing: 2px; text-transform: uppercase; font-weight: 500; cursor: pointer; transition: all 0.3s; border-radius: 0; }
        .btn-primary:hover { background: var(--gold); color: var(--dark); }
        
        /* Intelligence Section - NOT a tool */
        .intelligence { padding: 100px 0; background: white; }
        .intelligence h2 { font-family: 'Cormorant Garamond', serif; font-size: 42px; font-weight: 500; text-align: center; margin-bottom: 60px; }
        .intelligence-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 48px; }
        .intel-card { text-align: center; padding: 0 20px; }
        .intel-icon { font-size: 40px; margin-bottom: 24px; }
        .intel-card h3 { font-family: 'Cormorant Garamond', serif; font-size: 22px; font-weight: 500; margin-bottom: 16px; }
        .intel-card p { color: #4a5a6a; font-size: 14px; line-height: 1.6; }
        
        /* Consequence Section - High stakes framing */
        .consequence { background: var(--dark); color: white; padding: 100px 0; text-align: center; }
        .consequence h2 { font-family: 'Cormorant Garamond', serif; font-size: 42px; font-weight: 500; margin-bottom: 32px; }
        .consequence p { max-width: 700px; margin: 0 auto; font-size: 18px; color: #8a9bb0; line-height: 1.8; }
        .consequence-highlight { color: var(--gold); font-weight: 600; }
        
        /* Pricing - Advisory tiers */
        .pricing { padding: 100px 0; background: var(--cream); }
        .pricing h2 { text-align: center; font-family: 'Cormorant Garamond', serif; font-size: 42px; font-weight: 500; margin-bottom: 16px; }
        .pricing-sub { text-align: center; color: #8a9bb0; margin-bottom: 60px; font-size: 13px; letter-spacing: 1px; }
        .pricing-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 24px; }
        .pricing-card { background: white; padding: 40px 28px; border: 1px solid #e2e8f0; transition: all 0.3s; }
        .pricing-card:hover { transform: translateY(-4px); box-shadow: 0 20px 30px rgba(0,0,0,0.05); border-color: var(--gold); }
        .pricing-tier { font-size: 10px; letter-spacing: 2px; text-transform: uppercase; color: var(--gold); margin-bottom: 16px; }
        .pricing-price { font-family: 'Cormorant Garamond', serif; font-size: 36px; font-weight: 600; margin-bottom: 24px; }
        .pricing-price small { font-size: 12px; font-weight: 300; color: #8a9bb0; }
        .pricing-features { list-style: none; margin-bottom: 32px; }
        .pricing-features li { padding: 10px 0; font-size: 13px; color: #4a5a6a; border-bottom: 1px solid #f0f0f0; }
        .btn-card { width: 100%; background: transparent; border: 1px solid var(--dark); padding: 12px; font-size: 11px; letter-spacing: 2px; text-transform: uppercase; cursor: pointer; transition: all 0.3s; }
        .btn-card:hover { background: var(--dark); color: white; }
        .card-premium { border-top: 3px solid var(--gold); background: linear-gradient(135deg, white 0%, #fefcf8 100%); }
        
        /* Authority Section */
        .authority { padding: 80px 0; background: white; text-align: center; }
        .authority h2 { font-family: 'Cormorant Garamond', serif; font-size: 32px; font-weight: 500; margin-bottom: 48px; }
        .authority-quote { max-width: 700px; margin: 0 auto 32px; font-size: 18px; font-style: italic; color: #4a5a6a; border-left: 3px solid var(--gold); padding-left: 24px; text-align: left; }
        
        /* CTA - Exclusivity */
        .cta { background: var(--dark); color: white; padding: 80px 0; text-align: center; }
        .cta h2 { font-family: 'Cormorant Garamond', serif; font-size: 42px; font-weight: 500; margin-bottom: 16px; }
        .cta p { color: #8a9bb0; margin-bottom: 32px; }
        .btn-cta { background: var(--gold); color: var(--dark); border: none; padding: 16px 48px; font-size: 13px; letter-spacing: 2px; text-transform: uppercase; font-weight: 600; cursor: pointer; }
        .scarcity { margin-top: 24px; font-size: 11px; color: #5b6e8c; }
        
        .footer { padding: 48px 0; text-align: center; border-top: 1px solid #e2e8f0; color: #8a9bb0; font-size: 11px; letter-spacing: 1px; }
        
        @media (max-width: 900px) { .container { padding: 0 24px; } .hero h1 { font-size: 42px; } .pricing-grid { grid-template-columns: 1fr; max-width: 400px; margin: 0 auto; } .intelligence-grid { grid-template-columns: 1fr; gap: 32px; } }
    </style>
</head>
<body>
    <nav class="navbar">
        <div class="container">
            <a href="/" class="logo">VETTIFY <span>INTELLIGENCE</span></a>
            <span class="badge">Private Advisory</span>
        </div>
    </nav>

    <section class="hero">
        <div class="container">
            <div class="hero-badge">PERCEPTION INTELLIGENCE</div>
            <h1>We assess how investors, media, and clients will perceive you — before they do.</h1>
            <p>Private perception advisory for founders, executives, and public figures. Intelligence, not software.</p>
            <button class="btn-primary" onclick="openApplication()">Request Intelligence Brief →</button>
        </div>
    </section>

    <section class="intelligence">
        <div class="container">
            <h2>What We Evaluate</h2>
            <div class="intelligence-grid">
                <div class="intel-card">
                    <div class="intel-icon">🎯</div>
                    <h3>Investor Perception</h3>
                    <p>How would a pitch partner interpret your positioning? We simulate investor judgment before you raise.</p>
                </div>
                <div class="intel-card">
                    <div class="intel-icon">📰</div>
                    <h3>Media Readiness</h3>
                    <p>Would media advisors feature or avoid you? We evaluate your public narrative against editorial standards.</p>
                </div>
                <div class="intel-card">
                    <div class="intel-icon">🏛️</div>
                    <h3>Reputation Risk</h3>
                    <p>What perception gaps could cost you partnerships or opportunities? We identify them before they surface.</p>
                </div>
            </div>
        </div>
    </section>

    <section class="consequence">
        <div class="container">
            <h2>A weak perception costs <span class="consequence-highlight">funding, opportunities, and trust</span> — long before you know it exists.</h2>
            <p>Most founders discover their reputation risk only after a pitch fails, a partnership falls through, or credibility is already questioned. Vettify exists to prevent that moment entirely.</p>
        </div>
    </section>

    <section class="pricing">
        <div class="container">
            <h2>Intelligence Advisory Tiers</h2>
            <div class="pricing-sub">Application-only · White-glove onboarding</div>
            <div class="pricing-grid">
                <div class="pricing-card">
                    <div class="pricing-tier">PERCEPTION AUDIT</div>
                    <div class="pricing-price">R3,500</div>
                    <ul class="pricing-features">
                        <li>Full reputation risk analysis</li>
                        <li>Investor perception score</li>
                        <li>Strategic recommendations</li>
                        <li>48-hour delivery</li>
                    </ul>
                    <button class="btn-card" onclick="openApplication()">Request Audit</button>
                </div>
                <div class="pricing-card">
                    <div class="pricing-tier">INTELLIGENCE ADVISORY</div>
                    <div class="pricing-price">R15,000<span style="font-size:12px;">/month</span></div>
                    <ul class="pricing-features">
                        <li>Monthly perception audit</li>
                        <li>Crisis risk simulation</li>
                        <li>Investor readiness tracking</li>
                        <li>Priority response (24h)</li>
                    </ul>
                    <button class="btn-card" onclick="openApplication()">Request Advisory</button>
                </div>
                <div class="pricing-card card-premium">
                    <div class="pricing-tier">EXECUTIVE INTELLIGENCE</div>
                    <div class="pricing-price">R45,000<span style="font-size:12px;">/month</span></div>
                    <ul class="pricing-features">
                        <li>Weekly perception analysis</li>
                        <li>Human advisory layer</li>
                        <li>Competitor benchmarking</li>
                        <li>Strategic roadmap</li>
                    </ul>
                    <button class="btn-card" onclick="openApplication()">Request Executive</button>
                </div>
                <div class="pricing-card card-premium">
                    <div class="pricing-tier">CONCIERGE INTELLIGENCE</div>
                    <div class="pricing-price">R95,000<span style="font-size:12px;">/month</span></div>
                    <ul class="pricing-features">
                        <li>Daily monitoring</li>
                        <li>Direct strategist access</li>
                        <li>Bespoke crisis preparation</li>
                        <li>White-glove advisory</li>
                    </ul>
                    <button class="btn-card" onclick="openApplication()">Request Concierge</button>
                </div>
            </div>
        </div>
    </section>

    <section class="authority">
        <div class="container">
            <h2>Who Trusts Our Intelligence</h2>
            <div class="authority-quote">
                "The perception audit changed how I positioned my company before a major raise. We secured funding within 60 days."
                <div style="margin-top: 12px; font-size: 12px; color: #c9a03d;">— FOUNDER, RAISED R25M</div>
            </div>
            <div class="authority-quote">
                "I had no idea how my LinkedIn profile was being interpreted. Vettify identified gaps I didn't know existed."
                <div style="margin-top: 12px; font-size: 12px; color: #c9a03d;">— EXECUTIVE, FORTUNE 500</div>
            </div>
        </div>
    </section>

    <section class="cta">
        <div class="container">
            <h2>Applications are reviewed manually to ensure client fit.</h2>
            <p>Currently accepting founding members. Limited capacity.</p>
            <button class="btn-cta" onclick="openApplication()">Request Intelligence Brief →</button>
            <div class="scarcity">3 of 20 client slots remain</div>
        </div>
    </section>

    <footer class="footer">
        <div class="container">
            <p>VETTIFY INTELLIGENCE — PRIVATE PERCEPTION ADVISORY</p>
            <p style="margin-top: 12px;">Not a tool. Not software. Intelligence interpreted for decision-makers.</p>
        </div>
    </footer>

    <script>
        function openApplication() { window.location.href = '/apply'; }
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
    <title>Vettify | Intelligence Application</title>
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
        label { display: block; font-size: 10px; letter-spacing: 1.5px; text-transform: uppercase; margin-bottom: 8px; font-weight: 600; }
        input, select, textarea { width: 100%; padding: 14px 16px; border: 1px solid #e2e8f0; font-size: 15px; background: white; font-family: 'Inter', sans-serif; border-radius: 0; }
        input:focus, select:focus, textarea:focus { outline: none; border-color: #c9a03d; }
        .btn-submit { width: 100%; background: #0a1628; color: white; border: none; padding: 16px; font-size: 12px; letter-spacing: 2px; text-transform: uppercase; font-weight: 500; cursor: pointer; margin-top: 16px; border-radius: 0; }
        .btn-submit:hover { background: #c9a03d; color: #0a1628; }
        .note { font-size: 11px; color: #8a9bb0; text-align: center; margin-top: 24px; }
        @media (max-width: 600px) { .container { padding: 32px 20px; } .form-card { padding: 28px; } }
    </style>
</head>
<body>
    <div class="container">
        <a href="/" class="logo">VETTIFY <span>INTELLIGENCE</span></a>
        <div class="form-card">
            <h1>Apply for Intelligence Access</h1>
            <div class="sub">Applications are reviewed manually. Limited to 20 active clients.</div>
            <form id="applicationForm">
                <div class="form-group"><label>Full Name</label><input type="text" id="full_name" required></div>
                <div class="form-group"><label>Email Address</label><input type="email" id="email" required></div>
                <div class="form-group"><label>LinkedIn / Profile URL</label><input type="url" id="linkedin_url" placeholder="linkedin.com/in/..."></div>
                <div class="form-group"><label>Current Position / Title</label><input type="text" id="position" placeholder="Founder, CEO, Executive..."></div>
                <div class="form-group"><label>If raising capital, what amount?</label><select id="funding_amount"><option value="Not raising">Not raising currently</option><option value="Under R5M">Under R5M</option><option value="R5M-R20M">R5M - R20M</option><option value="R20M-R100M">R20M - R100M</option><option value="R100M+">R100M+</option></select></div>
                <div class="form-group"><label>What are your visibility goals?</label><textarea id="visibility_goal" rows="3" placeholder="Fundraising, speaking opportunities, media features, board positions..."></textarea></div>
                <button type="submit" class="btn-submit">Submit Application →</button>
                <div class="note">Your application will be reviewed within 24 hours. Selected clients will receive a confidential onboarding packet.</div>
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
                position: document.getElementById('position').value,
                funding_amount: document.getElementById('funding_amount').value,
                visibility_goal: document.getElementById('visibility_goal').value
            };
            try {
                const res = await fetch('/submit-application', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(formData) });
                if (res.ok) {
                    alert('Application received. We will review and respond within 24 hours.');
                    window.location.href = '/';
                } else { alert('Error submitting application.'); }
            } catch(err) { alert('Error submitting.'); }
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
    conn.execute('''INSERT INTO applications 
        (id, full_name, email, linkedin_url, position, funding_amount, visibility_goal, submitted_at) 
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
        (app_id, data['full_name'], data['email'], data['linkedin_url'], 
         data['position'], data['funding_amount'], data['visibility_goal'], datetime.now().isoformat()))
    conn.commit()
    conn.close()
    return jsonify({'status': 'received'})

@app.route('/admin/applications')
def admin_applications():
    conn = get_db()
    apps = conn.execute('SELECT * FROM applications ORDER BY submitted_at DESC').fetchall()
    conn.close()
    return render_template_string('''
<!DOCTYPE html>
<html>
<head><title>Vettify Admin</title><style>body{font-family:monospace;padding:20px;}table{border-collapse:collapse;}td,th{border:1px solid #ccc;padding:8px;text-align:left;}</style></head>
<body>
    <h1>Intelligence Applications ({{ apps|length }})</h1>
    <table>
        <tr><th>Name</th><th>Email</th><th>Position</th><th>Funding</th><th>Goal</th><th>Status</th><th>Submitted</th></tr>
        {% for a in apps %}
        <tr>
            <td>{{ a.full_name }}</td><td>{{ a.email }}</td><td>{{ a.position }}</td>
            <td>{{ a.funding_amount }}</td><td>{{ a.visibility_goal[:50] }}...</td>
            <td>{{ a.status }}</td><td>{{ a.submitted_at[:16] }}</td>
        </tr>
        {% endfor %}
    </table>
</body>
</html>
    ''', apps=apps)

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=5000)
    
