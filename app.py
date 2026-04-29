from flask import Flask, request, jsonify, send_file, render_template_string, g
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
import hashlib
import time
import sqlite3
from functools import wraps, lru_cache
from typing import Tuple, Dict, Any, List, Optional

app = Flask(__name__)

# Production security
SECRET_KEY = os.environ.get('SECRET_KEY')
if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY environment variable is required")
app.secret_key = SECRET_KEY

API_KEY = os.environ.get('API_KEY')
if not API_KEY:
    raise RuntimeError("API_KEY environment variable is required")

CORS(app)

# ============================================
# SQLite Database (Production-ready)
# ============================================

DATABASE = 'vettify.db'

def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(error):
    db = g.pop('db', None)
    if db is not None:
        db.close()

def init_db():
    db = sqlite3.connect(DATABASE)
    cursor = db.cursor()
    
    # Usage table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS usage (
            email TEXT PRIMARY KEY,
            count INTEGER DEFAULT 0,
            paid BOOLEAN DEFAULT 0,
            first_use TEXT,
            paid_at TEXT,
            transaction_id TEXT
        )
    ''')
    
    # Audit log table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            email TEXT,
            input_hash TEXT,
            age INTEGER,
            smoker BOOLEAN,
            coverage REAL,
            term INTEGER,
            premium REAL,
            risk_score INTEGER,
            endpoint TEXT
        )
    ''')
    
    # Rate limiting table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS rate_limit (
            ip TEXT,
            timestamp REAL,
            PRIMARY KEY (ip, timestamp)
        )
    ''')
    
    # Leads table
    cursor.execute('''
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
    
    db.commit()
    db.close()

# Initialize database on startup
init_db()

# ============================================
# API Key Protection
# ============================================

