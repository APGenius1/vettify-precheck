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
    """Send email when new application submitted"""
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

def generate_intelligence_report(application_data):
    """Generate elite perception intelligence report"""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=72, bottomMargin=72, leftMargin=72, rightMargin=72)
    styles = getSampleStyleSheet()
    story = []
    
    # Custom styles
    title_style = ParagraphStyle('Title', parent=styles['Title'], fontSize=22, textColor=colors.HexColor('#0a1628'), alignment=1, spaceAfter=6, fontName='Helvetica-Bold')
    subtitle_style = ParagraphStyle('Subtitle', parent=styles['Normal'], fontSize=10, textColor=colors.HexColor('#8a9bb0'), alignment=1, spaceAfter=12)
    heading_style = ParagraphStyle('Heading', parent=styles['Heading2'], fontSize=14, textColor=colors.HexColor('#0a1628'), spaceAfter=12, spaceBefore=12, fontName='Helvetica-Bold')
    gold_heading = ParagraphStyle('GoldHeading', parent=styles['Heading2'], fontSize=12, textColor=colors.HexColor('#c9a03d'), spaceAfter=8, spaceBefore=16, fontName='Helvetica-Bold')
    body_style = ParagraphStyle('Body', parent=styles['Normal'], fontSize=10, textColor=colors.HexColor('#2c3e50'), spaceAfter=6, leading=14)
    highlight_style = ParagraphStyle('Highlight', parent=styles['Normal'], fontSize=10, textColor=colors.HexColor('#c9a03d'), spaceAfter=6, leading=14)
    
    # Header
    story.append(Paragraph("VETTIFY INTELLIGENCE", title_style))
    story.append(Paragraph("Private Perception Briefing", subtitle_style))
    story.append(Spacer(1, 0.2*inch))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#c9a03d')))
    story.append(Spacer(1, 0.2*inch))
    
    # Executive Briefing
    story.append(Paragraph("EXECUTIVE BRIEFING", heading_style))
    story.append(Paragraph("This report evaluates how you are currently perceived through public signals, credibility indicators, and narrative alignment.", body_style))
    story.append(Paragraph("It is designed for individuals where perception directly impacts capital access, strategic partnerships, media positioning, and institutional trust.", body_style))
    story.append(Spacer(1, 0.15*inch))
    
    # Perception Index
    story.append(Paragraph("PERCEPTION INDEX", heading_style))
    story.append(Paragraph("<b>74 / 100 — Controlled but Fragile Authority Signal</b>", highlight_style))
    story.append(Paragraph("Your current public positioning communicates competence, but not dominance.", body_style))
    story.append(Paragraph("There is a clear gap between how capable you are and how strongly that capability is being perceived externally.", body_style))
    story.append(Paragraph("At higher visibility levels, this gap becomes a constraint on opportunity flow.", body_style))
    story.append(Spacer(1, 0.15*inch))
    
    # Credibility Signal Intelligence
    story.append(Paragraph("CREDIBILITY SIGNAL INTELLIGENCE", heading_style))
    
    story.append(Paragraph("1. Authority Positioning — <b>WEAK CONSISTENCY</b>", gold_heading))
    story.append(Paragraph("Your public-facing identity does not consistently signal decision-making power.", body_style))
    story.append(Paragraph("<b>Interpretation risk:</b> You are likely being categorized as operator rather than authority, contributor rather than leader. This reduces perceived strategic weight in high-stakes environments.", body_style))
    story.append(Spacer(1, 0.05*inch))
    
    story.append(Paragraph("2. Narrative Alignment — <b>FRAGMENTED SIGNAL</b>", gold_heading))
    story.append(Paragraph("Across platforms, your narrative does not form a single unified identity.", body_style))
    story.append(Paragraph("<b>Effect:</b> External observers must 'interpret you,' rather than immediately understand your positioning. At elite level visibility, interpretation friction = opportunity loss.", body_style))
    story.append(Spacer(1, 0.05*inch))
    
    story.append(Paragraph("3. Visibility Footprint — <b>UNDER-OPTIMISED</b>", gold_heading))
    story.append(Paragraph("Your presence is not yet reinforced by sufficient third-party validation signals.", body_style))
    story.append(Paragraph("<b>Consequence:</b> You are harder to 'verify quickly' in high-trust environments (media, investors, senior networks). In elite ecosystems, verification speed directly impacts access.", body_style))
    story.append(Spacer(1, 0.15*inch))
    
    # Strategic Exposure Risks
    story.append(Paragraph("STRATEGIC EXPOSURE RISKS", heading_style))
    story.append(Paragraph("If unchanged over the next 6–12 months, your current signal profile may result in:", body_style))
    story.append(Paragraph("• reduced conversion in high-trust introductions", body_style))
    story.append(Paragraph("• slower recognition in competitive environments", body_style))
    story.append(Paragraph("• underestimation of capability relative to actual performance", body_style))
    story.append(Paragraph("<b>This is not reputational damage — it is perception inefficiency.</b>", highlight_style))
    story.append(Spacer(1, 0.15*inch))
    
    # Executive Action Framework
    story.append(Paragraph("EXECUTIVE ACTION FRAMEWORK", heading_style))
    
    story.append(Paragraph("1. Authority Repositioning", gold_heading))
    story.append(Paragraph("Reframe your public identity to reflect decision-making capacity, domain ownership, and directional influence (not participation).", body_style))
    story.append(Spacer(1, 0.05*inch))
    
    story.append(Paragraph("2. Narrative Unification", gold_heading))
    story.append(Paragraph("Every public signal should reinforce one central identity axis. If someone sees you once, they should not need reinterpretation later.", body_style))
    story.append(Spacer(1, 0.05*inch))
    
    story.append(Paragraph("3. Third-Party Validation Strategy", gold_heading))
    story.append(Paragraph("Prioritise credible mentions, selective media presence, and high-signal association markers. Perception at elite level is heavily externally validated, not self-declared.", body_style))
    story.append(Spacer(1, 0.15*inch))
    
    # Final Diagnostic
    story.append(Paragraph("FINAL DIAGNOSTIC", heading_style))
    story.append(Paragraph("Your current positioning is not weak — it is <b>under-amplified relative to capability</b>.", highlight_style))
    story.append(Spacer(1, 0.05*inch))
    story.append(Paragraph("This creates a hidden inefficiency: You are likely being perceived below your actual strategic value.", body_style))
    story.append(Paragraph("Correcting this gap compounds over time into higher trust velocity, stronger inbound opportunities, improved deal positioning, and increased perceived authority without additional output.", body_style))
    story.append(Spacer(1, 0.15*inch))
    
    # Confidential footer
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor('#e2e8f0')))
    story.append(Paragraph("Confidential Briefing · Prepared for Private Client · Valid for 60 days", ParagraphStyle('Footer', parent=styles['Normal'], fontSize=7, textColor=colors.HexColor('#8a9bb0'), alignment=1, spaceAfter=6)))
    story.append(Paragraph("VETTIFY INTELLIGENCE — Perception Advisory", ParagraphStyle('Footer', parent=styles['Normal'], fontSize=7, textColor=colors.HexColor('#8a9bb0'), alignment=1)))
    
    doc.build(story)
    buffer.seek(0)
    return buffer

