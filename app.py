from flask import Flask, request, jsonify, send_file, render_template_string
from flask_cors import CORS
import io
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from datetime import datetime
import os
import uuid
import sqlite3
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

app = Flask(__name__)
app.secret_key = os.urandom(24).hex()
CORS(app)

# Email config
EMAIL_ADDRESS = "vettifyprecheck@gmail.com"
EMAIL_PASSWORD = "Isefbuqadsreulbb"

def send_email_notification(application_data):
    try:
        msg = MIMEMultipart()
        msg['From'] = EMAIL_ADDRESS
        msg['To'] = EMAIL_ADDRESS
        msg['Subject'] = f"New Application - {application_data['full_name']}"
        body = f"Name: {application_data['full_name']}\nEmail: {application_data['email']}\nPosition: {application_data['position']}\nLinkedIn: {application_data['linkedin_url']}\n\nSubmitted: {datetime.now()}"
        msg.attach(MIMEText(body, 'plain'))
        server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        print(f"Email error: {str(e)}")
        return False

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

# ================= PERCEPTION SCORE ENGINE =================
# 4 signals only: Authority, Narrative, Visibility, Validation

def analyze_authority_signal(text):
    """Analyze authority positioning from profile text"""
    score = 68
    reasons = []
    fixes = []
    
    # Check for decision-making language
    decision_words = ['decide', 'lead', 'direct', 'oversee', 'responsible for', 'accountable']
    ownership_words = ['founder', 'built', 'created', 'launched', 'founded']
    
    has_decision = any(word in text.lower() for word in decision_words)
    has_ownership = any(word in text.lower() for word in ownership_words)
    
    if not has_decision:
        score -= 12
        reasons.append("Missing decision-making language")
        fixes.append("Add phrases like 'I decide on X' or 'Lead Y'")
    if not has_ownership:
        score -= 8
        reasons.append("Weak ownership framing")
        fixes.append("Use ownership verbs: 'founded', 'built', 'created'")
    
    if len(reasons) == 0:
        reasons.append("Competence-focused but not authority-focused")
        fixes.append("Reframe from 'I do' to 'I decide' language")
    
    return {
        'score': max(0, min(100, score)),
        'level': 'Weak Consistency' if score < 70 else 'Moderate' if score < 85 else 'Strong',
        'reasons': reasons[:2],
        'fixes': fixes[:2]
    }

def analyze_narrative_alignment(text):
    """Analyze narrative consistency"""
    score = 71
    reasons = []
    fixes = []
    
    # Check for unified positioning
    has_clear_position = len(text.split()) > 50 if text else False
    
    if not has_clear_position:
        score -= 10
        reasons.append("No clear single positioning statement")
        fixes.append("Create a master bio (60-80 words) that defines your core narrative")
    
    # Check for fragmented signals
    if 'also' in text.lower() or 'additionally' in text.lower():
        score -= 5
        reasons.append("Multiple competing narratives dilute your positioning")
        fixes.append("Focus on ONE core story across all platforms")
    
    if len(reasons) == 0:
        reasons.append("Fragmented signal across platforms")
        fixes.append("Ensure LinkedIn, website, speaker bios tell the same story")
    
    return {
        'score': max(0, min(100, score)),
        'level': 'Fragmented Signal' if score < 75 else 'Aligned',
        'reasons': reasons[:2],
        'fixes': fixes[:2]
    }

def analyze_visibility_footprint(text):
    """Analyze visibility and third-party validation"""
    score = 59
    reasons = []
    fixes = []
    
    # Check for media mentions, speaking, publications
    media_indicators = ['spoke at', 'presented at', 'keynote', 'published', 'article', 'interview', 'podcast']
    has_media = any(word in text.lower() for word in media_indicators)
    
    if not has_media:
        score -= 15
        reasons.append("No visible speaking engagements or media presence")
        fixes.append("Target 1 bylined article or podcast appearance in 90 days")
    
    # Check for associations
    assoc_indicators = ['board', 'advisor', 'member', 'fellow', 'committee']
    has_associations = any(word in text.lower() for word in assoc_indicators)
    
    if not has_associations:
        score -= 8
        reasons.append("Missing visible association markers")
        fixes.append("Add advisory roles, board seats, or selective memberships")
    
    if len(reasons) == 0:
        reasons.append("Limited third-party validation footprint")
        fixes.append("Secure 2-3 credible mentions (media, podcast, panel)")
    
    return {
        'score': max(0, min(100, score)),
        'level': 'Under-Optimised' if score < 70 else 'Building' if score < 85 else 'Strong',
        'reasons': reasons[:2],
        'fixes': fixes[:2]
}

