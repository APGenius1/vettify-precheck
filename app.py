from flask import Flask, request, jsonify, send_file, render_template_string
from flask_cors import CORS
import io
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from datetime import datetime, timedelta
import os, uuid, math, sqlite3

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
    conn.execute("""CREATE TABLE IF NOT EXISTS leads (
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
    )""")
    conn.commit()
    conn.close()

init_db()

# ================= ACTUARIAL CORE =================
G_A, G_B, G_C = 0.00022, 0.000027, 0.092

def force_mortality(age):
    return G_A + G_B * math.exp(G_C * age)

def smoker_mult(age):
    return 2.5 if age < 30 else 2.2 if age < 40 else 1.9 if age < 50 else 1.6 if age < 60 else 1.4

def qx(age, smoker):
    mu = force_mortality(age)
    if smoker:
        mu *= smoker_mult(age)
    return 1 - math.exp(-mu / 12)

def epv_benefit(cov, age, term, smoker):
    v = 1 / (1 + 0.06 / 12)
    epv, surv = 0, 1
    for m in range(1, term * 12 + 1):
        a = age + (m - 1)//12
        q = qx(a, smoker)
        epv += (v**m) * surv * q * cov
        surv *= (1 - q)
    return epv

def epv_prem(age, term, smoker):
    v = 1 / (1 + 0.06 / 12)
    epv, surv = 0, 1
    for m in range(1, term * 12 + 1):
        a = age + (m - 1)//12
        q = qx(a, smoker)
        epv += (v**(m-1)) * surv
        surv *= (1 - q)
    return epv

def premium_calc(age, gender, smoker, income, coverage, term):
    p = epv_benefit(coverage, age, term, smoker) / max(epv_prem(age, term, smoker), 1)

    if gender == "male":
        p *= 1.12

    ratio = coverage / income if income else 10
    if ratio > 4:
        p *= 1 + min(0.6, (ratio - 4) * 0.1)

    return max(80, min(15000, round(p)))

# ================= SALES-OPTIMISED UNDERWRITING ENGINE =================
def underwriting_engine(age, smoker, coverage, income, term, premium):
    ratio = coverage / income if income else 10

    score = 70
    urgency = "Low"
    convertibility = 70
    hook = []
    verdict = ""

    # Age layer
    if age > 60:
        score -= 20
        convertibility -= 15
        hook.append("Age-driven underwriting tightening likely")
    elif age > 45:
        score -= 10

    # Smoker layer
    if smoker:
        score -= 30
        convertibility -= 25
        urgency = "High"
        hook.append("Smoker load may materially increase premium")

    # Financial strain signal
    if ratio > 8:
        score -= 15
        convertibility -= 20
        urgency = "High"
        hook.append("Coverage exceeds affordability norms")

    # Term risk
    if term > 25:
        score -= 5

    # Final classification
    score = max(10, min(95, score))

    if score >= 70:
        verdict = "Highly Insurable – Standard market acceptance expected"
    elif score >= 40:
        verdict = "Moderate Insurability – Some underwriting friction expected"
    else:
        verdict = "High Friction – Specialist underwriting likely required"

    # Sales CTA logic
    if convertibility >= 75:
        cta = "Strong conversion probability. Proceed immediately."
    elif convertibility >= 50:
        cta = "Good candidate. Pre-underwrite before submission."
    else:
        cta = "High decline risk. Re-structure cover before applying."

    return {
        "score": score,
        "convertibility": convertibility,
        "urgency": urgency,
        "verdict": verdict,
        "cta": cta,
        "hooks": hook
    }

# ================= RISK ENGINE =================
def risk_score(age, smoker, coverage, income, term):
    score = 70
    drivers = []

    if smoker:
        score -= 30
        drivers.append({"factor": "Smoker", "impact": -30, "explanation": "Increased mortality risk"})

    if age > 55:
        score -= 12
    elif age < 30:
        score += 5

    ratio = coverage / income if income else 0
    if ratio > 8:
        score -= 15

    if term > 25:
        score -= 5

    score = max(10, min(95, score))

    level = "Low" if score >= 70 else "Moderate" if score >= 40 else "High"

    return {
        "score": score,
        "level": level,
        "drivers": drivers
    }

# ================= MARKET =================
def market(premium, age):
    pct = 45 if age < 30 else 55 if age < 45 else 48
    return {
        "min": round(premium * 0.88),
        "max": round(premium * 1.12),
        "percentile": pct,
        "confidence": 12
    }

def insurers(score, smoker):
    if smoker:
        return ["Momentum", "BrightRock"], "Smoker specialist pathways recommended"
    if score >= 70:
        return ["Discovery", "Old Mutual", "Momentum"], "Top-tier underwriting bands"
    return ["Old Mutual", "Hollard"], "Standard/specialist mix recommended"