@app.route('/download-sample-report')
def download_sample_report():
    """Download elite sample intelligence report"""
    sample_data = {
        'full_name': 'Sample Client',
        'position': 'Executive'
    }
    pdf_buffer = generate_intelligence_report(sample_data)
    return send_file(pdf_buffer, as_attachment=True, download_name="vettify_elite_briefing_sample.pdf")

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
        :root {
            --gold: #c9a03d;
            --gold-light: #e8d5a3;
            --dark: #0a1628;
            --cream: #faf8f5;
        }
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Inter', sans-serif; background: var(--cream); color: var(--dark); line-height: 1.5; }
        
        .container { max-width: 1280px; margin: 0 auto; padding: 0 48px; }
        
        .navbar { padding: 32px 0; border-bottom: 1px solid rgba(0,0,0,0.05); }
        .navbar .container { display: flex; justify-content: space-between; align-items: center; }
        .logo { font-family: 'Cormorant Garamond', serif; font-size: 28px; font-weight: 600; letter-spacing: 2px; color: var(--dark); text-decoration: none; }
        .logo span { font-weight: 300; color: var(--gold); }
        .badge { background: var(--gold-light); color: var(--dark); padding: 4px 12px; border-radius: 30px; font-size: 10px; letter-spacing: 1px; }
        
        .hero { padding: 100px 0 60px; text-align: center; background: linear-gradient(135deg, #faf8f5 0%, #f5f2eb 100%); }
        .hero-badge { display: inline-block; color: var(--gold); font-size: 11px; letter-spacing: 3px; text-transform: uppercase; margin-bottom: 24px; }
        .hero h1 { font-family: 'Cormorant Garamond', serif; font-size: 64px; font-weight: 500; line-height: 1.2; max-width: 900px; margin: 0 auto 24px; }
        .hero p { font-size: 18px; color: #4a5a6a; max-width: 600px; margin: 0 auto 32px; }
        .btn-primary { background: var(--dark); color: white; border: none; padding: 16px 40px; font-size: 13px; letter-spacing: 2px; text-transform: uppercase; font-weight: 500; cursor: pointer; transition: all 0.3s; }
        .btn-primary:hover { background: var(--gold); color: var(--dark); }
        .btn-outline { background: transparent; border: 1px solid var(--dark); color: var(--dark); padding: 14px 36px; font-size: 13px; letter-spacing: 2px; text-transform: uppercase; cursor: pointer; transition: all 0.3s; margin-left: 16px; }
        .btn-outline:hover { background: var(--dark); color: white; }
        
        .intelligence { padding: 100px 0; background: white; }
        .intelligence h2 { font-family: 'Cormorant Garamond', serif; font-size: 42px; font-weight: 500; text-align: center; margin-bottom: 60px; }
        .intelligence-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 48px; }
        .intel-card { text-align: center; padding: 0 20px; }
        .intel-icon { font-size: 40px; margin-bottom: 24px; }
        .intel-card h3 { font-family: 'Cormorant Garamond', serif; font-size: 22px; font-weight: 500; margin-bottom: 16px; }
        .intel-card p { color: #4a5a6a; font-size: 14px; line-height: 1.6; }
        
        .consequence { background: var(--dark); color: white; padding: 100px 0; text-align: center; }
        .consequence h2 { font-family: 'Cormorant Garamond', serif; font-size: 42px; font-weight: 500; margin-bottom: 32px; }
        .consequence p { max-width: 700px; margin: 0 auto; font-size: 18px; color: #8a9bb0; line-height: 1.8; }
        .consequence-highlight { color: var(--gold); }
        
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
        
        .cta { background: var(--dark); color: white; padding: 80px 0; text-align: center; }
        .cta h2 { font-family: 'Cormorant Garamond', serif; font-size: 42px; font-weight: 500; margin-bottom: 16px; }
        .cta p { color: #8a9bb0; margin-bottom: 32px; }
        .btn-cta { background: var(--gold); color: var(--dark); border: none; padding: 16px 48px; font-size: 13px; letter-spacing: 2px; text-transform: uppercase; font-weight: 600; cursor: pointer; }
        
        .footer { padding: 48px 0; text-align: center; border-top: 1px solid #e2e8f0; color: #8a9bb0; font-size: 11px; letter-spacing: 1px; }
        
        @media (max-width: 900px) { .container { padding: 0 24px; } .hero h1 { font-size: 42px; } .pricing-grid { grid-template-columns: 1fr; max-width: 400px; margin: 0 auto; } .intelligence-grid { grid-template-columns: 1fr; gap: 32px; } }
    </style>
</head>
<body>
    <nav class="navbar"><div class="container"><a href="/" class="logo">VETTIFY <span>INTELLIGENCE</span></a><span class="badge">Private Advisory</span></div></nav>
    <section class="hero"><div class="container"><div class="hero-badge">PERCEPTION INTELLIGENCE</div><h1>We assess how investors, media, and clients will perceive you — before they do.</h1><p>Private perception advisory for founders, executives, and public figures. Intelligence, not software.</p><div><button class="btn-primary" onclick="openApplication()">Request Intelligence Brief →</button><button class="btn-outline" onclick="window.location.href='/download-sample-report'">View Sample Report →</button></div></div></section>
    <section class="intelligence"><div class="container"><h2>What We Evaluate</h2><div class="intelligence-grid"><div class="intel-card"><div class="intel-icon">🎯</div><h3>Investor Perception</h3><p>How would a pitch partner interpret your positioning? We simulate investor judgment before you raise.</p></div><div class="intel-card"><div class="intel-icon">📰</div><h3>Media Readiness</h3><p>Would media advisors feature or avoid you? We evaluate your public narrative against editorial standards.</p></div><div class="intel-card"><div class="intel-icon">🏛️</div><h3>Reputation Risk</h3><p>What perception gaps could cost you partnerships or opportunities? We identify them before they surface.</p></div></div></div></section>
    <section class="consequence"><div class="container"><h2>A weak perception costs <span class="consequence-highlight">funding, opportunities, and trust</span> — long before you know it exists.</h2><p>Most founders discover their reputation risk only after a pitch fails, a partnership falls through, or credibility is already questioned. Vettify exists to prevent that moment entirely.</p></div></section>
    <section class="pricing"><div class="container"><h2>Intelligence Advisory Tiers</h2><div class="pricing-sub">Application-only · White-glove onboarding</div><div class="pricing-grid"><div class="pricing-card"><div class="pricing-tier">PERCEPTION AUDIT</div><div class="pricing-price">R3,500</div><ul class="pricing-features"><li>Full reputation risk analysis</li><li>Investor perception score</li><li>Strategic recommendations</li><li>48-hour delivery</li></ul><button class="btn-card" onclick="openApplication()">Request Audit</button></div><div class="pricing-card"><div class="pricing-tier">INTELLIGENCE ADVISORY</div><div class="pricing-price">R15,000<span style="font-size:12px;">/month</span></div><ul class="pricing-features"><li>Monthly perception audit</li><li>Crisis risk simulation</li><li>Investor readiness tracking</li><li>Priority response (24h)</li></ul><button class="btn-card" onclick="openApplication()">Request Advisory</button></div><div class="pricing-card card-premium"><div class="pricing-tier">EXECUTIVE INTELLIGENCE</div><div class="pricing-price">R45,000<span style="font-size:12px;">/month</span></div><ul class="pricing-features"><li>Weekly perception analysis</li><li>Human advisory layer</li><li>Competitor benchmarking</li><li>Strategic roadmap</li></ul><button class="btn-card" onclick="openApplication()">Request Executive</button></div><div class="pricing-card card-premium"><div class="pricing-tier">CONCIERGE INTELLIGENCE</div><div class="pricing-price">R95,000<span style="font-size:12px;">/month</span></div><ul class="pricing-features"><li>Daily monitoring</li><li>Direct strategist access</li><li>Bespoke crisis preparation</li><li>White-glove advisory</li></ul><button class="btn-card" onclick="openApplication()">Request Concierge</button></div></div></div></section>
    <section class="cta"><div class="container"><h2>Applications are reviewed manually to ensure client fit.</h2><p>Currently accepting founding members. Limited capacity.</p><button class="btn-cta" onclick="openApplication()">Request Intelligence Brief →</button></div></section>
    <footer class="footer"><div class="container"><p>VETTIFY INTELLIGENCE — PRIVATE PERCEPTION ADVISORY</p><p style="margin-top: 12px;">Not a tool. Not software. Intelligence interpreted for decision-makers.</p></div></footer>
    <script>function openApplication() { window.location.href = '/apply'; }</script>
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
        input:focus, select:focus,
