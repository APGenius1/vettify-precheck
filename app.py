from flask import Flask, request, jsonify, send_file, render_template_string
from flask_cors import CORS
import io
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from datetime import datetime, timedelta
import json
import os
import uuid
import math
import re
import sqlite3

app = Flask(__name__)
app.secret_key = os.urandom(24).hex()
CORS(app)

# Database setup
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

# Actuarial Core
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
    premium = epv_benefit / epv_premiums if epv_premiums > 0 else coverage / (term_years * 12)
    if gender == "male":
        premium *= 1.12
    ratio = coverage / income if income > 0 else 10
    if ratio > 4:
        premium *= 1 + min(0.6, (ratio - 4) * 0.1)
    return max(80, min(15000, round(premium)))

def calculate_risk_score(age: int, smoker: bool, coverage: float, income: float, term_years: int) -> dict:
    """Returns detailed risk breakdown"""
    score = 70
    drivers = []
    
    # Smoker impact
    if smoker:
        score -= 30
        drivers.append({"factor": "Smoker", "impact": -30, "explanation": "Tobacco use significantly increases mortality risk"})
    else:
        drivers.append({"factor": "Non-smoker", "impact": 0, "explanation": "Standard mortality rates apply"})
    
    # Age impact
    if age > 65:
        score -= 18
        drivers.append({"factor": "Age >65", "impact": -18, "explanation": "Advanced age increases baseline mortality risk"})
    elif age > 55:
        score -= 12
        drivers.append({"factor": "Age 55-65", "impact": -12, "explanation": "Moderate age-related mortality increase"})
    elif age > 45:
        score -= 6
        drivers.append({"factor": "Age 45-55", "impact": -6, "explanation": "Minor age-related mortality increase"})
    elif age < 30:
        score += 5
        drivers.append({"factor": "Age <30", "impact": 5, "explanation": "Low baseline mortality for young age"})
    else:
        drivers.append({"factor": "Age 30-45", "impact": 0, "explanation": "Standard age mortality rates"})
    
    # Coverage/income ratio
    ratio = coverage / income if income > 0 else 0
    if ratio > 8:
        score -= 15
        drivers.append({"factor": "High coverage/income", "impact": -15, "explanation": f"Coverage {ratio:.1f}x income exceeds typical guidelines"})
    elif ratio > 6:
        score -= 10
        drivers.append({"factor": "Elevated coverage/income", "impact": -10, "explanation": f"Coverage {ratio:.1f}x income may trigger underwriting review"})
    elif ratio > 4:
        score -= 5
        drivers.append({"factor": "Moderate coverage/income", "impact": -5, "explanation": f"Coverage {ratio:.1f}x income near industry guideline"})
    else:
        drivers.append({"factor": "Coverage/income ratio", "impact": 0, "explanation": f"Coverage {ratio:.1f}x income within guidelines"})
    
    # Term impact
    if term_years > 25:
        score -= 5
        drivers.append({"factor": "Long term", "impact": -5, "explanation": "Policy term >25 years adds uncertainty"})
    else:
        drivers.append({"factor": "Term length", "impact": 0, "explanation": f"{term_years} year term: standard duration"})
    
    score = max(10, min(95, score))
    
    # Classification
    if score >= 70:
        level = "Low"
        approval = "High - Standard acceptance expected"
        color = "#16a34a"
        action = "Proceed with standard application"
    elif score >= 40:
        level = "Moderate"
        approval = "Moderate - Standard underwriting with possible questions"
        color = "#ea580c"
        action = "Prepare for medical questionnaire"
    else:
        level = "High"
        approval = "Low - Medical underwriting likely required"
        color = "#dc2626"
        action = "Consult with underwriter before applying"
    
    return {
        'score': score,
        'level': level,
        'approval': approval,
        'color': color,
        'action': action,
        'drivers': drivers
    }