def analyze_validation_signal(text):
    """Analyze third-party validation"""
    score = 65
    reasons = []
    fixes = []
    
    # Check for social proof
    social_indicators = ['recommend', 'endorse', 'work with', 'client', 'partner']
    has_social = any(word in text.lower() for word in social_indicators)
    
    if not has_social:
        score -= 10
        reasons.append("No visible social proof or endorsements")
        fixes.append("Collect LinkedIn recommendations from credible sources")
    
    return {
        'score': max(0, min(100, score)),
        'level': 'Under-Optimised' if score < 70 else 'Moderate',
        'reasons': reasons[:2],
        'fixes': fixes[:2]
    }

# ================= PERCEPTION GAP REPORT =================

def generate_perception_gap_report(client_data, profile_text):
    """Generate the core product: Perception Gap Report"""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, 
                           topMargin=72, bottomMargin=72, 
                           leftMargin=72, rightMargin=72)
    styles = getSampleStyleSheet()
    story = []
    
    # Styles
    title_style = ParagraphStyle('Title', parent=styles['Title'], fontSize=24, textColor=colors.HexColor('#0a1628'), alignment=1, spaceAfter=6, fontName='Helvetica-Bold')
    section_header = ParagraphStyle('SectionHeader', parent=styles['Heading2'], fontSize=13, textColor=colors.HexColor('#0a1628'), spaceAfter=10, spaceBefore=16, fontName='Helvetica-Bold')
    body_text = ParagraphStyle('BodyText', parent=styles['Normal'], fontSize=10, textColor=colors.HexColor('#2c3e50'), spaceAfter=6, leading=15)
    highlight = ParagraphStyle('Highlight', parent=styles['Normal'], fontSize=10, textColor=colors.HexColor('#c9a03d'), spaceAfter=6, leading=15, fontName='Helvetica-Bold')
    
    # Run analysis
    authority = analyze_authority_signal(profile_text)
    narrative = analyze_narrative_alignment(profile_text)
    visibility = analyze_visibility_footprint(profile_text)
    validation = analyze_validation_signal(profile_text)
    
    # Calculate scores
    scores = {
        'Authority Positioning': authority['score'],
        'Narrative Alignment': narrative['score'],
        'Visibility Footprint': visibility['score'],
        'Third-Party Validation': validation['score']
    }
    overall_score = sum(scores.values()) / 4
    
    # Determine perceived vs target level
    if overall_score >= 85:
        perceived_level = "Decision-Maker"
        target_level = "Strategic Leader"
        gap = "Small - refinement needed"
    elif overall_score >= 70:
        perceived_level = "Operator/Contributor"
        target_level = "Decision-Maker"
        gap = "Moderate - authority signals weak"
    else:
        perceived_level = "Individual Contributor"
        target_level = "Operator/Decision-Maker"
        gap = "Large - foundational repositioning needed"
    
    client_name = client_data.get('full_name', 'Private Client')
    
    # ========== REPORT CONTENT ==========
    story.append(Paragraph("CONFIDENTIAL", ParagraphStyle('Confidential', parent=styles['Normal'], fontSize=8, textColor=colors.HexColor('#c9a03d'), alignment=2)))
    story.append(Spacer(1, 0.05*inch))
    story.append(Paragraph("VETTIFY INTELLIGENCE", title_style))
    story.append(Paragraph("Perception Gap Report", ParagraphStyle('Subtitle', parent=styles['Normal'], fontSize=9, textColor=colors.HexColor('#8a9bb0'), alignment=1)))
    story.append(Spacer(1, 0.1*inch))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#c9a03d')))
    story.append(Spacer(1, 0.15*inch))
    
    story.append(Paragraph(f"Prepared for: <b>{client_name}</b>", body_text))
    story.append(Paragraph(f"Date: {datetime.now().strftime('%d %B %Y')}", body_text))
    story.append(Spacer(1, 0.1*inch))
    
    # Perception Gap
    story.append(Paragraph("1. PERCEPTION GAP ANALYSIS", section_header))
    story.append(Paragraph(f"<b>Perceived Level:</b> {perceived_level}", body_text))
    story.append(Paragraph(f"<b>Target Level:</b> {target_level}", body_text))
    story.append(Paragraph(f"<b>Gap:</b> {gap}", highlight))
    story.append(Spacer(1, 0.05*inch))
    story.append(Paragraph(f"<b>Your Perception Score:</b> {int(overall_score)}/100", highlight))
    story.append(Spacer(1, 0.1*inch))
    
    # Benchmark comparison
    story.append(Paragraph("2. BENCHMARK COMPARISON", section_header))
    benchmark_data = [
        ["Your Score", f"{int(overall_score)}/100", ""],
        ["Industry Average (Founders)", "72/100", f"{'+' if overall_score > 72 else ''}{int(overall_score - 72)} vs avg"],
        ["Top 10% Tier", "88/100", f"Gap: {88 - int(overall_score)} points"],
    ]
    bench_table = Table(benchmark_data, colWidths=[2.0*inch, 1.2*inch, 2.5*inch])
    bench_table.setStyle(TableStyle([
        ('FONTNAME', (0,0), (-1,-1), 'Helvetica'),
        ('FONTSIZE', (0,0), (-1,-1), 9),
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#0a1628')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e2e8f0')),
        ('TOPPADDING', (0,0), (-1,-1), 8),
    ]))
    story.append(bench_table)
    story.append(Spacer(1, 0.15*inch))
    
    # Score breakdown with reasons and fixes
    story.append(Paragraph("3. SCORE BREAKDOWN & WHY", section_header))
    
    for signal, data in [('Authority Positioning', authority), ('Narrative Alignment', narrative), 
                          ('Visibility Footprint', visibility), ('Third-Party Validation', validation)]:
        story.append(Paragraph(f"<b>{signal}: {data['score']}/100</b>", body_text))
        story.append(Paragraph(f"Level: {data['level']}", body_text))
        story.append(Paragraph("<b>Why:</b> " + ", ".join(data['reasons']), body_text))
        story.append(Paragraph("<b>Fix:</b> " + ", ".join(data['fixes']), body_text))
        story.append(Spacer(1, 0.08*inch))
    
    story.append(Spacer(1, 0.1*inch))
    
    # Actionable fixes with points
    story.append(Paragraph("4. ACTIONABLE IMPROVEMENTS", section_header))
    
    actions = []
    actions.extend([(fix, "Authority") for fix in authority['fixes'][:1]])
    actions.extend([(fix, "Narrative") for fix in narrative['fixes'][:1]])
    actions.extend([(fix, "Visibility") for fix in visibility['fixes'][:1]])
    actions.extend([(fix, "Validation") for fix in validation['fixes'][:1]])
    
    points = [12, 8, 15, 6, 8, 5]
    action_data = [["Action", "Category", "Points", "Timeline"]]
    for i, (action, category) in enumerate(actions[:6]):
        action_data.append([action[:50] + "...", category, f"+{points[i] if i < len(points) else 5}", "30-60 days"])
    
    action_table = Table(action_data, colWidths=[2.5*inch, 1.0*inch, 0.8*inch, 0.8*inch])
    action_table.setStyle(TableStyle([
        ('FONTNAME', (0,0), (-1,-1), 'Helvetica'),
        ('FONTSIZE', (0,0), (-1,-1), 8),
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#0a1628')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e2e8f0')),
        ('TOPPADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(action_table)
    story.append(Spacer(1, 0.1*inch))
    story.append(Paragraph(f"<b>Total potential gain: +{sum(points[:len(actions)])} points → {min(100, int(overall_score) + sum(points[:len(actions)]))}/100 (Top tier)</b>", highlight))
    story.append(Spacer(1, 0.15*inch))
    
    # Cost of gap
    story.append(Paragraph("5. COST OF THIS GAP", section_header))
    story.append(Paragraph("• Slower trust-building with investors and partners", body_text))
    story.append(Paragraph("• Potential underestimation in competitive environments", body_text))
    story.append(Paragraph("• Missed opportunities that favor stronger authority signals", body_text))
    story.append(Spacer(1, 0.15*inch))
    
    # Footer
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor('#e2e8f0')))
    story.append(Paragraph(f"Confidential · Prepared for {client_name} · Valid for 60 days", 
                         ParagraphStyle('Footer', parent=styles['Normal'], fontSize=7, 
                                       textColor=colors.HexColor('#8a9bb0'), alignment=1)))
    
    doc.build(story)
    buffer.seek(0)
    return buffer

# ================= SAMPLE REPORT =================
@app.route('/download-sample-report')
def download_sample_report():
    sample_data = {'full_name': 'Sample Client', 'position': 'Executive'}
    sample_text = "I am a founder building a SaaS company. Previously worked in operations. Looking to raise capital and expand my network."
    pdf_buffer = generate_perception_gap_report(sample_data, sample_text)
    return send_file(pdf_buffer, as_attachment=True, download_name="perception_gap_report.pdf")

# ================= HOMEPAGE =================
@app.route('/')
def home():
    return render_template_string('''
<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>Vettify | Perception Intelligence</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
<style>
:root{--gold:#c9a03d;--dark:#0a1628;--cream:#faf8f5}
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'Inter',sans-serif;background:var(--cream);color:var(--dark)}
.container{max-width:1200px;margin:0 auto;padding:0 48px}
.navbar{padding:32px 0;border-bottom:1px solid rgba(0,0,0,0.05)}
.navbar .container{display:flex;justify-content:space-between;align-items:center}
.logo{font-size:24px;font-weight:700;color:var(--dark);text-decoration:none}
.logo span{font-weight:300;color:var(--gold)}
.badge{background:#e8d5a3;padding:4px 12px;border-radius:30px;font-size:10px}
.hero{padding:80px 0;text-align:center}
.hero h1{font-size:48px;font-weight:600;margin-bottom:20px}
.hero p{font-size:18px;color:#5b6e8c;max-width:600px;margin:0 auto}
.btn-primary{background:var(--dark);color:white;border:none;padding:14px 36px;font-size:14px;font-weight:500;cursor:pointer;margin-top:32px}
.btn-outline{background:transparent;border:1px solid var(--dark);padding:14px 36px;font-size:14px;cursor:pointer;margin-left:16px}
.pricing{padding:80px 0;background:white}
.pricing h2{text-align:center;font-size:32px;margin-bottom:48px}
.pricing-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:32px}
.pricing-card{background:var(--cream);padding:40px;border:1px solid #e2e8f0}
.pricing-tier{font-size:12px;letter-spacing:2px;color:var(--gold);margin-bottom:16px}
.pricing-price{font-size:36px;font-weight:700;margin-bottom:24px}
.pricing-price small{font-size:14px;font-weight:400}
.btn-card{width:100%;background:transparent;border:1px solid var(--dark);padding:12px;cursor:pointer}
.card-premium{border-top:3px solid var(--gold)}
.cta{background:var(--dark);color:white;padding:80px 0;text-align:center}
.btn-cta{background:var(--gold);color:var(--dark);border:none;padding:16px 48px;font-weight:600;cursor:pointer}
.footer{padding:48px 0;text-align:center;border-top:1px solid #e2e8f0;color:#8a9bb0;font-size:12px}
@media(max-width:900px){.container{padding:0 24px}.hero h1{font-size:32px}.pricing-grid{grid-template-columns:1fr}}
</style>
</head>
<body>
<nav class="navbar"><div class="container"><a href="/" class="logo">VETTIFY <span>INTELLIGENCE</span></a><span class="badge">Private Advisory</span></div></nav>
<section class="hero"><div class="container"><h1>How are you perceived in high-trust environments?</h1><p>We measure perception gaps, benchmark against peers, and tell you exactly what to fix.</p><div><button class="btn-primary" onclick="openApplication()">Request Perception Audit →</button><button class="btn-outline" onclick="window.location.href='/download-sample-report'">View Sample Report →</button></div></div></section>
<section class="pricing"><div class="container"><h2>Perception Intelligence Tiers</h2><div class="pricing-grid"><div class="pricing-card"><div class="pricing-tier">PROFESSIONAL</div><div class="pricing-price">R9,900<span style="font-size:14px;">/month</span></div><button class="btn-card" onclick="openApplication()">Request Access</button></div><div class="pricing-card"><div class="pricing-tier">EXECUTIVE</div><div class="pricing-price">R24,900<span style="font-size:14px;">/month</span></div><button class="btn-card" onclick="openApplication()">Request Access</button></div><div class="pricing-card card-premium"><div class="pricing-tier">ELITE ADVISORY</div><div class="pricing-price">R49,900<span style="font-size:14px;">/month</span></div><button class="btn-card" onclick="openApplication()">Request Access</button></div></div></div></section>
<section class="cta"><div class="container"><h2>Applications reviewed manually. Limited capacity.</h2><button class="btn-cta" onclick="openApplication()">Request Perception Audit →</button></div></section>
<footer class="footer"><div class="container"><p>VETTIFY INTELLIGENCE — PERCEPTION GAP ENGINE</p></div></footer>
<script>function openApplication(){window.location.href='/apply'}</script>
</body>
</html>
    ''')

@app.route('/apply')
def apply():
    return render_template_string('''
<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>Apply | Vettify</title><link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600&display=swap" rel="stylesheet"><style>
*{margin:0;padding:0;box-sizing:border-box}body{font-family:'Inter',sans-serif;background:#faf8f5;padding:60px 20px}.container{max-width:600px;margin:0 auto;background:white;padding:40px;border:1px solid #e2e8f0}h1{font-size:28px;margin-bottom:8px}.sub{color:#8a9bb0;margin-bottom:32px}.form-group{margin-bottom:24px}label{display:block;font-size:11px;text-transform:uppercase;margin-bottom:8px;font-weight:600}input,select,textarea{width:100%;padding:12px;border:1px solid #e2e8f0;font-size:14px}.btn-submit{width:100%;background:#0a1628;color:white;border:none;padding:14px;font-size:14px;font-weight:500;cursor:pointer;margin-top:16px}.note{font-size:11px;color:#8a9bb0;text-align:center;margin-top:24px}@media(max-width:600px){.container{padding:24px}}</style></head>
<body><div class="container"><h1>Apply for Perception Audit</h1><div class="sub">Applications reviewed manually. Limited capacity.</div><form id="applicationForm"><div class="form-group"><label>Full Name</label><input type="text" id="full_name" required></div><div class="form-group"><label>Email</label><input type="email" id="email" required></div><div class="form-group"><label>LinkedIn URL</label><input type="url" id="linkedin_url"></div><div class="form-group"><label>Current Position</label><input type="text" id="position" placeholder="Founder, CEO, Executive..."></div><div class="form-group"><label>If raising capital, what amount?</label><select id="funding_amount"><option>Not raising</option><option>Under R5M</option><option>R5M-R20M</option><option>R20M-R100M</option><option>R100M+</option></select></div><div class="form-group"><label>Paste your LinkedIn profile text or bio</label><textarea id="profile_text" rows="6" placeholder="Paste your LinkedIn summary, bio, or profile description here..."></textarea></div><button type="submit" class="btn-submit">Request Perception Audit →</button><div class="note">Your application will be reviewed. Selected clients will receive a full perception gap report.</div></form></div>
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
        profile_text: document.getElementById('profile_text').value
    };
    try {
        const res = await fetch('/submit-application', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(formData) });
        if (res.ok) { alert('Application received. We will review and respond.'); window.location.href = '/'; }
        else { alert('Error submitting.'); }
    } catch(err) { alert('Error submitting.'); }
    btn.textContent = 'Request Perception Audit →';
    btn.disabled = false;
});
</script>
</body></html>
    ''')

@app.route('/submit-application', methods=['POST'])
def submit_application():
    data = request.json
    conn = get_db()
    app_id = str(uuid.uuid4())[:8]
    conn.execute('''INSERT INTO applications (id, full_name, email, linkedin_url, position, funding_amount, visibility_goal, submitted_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
        (app_id, data['full_name'], data['email'], data['linkedin_url'], data['position'], data['funding_amount'], data.get('profile_text', ''), datetime.now().isoformat()))
    conn.commit()
    conn.close()
    send_email_notification(data)
    return jsonify({'status': 'received'})

@app.route('/admin/applications')
def admin_applications():
    conn = get_db()
    apps = conn.execute('SELECT * FROM applications ORDER BY submitted_at DESC').fetchall()
    conn.close()
    return render_template_string('''
<!DOCTYPE html><html><head><title>Admin</title><style>body{font-family:monospace;padding:20px;}table{border-collapse:collapse;}td,th{border:1px solid #ccc;padding:8px;}</style></head>
<body><h1>Applications</h1><table>
<th>Name</th><th>Email</th><th>Position</th><th>Funding</th><th>Status</th><th>Date</th>
{% for a in apps %}
<tr><td>{{ a.full_name }}</td><td>{{ a.email }}</td><td>{{ a.position }}</td><td>{{ a.funding_amount }}</td><td>{{ a.status }}</td><td>{{ a.submitted_at[:16] }}</td></tr>
{% endfor %}
</table></body></html>
    ''', apps=apps)

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=5000)
