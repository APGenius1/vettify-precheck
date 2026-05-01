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
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

app = Flask(__name__)
app.secret_key = os.urandom(24).hex()
CORS(app)

# Email configuration
EMAIL_ADDRESS = "vettifyprecheck@gmail.com"
EMAIL_PASSWORD = "Isefbuqadsreulbb"

def send_email_notification(application_data):
    try:
        msg = MIMEMultipart()
        msg['From'] = EMAIL_ADDRESS
        msg['To'] = EMAIL_ADDRESS
        msg['Subject'] = f"New Intelligence Application - {application_data['full_name']}"
        
        body = f"""
        New Intelligence Application Received
        
        Applicant Details:
        -------------------
        Name: {application_data['full_name']}
        Email: {application_data['email']}
        Position: {application_data['position']}
        LinkedIn: {application_data['linkedin_url']}
        Funding Amount: {application_data['funding_amount']}
        
        Visibility Goals:
        {application_data['visibility_goal']}
        
        Submitted: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        
        ---
        Vettify Intelligence System
        """
        
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

# ================= ELITE INTELLIGENCE REPORT =================

def generate_intelligence_report(client_data):
    """Generate elite perception intelligence report - 4 pages of actionable strategic intelligence"""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, 
                           topMargin=72, bottomMargin=72, 
                           leftMargin=72, rightMargin=72)
    styles = getSampleStyleSheet()
    story = []
    
    # Custom styles
    title_style = ParagraphStyle('Title', parent=styles['Title'], fontSize=26, textColor=colors.HexColor('#0a1628'), alignment=1, spaceAfter=6, fontName='Helvetica-Bold')
    subtitle_style = ParagraphStyle('Subtitle', parent=styles['Normal'], fontSize=9, textColor=colors.HexColor('#8a9bb0'), alignment=1, spaceAfter=20)
    section_header = ParagraphStyle('SectionHeader', parent=styles['Heading2'], fontSize=14, textColor=colors.HexColor('#0a1628'), spaceAfter=12, spaceBefore=20, fontName='Helvetica-Bold')
    subsection = ParagraphStyle('Subsection', parent=styles['Heading3'], fontSize=12, textColor=colors.HexColor('#0a1628'), spaceAfter=8, spaceBefore=12, fontName='Helvetica-Bold')
    body_text = ParagraphStyle('BodyText', parent=styles['Normal'], fontSize=10, textColor=colors.HexColor('#2c3e50'), spaceAfter=8, leading=16)
    insight_text = ParagraphStyle('InsightText', parent=styles['Normal'], fontSize=10, textColor=colors.HexColor('#c9a03d'), spaceAfter=8, leading=16, fontName='Helvetica-Oblique')
    bullet = ParagraphStyle('Bullet', parent=styles['Normal'], fontSize=10, textColor=colors.HexColor('#2c3e50'), spaceAfter=4, leftIndent=12)
    
    # Scores
    perception_score = 74
    authority_score = 68
    narrative_score = 71
    visibility_score = 59
    client_name = client_data.get('full_name', 'Private Client')
    
    # ========== PAGE 1 ==========
    story.append(Paragraph("CONFIDENTIAL", ParagraphStyle('Confidential', parent=styles['Normal'], fontSize=8, textColor=colors.HexColor('#c9a03d'), alignment=2, spaceAfter=6)))
    story.append(Spacer(1, 0.05*inch))
    story.append(Paragraph("VETTIFY INTELLIGENCE", title_style))
    story.append(Paragraph("Private Perception & Authority Briefing", subtitle_style))
    story.append(Spacer(1, 0.1*inch))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#c9a03d')))
    story.append(Spacer(1, 0.2*inch))
    
    story.append(Paragraph(f"Prepared for: <b>{client_name}</b>", body_text))
    story.append(Paragraph(f"Date: {datetime.now().strftime('%d %B %Y')}", body_text))
    story.append(Paragraph("Classification: Private & Confidential", body_text))
    story.append(Spacer(1, 0.15*inch))
    
    story.append(Paragraph("I. EXECUTIVE SUMMARY", section_header))
    story.append(Paragraph("This briefing evaluates how your public presence is currently interpreted by high-stakes audiences — investors, media, strategic partners, and institutional decision-makers.", body_text))
    story.append(Spacer(1, 0.05*inch))
    story.append(Paragraph("The analysis identifies perception gaps that may be constraining opportunity flow, reputation leverage, and trust velocity in elite environments.", body_text))
    story.append(Spacer(1, 0.05*inch))
    story.append(Paragraph("<b>Key finding:</b> Your current positioning communicates competence but not dominance. The gap between actual capability and perceived authority is creating hidden friction in high-trust interactions.", insight_text))
    story.append(Spacer(1, 0.15*inch))
    
    story.append(Paragraph("II. PERCEPTION INDEX", section_header))
    story.append(Paragraph(f"<b>Overall Perception Score: {perception_score} / 100</b>", ParagraphStyle('Score', parent=styles['Normal'], fontSize=22, textColor=colors.HexColor('#c9a03d'), spaceAfter=12)))
    story.append(Spacer(1, 0.05*inch))
    story.append(Paragraph("Classification: <b>Controlled but Fragile Authority Signal</b>", insight_text))
    story.append(Spacer(1, 0.1*inch))
    
    score_data = [
        ["1. Authority Positioning", f"{authority_score}/100", "Weak Consistency"],
        ["2. Narrative Alignment", f"{narrative_score}/100", "Fragmented Signal"],
        ["3. Visibility Footprint", f"{visibility_score}/100", "Under-Optimised"],
    ]
    score_table = Table(score_data, colWidths=[2.2*inch, 1.2*inch, 2.2*inch])
    score_table.setStyle(TableStyle([
        ('FONTNAME', (0,0), (-1,-1), 'Helvetica'),
        ('FONTSIZE', (0,0), (-1,-1), 9),
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#0a1628')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('ALIGN', (1,0), (1,-1), 'CENTER'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e2e8f0')),
        ('TOPPADDING', (0,0), (-1,-1), 10),
        ('BOTTOMPADDING', (0,0), (-1,-1), 10),
    ]))
    story.append(score_table)
    story.append(Spacer(1, 0.15*inch))
    story.append(Paragraph("Your authority signals are not yet reinforced by consistent narrative or third-party validation. This creates a perception gap where actual capability exceeds perceived weight in high-stakes rooms.", body_text))
    story.append(Spacer(1, 0.15*inch))
    
    # ========== PAGE 2 ==========
    story.append(Paragraph("III. CREDIBILITY SIGNAL INTELLIGENCE", section_header))
    
    story.append(Paragraph("A. Authority Positioning Analysis", subsection))
    story.append(Paragraph("Your public-facing identity does not consistently signal decision-making power. In environments where first impressions determine access (investor intros, board consideration, media features), weak authority signals create filtering friction.", body_text))
    story.append(Spacer(1, 0.05*inch))
    story.append(Paragraph("• Current signals: Competence-focused, contribution-oriented, collaborative tone.", bullet))
    story.append(Paragraph("• Missing signals: Decisiveness, domain ownership, directional influence, gatekeeper positioning.", bullet))
    story.append(Spacer(1, 0.05*inch))
    story.append(Paragraph("<b>Interpretation risk:</b> You are likely being categorized as 'operator' rather than 'owner,' 'contributor' rather than 'authority.' In high-stakes contexts, this reduces perceived strategic weight.", body_text))
    story.append(Spacer(1, 0.1*inch))
    
    story.append(Paragraph("B. Narrative Alignment Audit", subsection))
    story.append(Paragraph("Across your public platforms, your narrative does not form a single, unified identity axis. This forces external observers to 'interpret' you rather than immediately understand your positioning.", body_text))
    story.append(Spacer(1, 0.05*inch))
    story.append(Paragraph("<b>Platform consistency assessment:</b>", body_text))
    story.append(Paragraph("• LinkedIn: Professional but generic — lacks domain signature", bullet))
    story.append(Paragraph("• Media presence: Limited editorial footprint — low third-party validation", bullet))
    story.append(Paragraph("• Public speaking/panels: No visible track record — missing authority reinforcement", bullet))
    story.append(Spacer(1, 0.05*inch))
    story.append(Paragraph("<b>Effect:</b> Each interaction requires reinterpretation. At elite visibility levels, interpretation friction = opportunity loss = slower trust velocity.", body_text))
    story.append(Spacer(1, 0.1*inch))
    
    story.append(Paragraph("C. Third-Party Validation Infrastructure", subsection))
    story.append(Paragraph("Your presence is not yet reinforced by sufficient external validation signals. In high-trust environments, perception is heavily socially validated — self-declaration alone carries limited weight.", body_text))
    story.append(Spacer(1, 0.05*inch))
    story.append(Paragraph("<b>Current validation gaps include:</b>", body_text))
    story.append(Paragraph("• No institutional affiliations visible in primary profile", bullet))
    story.append(Paragraph("• Limited media or press mentions as authority source", bullet))
    story.append(Paragraph("• Missing association markers (boards, advisory roles, selective memberships)", bullet))
    story.append(Spacer(1, 0.05*inch))
    story.append(Paragraph("<b>Consequence:</b> Verification friction in high-trust environments. People who need to quickly assess 'who you are' take longer to reach confidence — or move to someone easier to verify.", body_text))
    story.append(Spacer(1, 0.15*inch))
    
    # ========== PAGE 3 ==========
    story.append(Paragraph("IV. STRATEGIC EXPOSURE RISKS", section_header))
    story.append(Paragraph("Based on current signal architecture, the following risks are present over the next 6-12 months:", body_text))
    story.append(Spacer(1, 0.05*inch))
    
    story.append(Paragraph("<b>Risk 1: Reduced Conversion in High-Trust Introductions</b>", subsection))
    story.append(Paragraph("When introduced to investors, board members, or strategic partners without pre-existing reputation, weak visibility infrastructure reduces conversion probability. People rely on verification signals when trust is not pre-established.", body_text))
    story.append(Spacer(1, 0.08*inch))
    
    story.append(Paragraph("<b>Risk 2: Underestimation at First Encounter</b>", subsection))
    story.append(Paragraph("Your actual capability is likely exceeding perceived weight. This creates a 'hidden tax' on every first interaction — you spend credibility capital to overcome perception gap before value demonstration begins.", body_text))
    story.append(Spacer(1, 0.08*inch))
    
    story.append(Paragraph("<b>Risk 3: Opportunity Bypass in Competitive Contexts</b>", subsection))
    story.append(Paragraph("When competing for speaking slots, board positions, media features, or investment, those with stronger perception infrastructure get prioritized. Not because they are more capable — because they are easier to justify quickly.", body_text))
    story.append(Spacer(1, 0.08*inch))
    
    story.append(Paragraph("<b>This is not reputational damage — it is perception inefficiency.</b>", insight_text))
    story.append(Spacer(1, 0.15*inch))
    
    # ========== PAGE 4 ==========
    story.append(Paragraph("V. EXECUTIVE ACTION FRAMEWORK", section_header))
    
    story.append(Paragraph("Priority 1: Authority Repositioning", subsection))
    story.append(Paragraph("Action: Reframe public identity to reflect decision-making capacity, domain ownership, and directional influence — not participation or contribution.", body_text))
    story.append(Paragraph("<b>Timeline:</b> 30 days. <b>Impact:</b> Immediate shift in first-impression categorization.", body_text))
    story.append(Spacer(1, 0.08*inch))
    
    story.append(Paragraph("Priority 2: Narrative Unification", subsection))
    story.append(Paragraph("Action: Every public signal should reinforce one central identity axis. Someone encountering you once should not need reinterpretation later.", body_text))
    story.append(Paragraph("<b>Timeline:</b> 60 days. <b>Impact:</b> Reduced friction in sequential interactions.", body_text))
    story.append(Spacer(1, 0.08*inch))
    
    story.append(Paragraph("Priority 3: Third-Party Validation Infrastructure", subsection))
    story.append(Paragraph("Action: Prioritise credible mentions, selective media presence, board/advisor affiliations, and high-signal association markers.", body_text))
    story.append(Paragraph("<b>Timeline:</b> 90-120 days. <b>Impact:</b> Increased verification speed in high-trust environments.", body_text))
    story.append(Spacer(1, 0.08*inch))
    
    story.append(Paragraph("Priority 4: Visibility Footprint Expansion", subsection))
    story.append(Paragraph("Action: Targeted bylined articles, podcast appearances, or panel participation in high-signal venues within your domain.", body_text))
    story.append(Paragraph("<b>Timeline:</b> 90 days. <b>Impact:</b> External validation anchors for your authority claims.", body_text))
    story.append(Spacer(1, 0.15*inch))
    
    story.append(Paragraph("VI. FINAL DIAGNOSTIC", section_header))
    story.append(Paragraph("<b>Your current positioning is not weak — it is under-amplified relative to capability.</b>", insight_text))
    story.append(Spacer(1, 0.05*inch))
    story.append(Paragraph("You are likely being perceived below your actual strategic value. This creates a hidden inefficiency that compounds over time — each interaction starts from a deficit that must be overcome before value is recognized.", body_text))
    story.append(Spacer(1, 0.05*inch))
    story.append(Paragraph("<b>Correcting this perception gap compounds into:</b>", body_text))
    story.append(Paragraph("• Higher trust velocity in new relationships", bullet))
    story.append(Paragraph("• Stronger inbound opportunity flow", bullet))
    story.append(Paragraph("• Improved deal positioning without changing capability", bullet))
    story.append(Paragraph("• Increased perceived authority without additional output", bullet))
    story.append(Spacer(1, 0.1*inch))
    story.append(Paragraph("This is solvable. The gap is structural, not fundamental. With systematic execution of the framework above, perception alignment is achievable within 120 days.", body_text))
    story.append(Spacer(1, 0.2*inch))
    
    # Footer
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor('#e2e8f0')))
    story.append(Spacer(1, 0.05*inch))
    story.append(Paragraph(f"Confidential Briefing · Prepared for {client_name} · Valid for 60 days", 
                         ParagraphStyle('Footer', parent=styles['Normal'], fontSize=7, 
                                       textColor=colors.HexColor('#8a9bb0'), alignment=1, spaceAfter=4)))
    story.append(Paragraph("VETTIFY INTELLIGENCE — Perception Advisory", 
                         ParagraphStyle('Footer', parent=styles['Normal'], fontSize=7, 
                                       textColor=colors.HexColor('#8a9bb0'), alignment=1)))
    
    doc.build(story)
    buffer.seek(0)
    return buffer

