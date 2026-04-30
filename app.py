from flask import Flask, request, jsonify, send_file, render_template_string
from flask_cors import CORS
from functools import wraps
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
import logging
from typing import Dict, List, Tuple, Any, Optional
from dataclasses import dataclass, asdict
from contextlib import contextmanager

# ================= CONFIGURATION =================
class Config:
    DATABASE = "vettify.db"
    INTEREST_RATE = 0.06
    MONTHS_PER_YEAR = 12
    MIN_PREMIUM = 80
    MAX_PREMIUM = 15000
    GENDER_MULTIPLIER_MALE = 1.12
    MAX_RATIO_ADJUSTMENT = 0.6
    RATIO_THRESHOLD = 4
    RATIO_INCREMENT = 0.1
    CONFIDENCE_MARGIN = 0.12
    CACHE_TIMEOUT = 300
    
    G_A, G_B, G_C = 0.00022, 0.000027, 0.092
    
    SMOKER_MULTIPLIERS = [
        (30, 2.5), (40, 2.2), (50, 1.9), (60, 1.6), (float('inf'), 1.4)
    ]
    
    BASE_RISK_SCORE = 70
    SMOKER_PENALTY = 30
    AGE_PENALTY_OVER_55 = 12
    AGE_BONUS_UNDER_30 = 5
    RATIO_PENALTY_THRESHOLD = 8
    RATIO_PENALTY = 15
    TERM_PENALTY_THRESHOLD = 25
    TERM_PENALTY = 5
    MIN_RISK_SCORE = 10
    MAX_RISK_SCORE = 95
    
    RISK_LEVEL_LOW = 70
    RISK_LEVEL_MODERATE = 40

app = Flask(__name__)
app.config.from_object(Config)
app.secret_key = os.urandom(24).hex()
CORS(app)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ================= DATA CLASSES =================
@dataclass
class PolicyInput:
    age: int
    gender: str
    smoker: bool
    income: float
    coverage: float
    term: int
    
    def validate(self) -> Tuple[bool, Optional[str]]:
        if not 18 <= self.age <= 80:
            return False, "Age must be between 18 and 80"
        if self.gender not in ['male', 'female']:
            return False, "Gender must be 'male' or 'female'"
        if self.income <= 0:
            return False, "Income must be positive"
        if self.coverage <= 0:
            return False, "Coverage must be positive"
        if not 1 <= self.term <= 40:
            return False, "Term must be between 1 and 40 years"
        if self.coverage > self.income * 15:
            return False, "Coverage exceeds reasonable limits (max 15x income)"
        return True, None

@dataclass
class RiskScore:
    score: int
    level: str
    drivers: List[Dict[str, Any]]

@dataclass
class UnderwritingSummary:
    risk_score: int
    risk_level: str
    risk_explanation: str
    premium: int
    confidence_range: Dict[str, Any]
    coverage_ratio: str
    coverage_interpretation: str

# ================= DATABASE =================
@contextmanager
def get_db():
    conn = sqlite3.connect(Config.DATABASE)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