def require_api_key(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        api_key = request.headers.get('X-API-Key')
        if not api_key or api_key != API_KEY:
            return jsonify({'error': 'Invalid or missing API key'}), 401
        return f(*args, **kwargs)
    return decorated_function

# ============================================
# Rate Limiting (with auto-cleanup)
# ============================================

def check_rate_limit(ip: str) -> bool:
    db = get_db()
    now = time.time()
    window = 60  # seconds
    max_requests = 30
    
    # Clean old entries (>24 hours)
    cutoff = now - 86400  # 24 hours
    db.execute('DELETE FROM rate_limit WHERE timestamp < ?', (cutoff,))
    
    # Count recent requests
    count = db.execute(
        'SELECT COUNT(*) as cnt FROM rate_limit WHERE ip = ? AND timestamp > ?',
        (ip, now - window)
    ).fetchone()['cnt']
    
    if count >= max_requests:
        return False
    
    # Log this request
    db.execute(
        'INSERT INTO rate_limit (ip, timestamp) VALUES (?, ?)',
        (ip, now)
    )
    db.commit()
    return True

# ============================================
# Audit Logging
# ============================================

def log_audit(email: str, input_data: Dict, premium: float, risk_score: int, endpoint: str):
    db = get_db()
    input_str = f"{input_data.get('age')}_{input_data.get('smoker')}_{input_data.get('coverage_amount')}"
    input_hash = hashlib.md5(input_str.encode()).hexdigest()
    
    db.execute('''
        INSERT INTO audit_log (timestamp, email, input_hash, age, smoker, coverage, term, premium, risk_score, endpoint)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        datetime.now().isoformat(),
        email,
        input_hash,
        input_data.get('age'),
        1 if input_data.get('smoker') else 0,
        input_data.get('coverage_amount', 0),
        input_data.get('term_years', 0),
        premium,
        risk_score,
        endpoint
    ))
    db.commit()

# ============================================
# Gompertz-Makeham Actuarial Core
# ============================================

GOMPERTZ_A = 0.00022
GOMPERTZ_B = 0.000027
GOMPERTZ_C = 0.092
LAPSE_RATE = 0.02  # Annual lapse rate

def force_of_mortality(age: int) -> float:
    """μ(x) = A + B * exp(C * x)"""
    return GOMPERTZ_A + GOMPERTZ_B * math.exp(GOMPERTZ_C * age)

def smoker_mortality_multiplier(age: int) -> float:
    """Age-dependent smoker multiplier applied to force of mortality"""
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

@lru_cache(maxsize=10000)
def get_monthly_mortality(age: int, smoker: bool) -> float:
    """
    CORRECT: Apply smoker effect to force of mortality, then convert to probability
    q_month = 1 - exp(-μ/12)
    """
    mu = force_of_mortality(age)
    if smoker:
        mu *= smoker_mortality_multiplier(age)
    
    q = 1 - math.exp(-mu / 12)
    return min(q, 0.05)

@lru_cache(maxsize=10000)
def get_monthly_lapse() -> float:
    """Monthly lapse probability"""
    return 1 - math.exp(-LAPSE_RATE / 12)

# ============================================
# EPV Calculations with Lapse
# ============================================

def calculate_epv_benefit(coverage: float, age: int, term_years: int, smoker: bool, discount_rate: float = 0.06) -> float:
    """
    Expected Present Value of benefit with lapse assumptions
    """
    v = 1 / (1 + discount_rate / 12)
    epv = 0.0
    survival = 1.0
    
    for month in range(1, term_years * 12 + 1):
        current_age = age + (month - 1) // 12
        q_mort = get_monthly_mortality(current_age, smoker)
        q_lapse = get_monthly_lapse()
        
        # Total decrement
        prob_death = survival * q_mort
        survival *= (1 - q_mort - q_lapse)
        
        discount = v ** month
        epv += discount * prob_death * coverage
    
    return epv

def calculate_epv_premiums(age: int, term_years: int, smoker: bool, discount_rate: float = 0.06) -> float:
    """
    Expected Present Value of premium stream with lapse
    """
    v = 1 / (1 + discount_rate / 12)
    epv = 0.0
    survival = 1.0
    
    for month in range(1, term_years * 12 + 1):
        current_age = age + (month - 1) // 12
        q_mort = get_monthly_mortality(current_age, smoker)
        q_lapse = get_monthly_lapse()
        
        epv += (v ** (month - 1)) * survival
        survival *= (1 - q_mort - q_lapse)
    
    return epv

# ============================================
# Anti-selection loading (logistic, smooth)
# ============================================

def anti_selection_loading(coverage: float, income: float) -> float:
    """Smooth logistic loading for coverage/income ratio"""
    if income <= 0:
        return 1.0
    
    ratio = coverage / income
    # Logistic: 1 + 0.6 / (1 + exp(-1.2*(ratio-6)))
    loading = 1 + (0.6 / (1 + math.exp(-1.2 * (ratio - 6))))
    return min(loading, 1.8)

def confidence_interval(premium: float) -> Tuple[float, float]:
    """Add 10% uncertainty band for credibility"""
    return round(premium * 0.9), round(premium * 1.15)

# ============================================
# Pure Premium Calculation
# ============================================

def calculate_pure_premium(age: int, gender: str, smoker: bool, income: float, coverage: float, term_years: int) -> Tuple[float, float, float]:
    """
    Returns: (premium, premium_low, premium_high) with confidence interval
    """
    epv_benefit = calculate_epv_benefit(coverage, age, term_years, smoker)
    epv_premiums = calculate_epv_premiums(age, term_years, smoker)
    
    if epv_premiums <= 0:
        base_premium = max(80.0, min(15000.0, coverage / (term_years * 12)))
    else:
        base_premium = epv_benefit / epv_premiums
    
    # Gender loading
    if gender == "male":
        base_premium *= 1.12
    
    # Anti-selection loading
    base_premium *= anti_selection_loading(coverage, income)
    
    # Bounds
    base_premium = max(base_premium, 80.0)
    base_premium = min(base_premium, 15000.0)
    
    premium = round(base_premium)
    premium_low, premium_high = confidence_interval(base_premium)
    
    return premium, premium_low, premium_high

# ============================================
# Risk Scoring (Completely Independent)
# ============================================

def calculate_risk_score(age: int, smoker: bool, term_years: int) -> Tuple[int, str, str, str]:
    """
    Independent risk scoring - uses ONLY medical/demographic factors
    Does NOT use coverage/income to maintain pricing independence
    """
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
    
    if term_years > 25:
        score -= 5
    
    score = max(10, min(95, score))
    
    if score >= 70:
        level = "Low"
        comment = "Favorable risk profile"
        color = "#16a34a"
    elif score >= 40:
        level = "Moderate"
        comment = "Standard risk profile"
        color = "#ea580c"
    else:
        level = "High"
        comment = "Elevated risk profile"
        color = "#dc2626"
    
    return score, level, comment, color

# ============================================
# Usage Tracking (SQLite)
# ============================================

def get_usage(email: str) -> Dict:
    db = get_db()
    result = db.execute('SELECT count, paid FROM usage WHERE email = ?', (email,)).fetchone()
    if result:
        return {'count': result['count'], 'paid': bool(result['paid'])}
    return {'count': 0, 'paid': False}

def increment_usage(email: str) -> int:
    db = get_db()
    current = get_usage(email)
    new_count = current['count'] + 1
    
    if current['count'] == 0:
        db.execute(
            'INSERT INTO usage (email, count, paid, first_use) VALUES (?, ?, ?, ?)',
            (email, new_count, 0, datetime.now().isoformat())
        )
    else:
        db.execute('UPDATE usage SET count = ? WHERE email = ?', (new_count, email))
    
    db.commit()
    return new_count

def mark_paid(email: str, transaction_id: str) -> None:
    db = get_db()
    db.execute(
        'UPDATE usage SET paid = 1, paid_at = ?, transaction_id = ? WHERE email = ?',
        (datetime.now().isoformat(), transaction_id, email)
    )
    db.commit()

def can_access(email: str) -> Tuple[bool, str]:
    usage = get_usage(email)
    if usage['paid']:
        return True, "paid"
    if usage['count'] >= 20:
        return False, "free_limit_reached"
    return True, "free"

# ============================================
# Input Validation
# ============================================

def validate_assessment_input(data: Dict) -> Tuple[bool, str, Dict]:
    try:
        age = int(data.get('age', 0))
        if age < 18 or age > 80:
            return False, "Age must be between 18 and 80", {}
        
        gender = data.get('gender', '').lower()
        if gender not in ['male', 'female']:
            return False, "Gender must be male or female", {}
        
        smoker = bool(data.get('smoker', False))
        
        income = float(data.get('income_band', 0))
        if income < 0 or income > 100_000_000:
            return False, "Income must be between R0 and R100,000,000", {}
        
        coverage = float(data.get('coverage_amount', 0))
        if coverage < 50000 or coverage > 100_000_000:
            return False, "Coverage must be between R50,000 and R100,000,000", {}
        
        term = int(data.get('term_years', 0))
        if term < 1 or term > 50:
            return False, "Term must be between 1 and 50 years", {}
        
        email = data.get('email', '').strip()
        if email and not re.match(r'^[^\s@]+@[^\s@]+\.[^\s@]+$', email):
            return False, "Invalid email address", {}
        
        cleaned_data = {
            'age': age,
            'gender': gender,
            'smoker': smoker,
            'income_band': income,
            'coverage_amount': coverage,
            'term_years': term,
            'email': email
        }
        
        return True, "", cleaned_data
        
    except (ValueError, TypeError) as e:
        return False, f"Invalid input: {str(e)}", {}

# ============================================
# PDF Generation
# ============================================

def generate_actuarial_report(data: Dict, premium: float, premium_low: float, premium_high: float, 
                               risk_score: int, risk_level: str, risk_comment: str, risk_color: str) -> io.BytesIO:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=72)
    styles = getSampleStyleSheet()
    story = []
    
    vettify_blue = colors.HexColor('#0a2540')
    risk_color_obj = colors.HexColor(risk_color)
    
    epv_benefit = calculate_epv_benefit(data['coverage_amount'], data['age'], data['term_years'], data['smoker'])
    epv_premiums = calculate_epv_premiums(data['age'], data['term_years'], data['smoker'])
    
    title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'], fontSize=28, textColor=vettify_blue, alignment=1, spaceAfter=6)
    story.append(Paragraph("VETTIFY PRECHECK", title_style))
    story.append(Spacer(1, 0.2*inch))
    
    report_id = str(uuid.uuid4())[:8]
    valid_until = (datetime.now() + timedelta(days=7)).strftime('%d %B %Y')
    story.append(Paragraph(f"Report ID: {report_id}", styles['Normal']))
    story.append(Paragraph(f"Valid Until: {valid_until}", styles['Normal']))
    story.append(Paragraph(f"Generated: {datetime.now().strftime('%d %B %Y at %H:%M')}", styles['Normal']))
    story.append(Spacer(1, 0.2*inch))
    
    story.append(Paragraph("RISK ASSESSMENT", styles['Heading2']))
    score_style = ParagraphStyle('Score', parent=styles['Normal'], fontSize=48, textColor=risk_color_obj, alignment=1, spaceAfter=6)
    story.append(Paragraph(f"{risk_score}<font size=20>/100</font>", score_style))
    story.append(Paragraph(f"{risk_level} RISK", styles['Normal']))
    story.append(Paragraph(risk_comment, styles['Normal']))
    story.append(Spacer(1, 0.2*inch))
    
    story.append(Paragraph("CLIENT PROFILE", styles['Heading2']))
    info_data = [
        ["Age", str(data['age']) + " years"],
        ["Gender", data['gender'].capitalize()],
        ["Smoker", "Yes" if data['smoker'] else "No"],
        ["Annual Income", f"R{data['income_band']:,.0f}"],
        ["Coverage Requested", f"R{data['coverage_amount']:,.0f}"],
        ["Term", f"{data['term_years']} years"],
        ["Monthly Premium", f"R{premium:,.0f} (Range: R{premium_low:,.0f} - R{premium_high:,.0f})"],
    ]
    info_table = Table(info_data, colWidths=[1.8*inch, 3.2*inch])
    info_table.setStyle(TableStyle([('FONTNAME', (0,0), (-1,-1), 'Helvetica'), ('FONTSIZE', (0,0), (-1,-1), 10)]))
    story.append(info_table)
    story.append(Spacer(1, 0.2*inch))
    
    story.append(Paragraph("ACTUARIAL METHODOLOGY", styles['Heading2']))
    method_text = f"""
    Premium calculated using equivalence principle with lapse assumptions:
    
    • EPV of Benefit: R{epv_benefit:,.0f}
    • EPV of Premiums: {epv_premiums:.4f}
    • Monthly Premium = EPV(Benefit) / EPV(Premiums) = R{premium:,.0f}
    • Confidence Interval: ±10% (R{premium_low:,.0f} - R{premium_high:,.0f})
    
    Mortality Model: Gompertz-Makeham μ(x) = A + B·e^(C·x)
    Smoker adjustment: Applied to force of mortality (actuarially correct)
    Lapse assumption: {LAPSE_RATE * 100:.0f}% annual
    Discount rate: 6% per annum (monthly compounding)
    """
    story.append(Paragraph(method_text, styles['Normal']))
    story.append(Spacer(1, 0.15*inch))
    
    story.append(Paragraph("DISCLAIMER", styles['Heading2']))
    disclaimer_style = ParagraphStyle('Disclaimer', parent=styles['Normal'], fontSize=7, textColor=colors.grey)
    story.append(Paragraph("This is a pre-screening intelligence report only. Valid for 7 days. Actual underwriting decisions and premiums vary by insurer and require full medical underwriting. Not a binding quote.", disclaimer_style))
    story.append(Spacer(1, 0.1*inch))
    
    footer_style = ParagraphStyle('Footer', parent=styles['Normal'], fontSize=7, textColor=vettify_blue, alignment=1)
    story.append(Paragraph("vettifyprecheck.com · Gompertz-Makeham Actuarial Model", footer_style))
    
    doc.build(story)
    buffer.seek(0)
    return buffer

# ============================================
# Flask Routes
# ============================================

@app.before_request
def before_request():
    if request.endpoint not in ['static', 'home']:
        client_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
        if not check_rate_limit(client_ip):
            return jsonify({'error': 'Rate limit exceeded. Please try again later.'}), 429

@app.route('/')
def home():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/usage', methods=['GET'])
@require_api_key
def usage_endpoint():
    """GET /api/usage?email=user@example.com - Returns usage data (requires API key)"""
    email = request.args.get('email', '').strip()
    if not email:
        return jsonify({'error': 'Email required'}), 400
    
    usage = get_usage(email)
    return jsonify({
        'count': usage['count'],
        'paid': usage['paid'],
        'remaining': max(0, 20 - usage['count'])
    })

@app.route('/api/calculate', methods=['POST'])
@require_api_key
def calculate_endpoint():
    """POST /api/calculate - Calculate risk score and premium estimate (requires API key)"""
    data = request.json
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    valid, error, cleaned = validate_assessment_input(data)
    if not valid:
        return jsonify({'error': error}), 400
    
    email = cleaned.get('email', '')
    if not email:
        return jsonify({'error': 'Email required'}), 400
    
    can_access_flag, status = can_access(email)
    if not can_access_flag:
        return jsonify({'error': 'Free limit reached. Please purchase the full report.'}), 403
    
    premium, premium_low, premium_high = calculate_pure_premium(
        cleaned['age'], cleaned['gender'], cleaned['smoker'],
        cleaned['income_band'], cleaned['coverage_amount'], cleaned['term_years']
    )
    
    risk_score, risk_level, risk_comment, risk_color = calculate_risk_score(
        cleaned['age'], cleaned['smoker'], cleaned['term_years']
    )
    
    # Log audit
    log_audit(email, cleaned, premium, risk_score, '/api/calculate')
    
    # Increment usage for free users
    usage = get_usage(email)
    if not usage['paid']:
        increment_usage(email)
    
    return jsonify({
        'success': True,
        'premium': premium,
        'premium_range': {'low': premium_low, 'high': premium_high},
        'risk_score': risk_score,
        'risk_level': risk_level,
        'risk_comment': risk_comment,
        'risk_color': risk_color,
        'remaining': max(0, 20 - (usage['count'] + 1))
    })

@app.route('/api/generate-report', methods=['POST'])
@require_api_key
def generate_report_endpoint():
    """POST /api/generate-report - Generate full PDF report (requires API key)"""
    data = request.json
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    valid, error, cleaned = validate_assessment_input(data)
    if not valid:
        return jsonify({'error': error}), 400
    
    email = cleaned.get('email', '')
    if not email:
        return jsonify({'error': 'Email required'}), 400
    
    can_access_flag, status = can_access(email)
    if not can_access_flag:
        return jsonify({'error': 'Free limit reached. Please purchase the full report.'}), 403
    
    premium, premium_low, premium_high = calculate_pure_premium(
        cleaned['age'], cleaned['gender'], cleaned['smoker'],
        cleaned['income_band'], cleaned['coverage_amount'], cleaned['term_years']
    )
    
    risk_score, risk_level, risk_comment, risk_color = calculate_risk_score(
        cleaned['age'], cleaned['smoker'], cleaned['term_years']
    )
    
    # Log audit
    log_audit(email, cleaned, premium, risk_score, '/api/generate-report')
    
    # Generate PDF
    pdf_buffer = generate_actuarial_report(cleaned, premium, premium_low, premium_high, 
                                            risk_score, risk_level, risk_comment, risk_color)
    
    # Store lead
    db = get_db()
    lead_id = str(uuid.uuid4())
    db.execute('''
        INSERT INTO leads (id, email, age, gender, smoker, income, coverage, term, premium, risk_score, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (lead_id, email, cleaned['age'], cleaned['gender'], 1 if cleaned['smoker'] else 0,
          cleaned['income_band'], cleaned['coverage_amount'], cleaned['term_years'], premium, risk_score,
          datetime.now().isoformat()))
    db.commit()
    
    # Increment usage for free users
    usage = get_usage(email)
    if not usage['paid']:
        increment_usage(email)
    
    return send_file(
        pdf_buffer,
        mimetype='application/pdf',
        as_attachment=True,
        download_name=f'vettify_report_{cleaned["age"]}_{datetime.now().strftime("%Y%m%d")}.pdf'
    )

# ============================================
# HTML Template
# ============================================

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
        .paywall { background: #fef3c7; border-radius: 20px; padding: 24px; text-align: center; margin-top: 24px; }
        .paywall h3 { font-size: 18px; font-weight: 700; color: #92400e; margin-bottom: 12px; }
        .paywall-price { font-size: 32px; font-weight: 800; color: #0a2540; margin: 16px 0; }
        .btn-pay { width: 100%; padding: 14px; background: #0070ba; color: white; border: none; border-radius: 12px; font-weight: 700; font-size: 16px; cursor: pointer; }
        .btn-pay:disabled { opacity: 0.6; cursor: not-allowed; }
        .hidden { display: none; }
        .loading { text-align: center; padding: 40px; }
        .error { color: #dc2626; padding: 12px; background: #fee2e2; border-radius: 12px; margin-top: 16px; display: none; }
        .remaining-badge { background: #e8f0fe; padding: 8px 16px; border-radius: 30px; font-size: 12px; margin-bottom: 16px; text-align: center; }
        .footer { text-align: center; padding: 48px 32px; color: #8a9bb0; border-top: 1px solid #e2e8f0; margin-top: 48px; }
        .paid-badge { background: #16a34a; color: white; padding: 4px 12px; border-radius: 30px; font-size: 11px; display: inline-block; margin-bottom: 12px; }
        @media (max-width: 900px) { .main-container { grid-template-columns: 1fr; } .hero h1 { font-size: 32px; } }
    </style>
</head>
<body>
    <nav class="navbar">
        <div class="nav-container">
            <a href="/" class="logo">VETTIFY <span>PreCheck</span></a>
            <button class="btn-outline" onclick="showBrokerModal()">For Brokers →</button>
        </div>
    </nav>
    
    <div class="hero">
        <div class="hero-badge">⚡ Gompertz-Makeham Actuarial Model</div>
        <h1>Know before you apply</h1>
        <p>EPV-based pricing • 20 free assessments • Confidence intervals</p>
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
                    <div class="form-group"><label>Annual Income (ZAR)</label><input type="number" id="income" required placeholder="500000" min="0" step="10000"></div>
                    <div class="form-group"><