@app.route('/download-sample-report')
def download_sample_report():
    sample_data = {'full_name': 'Private Client', 'position': 'Executive', 'email': 'client@example.com'}
    pdf_buffer = generate_intelligence_report(sample_data)
    return send_file(pdf_buffer, as_attachment=True, download_name="vettify_elite_briefing.pdf")

# ================= HOMEPAGE =================
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
        :root { --gold: #c9a03d; --gold-light: #e8d5a3; --dark: #0a1628; --cream: #faf8f5; }
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Inter', sans-serif; background: var(--cream); color: var(--dark); }
        .container { max-width: 1280px; margin: 0 auto; padding: 0 48px; }
        .navbar { padding: 32px 0; border-bottom: 1px solid rgba(0,0,0,0.05); }
        .navbar .container { display: flex; justify-content: space-between; align-items: center; }
        .logo { font-family: 'Cormorant Garamond', serif; font-size: 28px; font-weight: 600; letter-spacing: 2px; color: var(--dark); text-decoration: none; }
        .logo span { font-weight: 300; color: var(--gold); }
        .badge { background: var(--gold-light); padding: 4px 12px; border-radius: 30px; font-size: 10px; letter-spacing: 1px; }
        .hero { padding: 100px 0 60px; text-align: center; background: linear-gradient(135deg, #faf8f5 0%, #f5f2eb 100%); }
        .hero-badge { display: inline-block; color: var(--gold); font-size: 11px; letter-spacing: 3px; text-transform: uppercase; margin-bottom: 24px; }
        .hero h1 { font-family: 'Cormorant Garamond', serif; font-size: 64px; font-weight: 500; line-height: 1.2; max-width: 900px; margin: 0 auto 24px; }
        .hero p { font-size: 18px; color: #4a5a6a; max-width: 600px; margin: 0 auto 32px; }
        .btn-primary { background: var(--dark); color: white; border: none; padding: 16px 40px; font-size: 13px; letter-spacing: 2px; text-transform: uppercase; font-weight: 500; cursor: pointer; }
        .btn-primary:hover { background: var(--gold); color: var(--dark); }
        .btn-outline { background: transparent; border: 1px solid var(--dark); color: var(--dark); padding: 14px 36px; font-size: 13px; letter-spacing: 2px; text-transform: uppercase; cursor: pointer; margin-left: 16px; }
        .btn-outline:hover { background: var(--dark); color: white; }
        .pricing { padding: 100px 0; background: var(--cream); }
        .pricing h2 { text-align: center; font-family: 'Cormorant Garamond', serif; font-size: 42px; font-weight: 500; margin-bottom: 16px; }
        .pricing-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 24px; margin-top: 60px; }
        .pricing-card { background: white; padding: 40px 28px; border: 1px solid #e2e8f0; transition: all 0.3s; }
        .pricing-card:hover { transform: translateY(-4px); border-color: var(--gold); }
        .pricing-tier { font-size: 10px; letter-spacing: 2px; color: var(--gold); margin-bottom: 16px; }
        .pricing-price { font-family: 'Cormorant Garamond', serif; font-size: 36px; font-weight: 600; margin-bottom: 24px; }
        .btn-card { width: 100%; background: transparent; border: 1px solid var(--dark); padding: 12px; font-size: 11px; letter-spacing: 2px; cursor: pointer; }
        .btn-card:hover { background: var(--dark); color: white; }
        .card-premium { border-top: 3px solid var(--gold); }
        .cta { background: var(--dark); color: white; padding: 80px 0; text-align: center; }
        .btn-cta { background: var(--gold); color: var(--dark); border: none; padding: 16px 48px; font-size: 13px; letter-spacing: 2px; text-transform: uppercase; font-weight: 600; cursor: pointer; }
        .footer { padding: 48px 0; text-align: center; border-top: 1px solid #e2e8f0; color: #8a9bb0; font-size: 11px; }
        @media (max-width: 900px) { .container { padding: 0 24px; } .hero h1 { font-size: 42px; } .pricing-grid { grid-template-columns: 1fr; } }
    </style>
</head>
<body>
<nav class="navbar"><div class="container"><a href="/" class="logo">VETTIFY <span>INTELLIGENCE</span></a><span class="badge">Private Advisory</span></div></nav>
<section class="hero"><div class="container"><div class="hero-badge">PERCEPTION INTELLIGENCE</div><h1>We assess how investors, media, and clients will perceive you — before they do.</h1><p>Private perception advisory for founders, executives, and public figures.</p><div><button class="btn-primary" onclick="openApplication()">Request Intelligence Brief →</button><button class="btn-outline" onclick="window.location.href='/download-sample-report'">View Sample Report →</button></div></div></section>
<section class="pricing"><div class="container"><h2>Intelligence Advisory Tiers</h2><div class="pricing-grid"><div class="pricing-card"><div class="pricing-tier">PERCEPTION AUDIT</div><div class="pricing-price">R3,500</div><button class="btn-card" onclick="openApplication()">Request Audit</button></div><div class="pricing-card"><div class="pricing-tier">INTELLIGENCE ADVISORY</div><div class="pricing-price">R15,000<span style="font-size:12px;">/month</span></div><button class="btn-card" onclick="openApplication()">Request Advisory</button></div><div class="pricing-card card-premium"><div class="pricing-tier">EXECUTIVE INTELLIGENCE</div><div class="pricing-price">R45,000<span style="font-size:12px;">/month</span></div><button class="btn-card" onclick="openApplication()">Request Executive</button></div><div class="pricing-card card-premium"><div class="pricing-tier">CONCIERGE INTELLIGENCE</div><div class="pricing-price">R95,000<span style="font-size:12px;">/month</span></div><button class="btn-card" onclick="openApplication()">Request Concierge</button></div></div></div></section>
<section class="cta"><div class="container"><h2>Applications reviewed manually.</h2><button class="btn-cta" onclick="openApplication()">Request Intelligence Brief →</button></div></section>
<footer class="footer"><div class="container"><p>VETTIFY INTELLIGENCE — PRIVATE PERCEPTION ADVISORY</p></div></footer>
<script>function openApplication() { window.location.href = '/apply'; }</script>
</body>
</html>
    ''')

@app.route('/apply')
def apply():
    return render_template_string('''
<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>Vettify | Application</title>
<link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@300;400;500;600;700&family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
<style>*{margin:0;padding:0;box-sizing:border-box;}body{font-family:'Inter',sans-serif;background:#faf8f5;color:#0a1628;}.container{max-width:800px;margin:0 auto;padding:60px 32px;}.logo{font-family:'Cormorant Garamond',serif;font-size:28px;font-weight:600;text-align:center;margin-bottom:48px;text-decoration:none;color:#0a1628;display:block;}.logo span{color:#c9a03d;}.form-card{background:white;padding:48px;border:1px solid #e2e8f0;}h1{font-family:'Cormorant Garamond',serif;font-size:32px;font-weight:500;margin-bottom:8px;}.sub{color:#8a9bb0;margin-bottom:32px;font-size:13px;}.form-group{margin-bottom:24px;}label{display:block;font-size:10px;letter-spacing:1.5px;text-transform:uppercase;margin-bottom:8px;font-weight:600;}input,select,textarea{width:100%;padding:14px 16px;border:1px solid #e2e8f0;font-size:15px;background:white;}input:focus,select:focus,textarea:focus{outline:none;border-color:#c9a03d;}.btn-submit{width:100%;background:#0a1628;color:white;border:none;padding:16px;font-size:12px;letter-spacing:2px;text-transform:uppercase;font-weight:500;cursor:pointer;margin-top:16px;}.btn-submit:hover{background:#c9a03d;color:#0a1628;}.note{font-size:11px;color:#8a9bb0;text-align:center;margin-top:24px;}@media(max-width:600px){.container{padding:32px 20px;}.form-card{padding:28px;}}</style>
</head>
<body><div class="container"><a href="/" class="logo">VETTIFY <span>INTELLIGENCE</span></a><div class="form-card"><h1>Apply for Intelligence Access</h1><div class="sub">Applications reviewed manually. Limited capacity.</div><form id="applicationForm"><div class="form-group"><label>Full Name</label><input type="text" id="full_name" required></div><div class="form-group"><label>Email</label><input type="email" id="email" required></div><div class="form-group"><label>LinkedIn URL</label><input type="url" id="linkedin_url"></div><div class="form-group"><label>Position</label><input type="text" id="position" placeholder="Founder, CEO, Executive..."></div><div class="form-group"><label>If raising capital, what amount?</label><select id="funding_amount"><option>Not raising</option><option>Under R5M</option><option>R5M-R20M</option><option>R20M-R100M</option><option>R100M+</option></select></div><div class="form-group"><label>Visibility goals</label><textarea id="visibility_goal" rows="3"></textarea></div><button type="submit" class="btn-submit">Submit Application →</button></form><div class="note">Your application will be reviewed. Selected clients will receive onboarding details.</div></div></div>
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
        if (res.ok) { alert('Application received.'); window.location.href = '/'; }
        else { alert('Error submitting.'); }
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
    conn.execute('''INSERT INTO applications (id, full_name, email, linkedin_url, position, funding_amount, visibility_goal, submitted_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
        (app_id, data['full_name'], data['email'], data['linkedin_url'], data['position'], data['funding_amount'], data['visibility_goal'], datetime.now().isoformat()))
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
<body><h1>Applications ({{ apps|length }})</h1><table>
<tr><th>Name</th><th>Email</th><th>Position</th><th>Funding</th><th>Status</th><th>Date</th></tr>
{% for a in apps %}
<tr><td>{{ a.full_name }}</td><td>{{ a.email }}</td><td>{{ a.position }}</td><td>{{ a.funding_amount }}</td><td>{{ a.status }}</td><td>{{ a.submitted_at[:16] }}</td></tr>
{% endfor %}
</table></body></html>
    ''', apps=apps)

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=5000)