# ================= PDF ENGINE (UPGRADED SALES VERSION) =================
def generate_pdf(data, premium, risk, market_data, underwrite, insurer_list, insurer_note):

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    story = []

    blue = colors.HexColor("#0a2540")
    risk_color = colors.green if risk["score"] > 70 else colors.orange if risk["score"] > 40 else colors.red

    report_id = str(uuid.uuid4())[:8]

    # HEADER
    story.append(Paragraph("VETTIFY PRECHECK", ParagraphStyle("t", fontSize=26, textColor=blue, alignment=1)))
    story.append(Paragraph("Actuarial + Sales Intelligence Report", styles["Normal"]))
    story.append(Spacer(1, 0.2*inch))

    story.append(Paragraph(f"<b>Report ID:</b> {report_id}", styles["Normal"]))
    story.append(Paragraph(f"<b>Valid:</b> 7 days", styles["Normal"]))
    story.append(Spacer(1, 0.2*inch))

    # EXEC SUMMARY (SALES CORE)
    story.append(Paragraph("EXECUTIVE SUMMARY", styles["Heading2"]))
    story.append(Paragraph(
        f"Insurability Verdict: <b>{underwrite['verdict']}</b><br/>"
        f"Conversion Outlook: <b>{underwrite['cta']}</b>",
        styles["Normal"]
    ))
    story.append(Spacer(1, 0.15*inch))

    # RISK SCORE
    story.append(Paragraph("RISK SCORE", styles["Heading2"]))
    story.append(Paragraph(
        f"<font size=48><b>{risk['score']}</b></font>/100",
        ParagraphStyle("r", alignment=1, textColor=risk_color)
    ))
    story.append(Paragraph(risk["level"], styles["Normal"]))
    story.append(Spacer(1, 0.2*inch))

    # PREMIUM
    story.append(Paragraph("PREMIUM ESTIMATE", styles["Heading2"]))
    story.append(Paragraph(f"<b>R{premium}/month</b>", styles["Normal"]))
    story.append(Paragraph(f"Market Range: R{market_data['min']} - R{market_data['max']}", styles["Normal"]))
    story.append(Spacer(1, 0.2*inch))

    # SALES INTELLIGENCE BLOCK
    story.append(Paragraph("SALES INTELLIGENCE", styles["Heading2"]))
    for h in underwrite["hooks"]:
        story.append(Paragraph(f"• {h}", styles["Normal"]))
    story.append(Paragraph(f"<b>Urgency:</b> {underwrite['urgency']}", styles["Normal"]))
    story.append(Paragraph(f"<b>Convertibility Score:</b> {underwrite['convertibility']}/100", styles["Normal"]))
    story.append(Spacer(1, 0.2*inch))

    # INSURERS
    story.append(Paragraph("INSURER MATCHING", styles["Heading2"]))
    story.append(Paragraph(", ".join(insurer_list), styles["Normal"]))
    story.append(Paragraph(insurer_note, styles["Normal"]))

    doc.build(story)
    buffer.seek(0)
    return buffer

# ================= ROUTES =================
@app.route("/calculate", methods=["POST"])
def calculate():
    d = request.json

    prem = premium_calc(d["age"], d["gender"], d["smoker"], d["income"], d["coverage"], d["term"])
    risk = risk_score(d["age"], d["smoker"], d["coverage"], d["income"], d["term"])
    market_data = market(prem, d["age"])
    insurers_list, note = insurers(risk["score"], d["smoker"])
    underwrite = underwriting_engine(d["age"], d["smoker"], d["coverage"], d["income"], d["term"], prem)

    return jsonify({
        "premium": prem,
        "risk": risk,
        "market": market_data,
        "insurers": insurers_list,
        "note": note,
        "underwriting": underwrite
    })

@app.route("/generate-report", methods=["POST"])
def report():
    d = request.json

    prem = premium_calc(d["age"], d["gender"], d["smoker"], d["income"], d["coverage"], d["term"])
    risk = risk_score(d["age"], d["smoker"], d["coverage"], d["income"], d["term"])
    market_data = market(prem, d["age"])
    insurers_list, note = insurers(risk["score"], d["smoker"])
    underwrite = underwriting_engine(d["age"], d["smoker"], d["coverage"], d["income"], d["term"], prem)

    pdf = generate_pdf(d, prem, risk, market_data, underwrite, insurers_list, note)

    return send_file(pdf, as_attachment=True, download_name="vettify_report.pdf")

# ================= RUN =================
if __name__ == "__main__":
    app.run(debug=True)