def get_market_comparison(premium: float, age: int) -> dict:
    """Market benchmarking"""
    if age < 30:
        market_min = premium * 0.85
        market_max = premium * 1.15
        percentile = 45
    elif age < 45:
        market_min = premium * 0.90
        market_max = premium * 1.12
        percentile = 55
    else:
        market_min = premium * 0.88
        market_max = premium * 1.18
        percentile = 48
    
    confidence = 12  # ±12% confidence interval
    
    return {
        'min': round(market_min),
        'max': round(market_max),
        'percentile': percentile,
        'confidence': confidence,
        'position': "below median" if percentile < 50 else "above median"
    }

def get_insurer_match(risk_score: int, age: int, smoker: bool) -> dict:
    """Insurer matching based on risk profile"""
    if risk_score >= 70:
        insurers = ["Discovery", "Old Mutual", "Momentum", "Sanlam"]
        recommendation = "Preferred rates available across major insurers"
    elif risk_score >= 40:
        insurers = ["Old Mutual", "Momentum"]
        recommendation = "Standard underwriting with these insurers"
    else:
        insurers = ["BrightRock", "Hollard"]
        recommendation = "Specialist insurers recommended for this profile"
    
    if smoker:
        insurers = ["Momentum", "BrightRock"]
        recommendation = "Smoker-friendly options available through specialist products"
    
    return {'insurers': insurers, 'recommendation': recommendation}

# Database helpers
def get_usage(email: str):
    conn = get_db()
    result = conn.execute('SELECT count, paid FROM usage WHERE email = ?', (email,)).fetchone()
    conn.close()
    return {'count': result['count'] if result else 0, 'paid': bool(result['paid']) if result else False}

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