def init_db():
    try:
        with get_db() as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS usage (
                email TEXT PRIMARY KEY,
                count INTEGER DEFAULT 0,
                paid BOOLEAN DEFAULT 0,
                first_use TEXT,
                last_use TEXT,
                total_calculations INTEGER DEFAULT 0
            )""")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_last_use ON usage(last_use)")
            conn.commit()
        logger.info("Database initialized successfully")
    except sqlite3.Error as e:
        logger.error(f"Database initialization failed: {e}")

# ================= CACHE =================
class PremiumCache:
    def __init__(self, timeout: int = Config.CACHE_TIMEOUT):
        self._cache = {}
        self.timeout = timeout
    
    def _make_key(self, age: int, gender: str, smoker: bool, income: float, 
                  coverage: float, term: int) -> str:
        return f"{age}_{gender}_{smoker}_{income:.2f}_{coverage:.2f}_{term}"
    
    def get(self, age: int, gender: str, smoker: bool, income: float, 
            coverage: float, term: int) -> Optional[int]:
        key = self._make_key(age, gender, smoker, income, coverage, term)
        if key in self._cache:
            value, timestamp = self._cache[key]
            if (datetime.now() - timestamp).seconds < self.timeout:
                return value
            del self._cache[key]
        return None
    
    def set(self, age: int, gender: str, smoker: bool, income: float, 
            coverage: float, term: int, premium: int):
        key = self._make_key(age, gender, smoker, income, coverage, term)
        self._cache[key] = (premium, datetime.now())

premium_cache = PremiumCache()

# ================= ACTUARIAL CORE =================
def get_smoker_multiplier(age: int) -> float:
    for max_age, multiplier in Config.SMOKER_MULTIPLIERS:
        if age < max_age:
            return multiplier
    return 1.4

def force_mortality(age: int) -> float:
    return Config.G_A + Config.G_B * math.exp(Config.G_C * age)

def calculate_qx(age: int, smoker: bool) -> float:
    mu = force_mortality(age)
    if smoker:
        mu *= get_smoker_multiplier(age)
    return 1 - math.exp(-mu / Config.MONTHS_PER_YEAR)

def epv_benefit(coverage: float, age: int, term: int, smoker: bool) -> float:
    v = 1 / (1 + Config.INTEREST_RATE / Config.MONTHS_PER_YEAR)
    epv = 0.0
    surv = 1.0
    
    for month in range(term * Config.MONTHS_PER_YEAR):
        current_age = age + month // Config.MONTHS_PER_YEAR
        qx_val = calculate_qx(current_age, smoker)
        epv += (v ** (month + 1)) * surv * qx_val * coverage
        surv *= (1 - qx_val)
    
    return epv

def epv_premium(age: int, term: int, smoker: bool) -> float:
    v = 1 / (1 + Config.INTEREST_RATE / Config.MONTHS_PER_YEAR)
    epv = 0.0
    surv = 1.0
    
    for month in range(term * Config.MONTHS_PER_YEAR):
        current_age = age + month // Config.MONTHS_PER_YEAR
        epv += (v ** month) * surv
        surv *= (1 - calculate_qx(current_age, smoker))
    
    return epv

def calculate_base_premium(age: int, gender: str, smoker: bool, 
                          income: float, coverage: float, term: int) -> int:
    cached = premium_cache.get(age, gender, smoker, income, coverage, term)
    if cached:
        return cached
    
    epv_ben = epv_benefit(coverage, age, term, smoker)
    epv_prem_val = epv_premium(age, term, smoker)
    
    if epv_prem_val < 1e-6:
        raise ValueError("EPV of premium too small")
    
    premium = epv_ben / epv_prem_val
    
    if gender == "male":
        premium *= Config.GENDER_MULTIPLIER_MALE
    
    ratio = coverage / income if income > 0 else 10
    if ratio > Config.RATIO_THRESHOLD:
        adjustment = 1 + min(Config.MAX_RATIO_ADJUSTMENT, 
                           (ratio - Config.RATIO_THRESHOLD) * Config.RATIO_INCREMENT)
        premium *= adjustment
    
    final_premium = max(Config.MIN_PREMIUM, min(Config.MAX_PREMIUM, round(premium)))
    premium_cache.set(age, gender, smoker, income, coverage, term, final_premium)
    
    return final_premium

# ================= RISK ENGINE =================
def get_risk_explanation(score: int) -> str:
    if score >= Config.RISK_LEVEL_LOW:
        return "Strong profile: standard mortality, minimal underwriting friction, likely straight-through approval."
    elif score >= Config.RISK_LEVEL_MODERATE:
        return "Moderate profile: expect underwriting questions and possible loadings."
    return "High-risk profile: specialist underwriting required, possible medical evidence."

def calculate_risk_score(age: int, smoker: bool, coverage: float, 
                        income: float, term: int) -> RiskScore:
    score = Config.BASE_RISK_SCORE
    drivers = []
    
    if smoker:
        score -= Config.SMOKER_PENALTY
        drivers.append({
            "factor": "Smoker",
            "impact": -Config.SMOKER_PENALTY,
            "explanation": "Increased mortality risk"
        })
    
    if age > 55:
        score -= Config.AGE_PENALTY_OVER_55
        drivers.append({
            "factor": "Age > 55",
            "impact": -Config.AGE_PENALTY_OVER_55,
            "explanation": "Higher mortality risk at advanced age"
        })
    elif age < 30:
        score += Config.AGE_BONUS_UNDER_30
        drivers.append({
            "factor": "Age < 30",
            "impact": Config.AGE_BONUS_UNDER_30,
            "explanation": "Lower mortality risk at younger age"
        })
    
    ratio = coverage / income if income > 0 else 0
    if ratio > Config.RATIO_PENALTY_THRESHOLD:
        score -= Config.RATIO_PENALTY
        drivers.append({
            "factor": "High coverage ratio",
            "impact": -Config.RATIO_PENALTY,
            "explanation": f"Coverage {ratio:.1f}x income exceeds typical limits"
        })
    
    if term > Config.TERM_PENALTY_THRESHOLD:
        score -= Config.TERM_PENALTY
        drivers.append({
            "factor": "Long term",
            "impact": -Config.TERM_PENALTY,
            "explanation": "Extended policy duration increases risk"
        })
    
    score = max(Config.MIN_RISK_SCORE, min(Config.MAX_RISK_SCORE, score))
    
    if score >= Config.RISK_LEVEL_LOW:
        level = "Low"
    elif score >= Config.RISK_LEVEL_MODERATE:
        level = "Moderate"
    else:
        level = "High"
    
    return RiskScore(score=score, level=level, drivers=drivers)

def insurer_match(score: int, smoker: bool) -> Tuple[List[str], str]:
    if smoker:
        return ["Momentum", "BrightRock"], "Smoker pricing applies; specialist underwriting required."
    
    if score >= Config.RISK_LEVEL_LOW:
        return ["Discovery", "Momentum", "Old Mutual", "Sanlam"], "Top-tier underwriting bands."
    elif score >= Config.RISK_LEVEL_MODERATE:
        return ["Old Mutual", "Momentum"], "Standard underwriting expected."
    else:
        return ["Hollard", "BrightRock"], "Restricted underwriting pool."

def get_market_comparison(premium: int, age: int) -> Dict[str, Any]:
    confidence = Config.CONFIDENCE_MARGIN
    return {
        "min": round(premium * (1 - confidence)),
        "max": round(premium * (1 + confidence)),
        "percentile": 45 if age < 30 else 55 if age < 45 else 48,
        "confidence": round(confidence * 100)
    }

def create_underwriting_summary(premium: int, risk: RiskScore, age: int, 
                                coverage: float, income: float) -> UnderwritingSummary:
    ratio = coverage / income if income > 0 else 0
    confidence_margin = Config.CONFIDENCE_MARGIN
    
    return UnderwritingSummary(
        risk_score=risk.score,
        risk_level=risk.level,
        risk_explanation=get_risk_explanation(risk.score),
        premium=premium,
        confidence_range={
            "low": int(premium * (1 - confidence_margin)),
            "high": int(premium * (1 + confidence_margin)),
            "confidence": f"±{round(confidence_margin * 100)}%"
        },
        coverage_ratio=f"{round(ratio, 1)}x income",
        coverage_interpretation=(
            "Within norms" if ratio <= 4 else
            "Elevated risk" if ratio <= 8 else
            "High strain loading expected"
        )
    )

# ================= DECORATORS =================
def validate_policy_input(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        data = request.json
        if not data:
            return jsonify({"error": "No input data provided"}), 400
        
        try:
            policy_input = PolicyInput(
                age=int(data.get("age", 0)),
                gender=data.get("gender", "").lower(),
                smoker=bool(data.get("smoker", False)),
                income=float(data.get("income", 0)),
                coverage=float(data.get("coverage", 0)),
                term=int(data.get("term", 0))
            )
            
            is_valid, error_msg = policy_input.validate()
            if not is_valid:
                return jsonify({"error": error_msg}), 400
            
            request.policy_input = policy_input
            return f(*args, **kwargs)
            
        except (ValueError, TypeError) as e:
            logger.error(f"Input validation error: {e}")
            return jsonify({"error": f"Invalid input format: {str(e)}"}), 400
    
    return decorated_function

def handle_errors(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except Exception as e:
            logger.error(f"Error in {f.__name__}: {str(e)}", exc_info=True)
            return jsonify({"error": "An internal error occurred", "details": str(e)}), 500
    return decorated_function

# ================= API ENDPOINTS =================
@app.route("/health", methods=["GET"])
def health_check():
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "2.0.0"
    })

@app.route("/calculate", methods=["POST"])
@validate_policy_input
@handle_errors
def calculate():
    policy = request.policy_input
    
    premium = calculate_base_premium(
        policy.age, policy.gender, policy.smoker,
        policy.income, policy.coverage, policy.term
    )
    
    risk = calculate_risk_score(
        policy.age, policy.smoker,
        policy.coverage, policy.income, policy.term
    )
    
    market_data = get_market_comparison(premium, policy.age)
    insurers, note = insurer_match(risk.score, policy.smoker)
    underwriting = create_underwriting_summary(
        premium, risk, policy.age, policy.coverage, policy.income
    )
    
    return jsonify({
        "premium": premium,
        "risk": asdict(risk),
        "market": market_data,
        "insurers": insurers,
        "insurer_note": note,
        "underwriting": asdict(underwriting)
    })

@app.route("/generate-report", methods=["POST"])
@validate_policy_input
@handle_errors
def generate_report():
    policy = request.policy_input
    
    premium = calculate_base_premium(
        policy.age, policy.gender, policy.smoker,
        policy.income, policy.coverage, policy.term
    )
    
    risk = calculate_risk_score(
        policy.age, policy.smoker,
        policy.coverage, policy.income, policy.term
    )
    
    insurers, note = insurer_match(risk.score, policy.smoker)
    underwriting = create_underwriting_summary(
        premium, risk, policy.age, policy.coverage, policy.income
    )
    
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    
    story = []
    story.append(Paragraph("VETTIFY UNDERWRITING REPORT", styles["Heading1"]))
    story.append(Spacer(1, 0.2*inch))
    story.append(Paragraph(f"<b>Risk:</b> {underwriting.risk_score} / 100", styles["Normal"]))
    story.append(Paragraph(f"<b>Insight:</b> {underwriting.risk_explanation}", styles["Normal"]))
    story.append(Spacer(1, 0.1*inch))
    story.append(Paragraph(f"<b>Premium:</b> R{premium}", styles["Normal"]))
    story.append(Paragraph(
        f"Range: R{underwriting.confidence_range['low']} – R{underwriting.confidence_range['high']} ({underwriting.confidence_range['confidence']})",
        styles["Normal"]
    ))
    story.append(Spacer(1, 0.1*inch))
    story.append(Paragraph(f"<b>Coverage Ratio:</b> {underwriting.coverage_ratio}", styles["Normal"]))
    story.append(Paragraph(underwriting.coverage_interpretation, styles["Normal"]))
    story.append(Spacer(1, 0.2*inch))
    story.append(Paragraph("<b>Insurers:</b> " + ", ".join(insurers), styles["Normal"]))
    story.append(Paragraph(note, styles["Normal"]))
    
    doc.build(story)
    buffer.seek(0)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"vettify_report_{timestamp}.pdf"
    
    return send_file(
        buffer,
        as_attachment=True,
        download_name=filename,
        mimetype='application/pdf'
    )

# ================= NEW DASHBOARD ROUTES =================
@app.route("/")
@app.route("/dashboard")
def dashboard():
    """Serve the main dashboard"""
    with open('dashboard.html', 'r') as f:
        return f.read()

@app.route("/api/stats", methods=["GET"])
@handle_errors
def get_stats():
    """Get system statistics for dashboard"""
    with get_db() as conn:
        cursor = conn.execute("SELECT COUNT(*) as total, SUM(count) as total_calc FROM usage")
        stats = cursor.fetchone()
        
        cursor = conn.execute("""
            SELECT COUNT(*) as today_count 
            FROM usage 
            WHERE last_use >= date('now', '-1 day')
        """)
        today = cursor.fetchone()
        
        return jsonify({
            "total_users": stats['total'] or 0,
            "total_calculations": stats['total_calc'] or 0,
            "today_quotes": today['today_count'] or 0,
            "timestamp": datetime.now().isoformat()
        })

@app.route("/api/compare", methods=["POST"])
@validate_policy_input
@handle_errors
def compare_scenarios():
    """Compare multiple scenarios"""
    policy = request.policy_input
    scenarios = []
    
    coverage_options = [policy.coverage * 0.5, policy.coverage, policy.coverage * 1.5]
    
    for cov in coverage_options:
        premium = calculate_base_premium(
            policy.age, policy.gender, policy.smoker,
            policy.income, cov, policy.term
        )
        scenarios.append({
            "coverage": cov,
            "premium": premium,
            "ratio": round(cov / policy.income, 1)
        })
    
    return jsonify({
        "base_scenario": asdict(policy),
        "comparisons": scenarios
    })

# ================= RUN APPLICATION =================
if __name__ == "__main__":
    init_db()
    app.run(debug=True, host='0.0.0.0', port=5000)