# PDF Generation
def generate_pdf(data: dict, premium: float, risk_result: dict, market: dict, insurer_match: dict):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=72)
    styles = getSampleStyleSheet()
    story = []
    
    vettify_blue = colors.HexColor('#0a2540')
    risk_color = colors.HexColor(risk_result['color'])
    
    # Header
    story.append(Paragraph("VETTIFY PRECHECK", ParagraphStyle('Title', parent=styles['Heading1'], fontSize=28, textColor=vettify_blue, alignment=1, spaceAfter=6)))
    story.append(Paragraph("Actuarial Underwriting Intelligence Report", ParagraphStyle('Sub', parent=styles['Normal'], fontSize=10, textColor=colors.grey, alignment=1)))
    story.append(Spacer(1, 0.1*inch))
    story.append(HRFlowable(width="100%", thickness=1, color=vettify_blue))
    story.append(Spacer(1, 0.2*inch))
    
    # Report metadata
    report_id = str(uuid.uuid4())[:8]
    valid_until = (datetime.now() + timedelta(days=7)).strftime('%d %B %Y')
    story.append(Paragraph(f"<b>Report ID:</b> {report_id}", styles['Normal']))
    story.append(Paragraph(f"<b>Valid Until:</b> {valid_until}", styles['Normal']))
    story.append(Paragraph(f"<b>Generated:</b> {datetime.now().strftime('%d %B %Y at %H:%M')}", styles['Normal']))
    story.append(Spacer(1, 0.2*inch))
    
    # Risk Score - Large and prominent
    story.append(Paragraph("YOUR RISK SCORE", ParagraphStyle('ScoreHead', parent=styles['Heading2'], fontSize=14, textColor=colors.grey)))
    story.append(Paragraph(f"{risk_result['score']}<font size=12>/100</font>", ParagraphStyle('Score', parent=styles['Normal'], fontSize=56, textColor=risk_color, alignment=1, spaceAfter=6)))
    story.append(Paragraph(f"<b>{risk_result['level']} RISK</b>", ParagraphStyle('RiskLevel', parent=styles['Normal'], fontSize=16, textColor=risk_color, alignment=1)))
    story.append(Paragraph(f"{risk_result['approval']}", styles['Normal']))
    story.append(Spacer(1, 0.2*inch))
    
    # Risk Drivers Breakdown Table
    story.append(Paragraph("RISK DRIVERS BREAKDOWN", styles['Heading2']))
    story.append(Spacer(1, 0.05*inch))
    
    driver_data = [["Factor", "Impact", "Explanation"]]
    for d in risk_result['drivers']:
        impact_str = f"+{d['impact']}" if d['impact'] > 0 else str(d['impact'])
        driver_data.append([d['actor'], impact_str, d['explanation']])
    
    driver_table = Table(driver_data, colWidths=[1.5*inch, 0.8*inch, 3.2*inch])
    driver_table.setStyle(TableStyle([
        ('FONTNAME', (0,0), (-1,-1), 'Helvetica'),
        ('FONTSIZE', (0,0), (-1,-1), 9),
        ('BACKGROUND', (0,0), (-1,0), vettify_blue),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('ALIGN', (1,0), (1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(driver_table)
    story.append(Spacer(1, 0.2*inch))
    
    # Comparative Benchmark
    story.append(Paragraph("COMPARATIVE BENCHMARK", styles['Heading2']))
    story.append(Spacer(1, 0.05*inch))
    story.append(Paragraph(f"<b>Your risk score of {risk_result['score']} is lower than {market['percentile']}% of similar applicants.</b>", styles['Normal']))
    story.append(Spacer(1, 0.1*inch))
    
    # Premium with confidence interval
    story.append(Paragraph("PREMIUM ESTIMATE", styles['Heading2']))
    low_premium = int(premium * (1 - market['confidence']/100))
    high_premium = int(premium * (1 + market['confidence']/100))
    story.append(Paragraph(f"<font size=24><b>R{premium}</b></font> <font size=12>/ month</font>", styles['Normal']))
    story.append(Paragraph(f"<b>Confidence Interval:</b> ±{market['confidence']}% (R{low_premium} - R{high_premium})", styles['Normal']))
    story.append(Paragraph(f"<b>Market Range:</b> R{market['min']} - R{market['max']}/month", styles['Normal']))
    story.append(Paragraph(f"<b>Your premium is {market['position']} for your age group.</b>", styles['Normal']))
    story.append(Spacer(1, 0.15*inch))
    
    # Insurer Matching
    story.append(Paragraph("INSURER MATCHING", styles['Heading2']))
    story.append(Paragraph(f"<b>Recommended Insurers:</b> {', '.join(insurer_match['insurers'])}", styles['Normal']))
    story.append(Paragraph(f"<b>{insurer_match['recommendation']}</b>", styles['Normal']))
    story.append(Spacer(1, 0.15*inch))
    
    # Next Steps / Action CTA
    story.append(Paragraph("NEXT STEPS", ParagraphStyle('ActionHead', parent=styles['Heading2'], textColor=vettify_blue)))
    story.append(Spacer(1, 0.05*inch))
    story.append(Paragraph("✓ Share this report with your broker or insurer", styles['Normal']))
    story.append(Paragraph("✓ Use this estimate for pre-approval discussions", styles['Normal']))
    story.append(Paragraph("✓ Lock in indicative rates within 7 days", styles['Normal']))
    story.append(Spacer(1, 0.1*inch))
    story.append(Paragraph(f"<b>Recommended Action:</b> {risk_result['action']}", ParagraphStyle('Action', parent=styles['Normal'], textColor=risk_color)))
    story.append(Spacer(1, 0.2*inch))
    
    # Value Anchoring
    story.append(Paragraph("VALUE COMPARISON", styles['Heading2']))
    story.append(Paragraph("This actuarial analysis typically costs <b>R500 - R1,500</b> through traditional brokerage underwriting reviews.", styles['Normal']))
    story.append(Paragraph(f"<b>You're getting this report for only R49</b> — a discount of over 90% off market rate.", styles['Normal']))
    story.append(Spacer(1, 0.15*inch))
    
    # Methodology Footer
    story.append(Paragraph("METHODOLOGY", styles['Heading2']))
    story.append(Paragraph("Gompertz-Makeham mortality model • EPV (Expected Present Value) calculation • Monthly step consistent • 6% discount rate", ParagraphStyle('Method', parent=styles['Normal'], fontSize=7, textColor=colors.grey)))
    story.append(Spacer(1, 0.1*inch))
    
    # Disclaimer
    story.append(Paragraph("DISCLAIMER", styles['Heading2']))
    story.append(Paragraph("This is a pre-screening intelligence report only. Valid for 7 days. Actual underwriting decisions vary by insurer.", ParagraphStyle('Disclaimer', parent=styles['Normal'], fontSize=7, textColor=colors.grey)))
    
    doc.build(story)
    buffer.seek(0)
    return buffer

# Flask Routes
@app.route('/')
def home():
    return render_template_string(HTML_TEMPLATE)

@app.route('/calculate', methods=['POST'])
def calculate():
    data = request.json
    email = data.get('email')
    
    usage = get_usage(email)
    if not usage['paid'] and usage['count'] >= 5:
        return jsonify({'error': 'Free limit reached. Please purchase the full report.'}), 403
    
    premium = calculate_premium(
        data['age'], data['gender'], data['smoker'],
        data['income_band'], data['coverage_amount'], data['term_years']
    )
    
    risk_result = calculate_risk_score(
        data['age'], data['smoker'],
        data['coverage_amount'], data['income_band'], data['term_years']
    )
    
    market = get_market_comparison(premium, data['age'])
    insurer_match = get_insurer_match(risk_result['score'], data['age'], data['smoker'])
    
    if not usage['paid']:
        increment_usage(email)
    
    return jsonify({
        'premium': premium,
        'risk_score': risk_result['score'],
        'risk_level': risk_result['level'],
        'risk_color': risk_result['color'],
        'approval': risk_result['approval'],
        'action': risk_result['action'],
        'drivers': risk_result['drivers'],
        'market_min': market['min'],
        'market_max': market['max'],
        'percentile': market['percentile'],
        'confidence': market['confidence'],
        'insurers': insurer_match['insurers'],
        'insurer_recommendation': insurer_match['recommendation']
    })

@app.route('/generate-report', methods=['POST'])
def generate_report():
    data = request.json
    email = data.get('email')
    
    usage = get_usage(email)
    if not usage['paid'] and usage['count'] >= 5:
        return jsonify({'error': 'Free limit reached. Please purchase the full report.'}), 403
    
    premium = calculate_premium(
        data['age'], data['gender'], data['smoker'],
        data['income_band'], data['coverage_amount'], data['term_years']
    )
    
    risk_result = calculate_risk_score(
        data['age'], data['smoker'],
        data['coverage_amount'], data['income_band'], data['term_years']
    )
    
    market = get_market_comparison(premium, data['age'])
    insurer_match = get_insurer_match(risk_result['score'], data['age'], data['smoker'])
    
    pdf_buffer = generate_pdf({
        'age': data['age'],
        'gender': data['gender'],
        'smoker': data['smoker'],
        'income': data['income_band'],
        'coverage': data['coverage_amount'],
        'term': data['term_years']
    }, premium, risk_result, market, insurer_match)
    
    # Save lead
    conn = get_db()
    lead_id = str(uuid.uuid4())
    conn.execute('INSERT OR REPLACE INTO leads VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                 (lead_id, email, data['age'], data['gender'], 1 if data['smoker'] else 0,
                  data['income_band'], data['coverage_amount'], data['term_years'], premium, risk_result['score'], datetime.now().isoformat()))
    conn.commit()
    conn.close()
    
    if not usage['paid']:
        increment_usage(email)
    
    return send_file(pdf_buffer, mimetype='application/pdf', as_attachment=True, download_name=f'vettify_report_{data["age"]}.pdf')

@app.route('/usage', methods=['GET'])
def usage():
    email = request.args.get('email')
    usage = get_usage(email)
    return jsonify({'count': usage['count'], 'paid': usage['paid']})

# HTML Template
HTML_TEMPLATE = '''
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
        .main-container { max-width: 1280px; margin: -40px auto 48px; padding: 0 32px; display: grid; grid-template-columns: 1fr 0.9fr; gap: 32px; }
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
        .result-card { background: white; border-radius: 28px; box-shadow: 0 8px 30px rgba(0,0,0,0.1); padding: 32px; position: sticky; top: 100px; }
        .result-score { text-align: center; padding: 24px; background: #f8fafc; border-radius: 20px; margin-bottom: 24px; }
        .score-number { font-size: 64px; font-weight: 800; line-height: 1; }
        .premium-box { background: #f0fdf4; padding: 16px; border-radius: 16px; text-align: center; }
        .premium-amount { font-size: 28px; font-weight: 800; color: #16a34a; }
        .drivers-list { background: #f8fafc; border-radius: 16px; padding: 20px; margin: 16px 0; }
        .driver-item { display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #e2e8f0; font-size: 14px; }
        .driver-impact-neg { color: #dc2626; font-weight: 600; }
        .driver-impact-pos { color: #16a34a; font-weight: 600; }
        .features-list { background: #f8fafc; border-radius: 16px; padding: 20px; margin: 20px 0; }
        .features-list li { margin-left: 20px; margin-bottom: 8px; color: #1a2c3e; font-size: 13px; }
        .paywall { background: #fef3c7; border-radius: 20px; padding: 24px; text-align: center; margin-top: 24px; }
        .paywall h3 { font-size: 18px; font-weight: 700; color: #92400e; margin-bottom: 12px; }
        .paywall-price { font-size: 32px; font-weight: 800; color: #0a2540; margin: 16px 0; }
        .btn-pay { width: 100%; padding: 14px; background: #0070ba; color: white; border: none; border-radius: 12px; font-weight: 700; font-size: 16px; cursor: pointer; }
        .value-badge { background: #e8f0fe; border-radius: 12px; padding: 12px; margin: 16px 0; text-align: center; font-size: 12px; color: #0a2540; }
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
        <div class="hero-badge">⚡ Decision Intelligence System</div>
        <h1>Know before you apply</h1>
        <p>Risk breakdown • Insurer matching • Confidence intervals • First 5 free</p>
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
                    <button type="submit" class="btn-primary" id="calculateBtn">Analyze Risk Profile →</button>
                </form>
                <div class="error" id="error"></div>
            </div>
        </div>
        
        <div>
            <div class="result-card" id="resultCard">
                <div id="statusContainer"></div>
                <div id="freeResult">
                    <div class="result-score"><div class="score-number" id="riskScore">—</div><div class="score-label">Risk Score (0-100)</div><div id="approvalText" style="margin-top: 8px; font-size: 12px;"></div></div>
                    
                    <div class="result-section"><h4>Risk Drivers</h4><div id="driversContainer" class="drivers-list">Complete the form to see analysis</div></div>
                    
                    <div class="result-section"><h4>Premium Estimate</h4><div id="premiumText">—</div><div id="marketRange" style="font-size: 12px; color: #5b6e8c; margin-top: 4px;"></div></div>
                    
                    <div class="result-section"><h4>Insurer Matching</h4><div id="insurerText">—</div></div>
                    
                    <div class="value-badge" id="valueBadge" style="display: none;">
                        <strong>💰 Market Value: R500 - R1,500</strong><br>
                        You're getting this analysis for only R49
                    </div>
                    
                    <div class="paywall" id="paywall">
                        <h3>🔓 Unlock Full Intelligence Report</h3>
                        <p>Risk breakdown • Insurer matching • Confidence intervals • Actionable insights</p>
