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
import threading
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

app = Flask(__name__)
app.secret_key = os.urandom(24).hex()
CORS(app)

# ================= EMAIL CONFIGURATION =================
EMAIL_ADDRESS = "vettifyprecheck@gmail.com"
EMAIL_PASSWORD = "Isefbuqadsreulbb"

def send_email_notification(application_data):
    """Send email in background thread - does not block user"""
    try:
        msg = MIMEMultipart()
        msg['From'] = EMAIL_ADDRESS
        msg['To'] = EMAIL_ADDRESS
        msg['Subject'] = f"New Application - {application_data['full_name']}"
        
        body = f"""
        New Perception Audit Application
        
        Name: {application_data['full_name']}
        Email: {application_data['email']}
        Position: {application_data['position']}
        LinkedIn: {application_data['linkedin_url']}
        Funding Amount: {application_data['funding_amount']}
        
        Profile Text:
        {application_data.get('profile_text', 'Not provided')[:500]}
        
        Submitted: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        """
        
        msg.attach(MIMEText(body, 'plain'))
        server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        server.send_message(msg)
        server.quit()
    except Exception as e:
        print(f"Email error: {str(e)}")

# ================= DATABASE SETUP =================
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
        profile_text TEXT,
        status TEXT DEFAULT 'pending',
        submitted_at TEXT
    )""")
    conn.commit()
    conn.close()

init_db()

# ================= PERCEPTION SCORING ENGINE =================

def analyze_authority_signal(text):
    """Analyze how well the profile signals decision-making authority"""
    score = 70
    reasons = []
    fixes = []
    
    decision_words = ['decide', 'lead', 'direct', 'oversee', 'responsible', 'accountable', 'head of', 'executive']
    ownership_words = ['founder', 'built', 'created', 'launched', 'founded', 'co-founded']
    
    has_decision = any(word in text.lower() for word in decision_words)
    has_ownership = any(word in text.lower() for word in ownership_words)
    
    if not has_decision:
        score -= 15
        reasons.append("Your profile lacks decision-making language like 'lead', 'decide', or 'oversee'")
        fixes.append("Rewrite your headline to include a decision verb (e.g., 'I decide on X' or 'Leading Y')")
    else:
        score += 5
        reasons.append("Decision-making language detected - good foundation")
        fixes.append("Strengthen with more specific authority claims")
    
    if not has_ownership:
        score -= 10
        reasons.append("Missing ownership framing like 'founded' or 'built'")
        fixes.append("Add ownership language to your bio (e.g., 'Built X from zero to Y')")
    else:
        score += 5
    
    score = max(0, min(100, score))
    
    if score >= 80:
        level = "Strong"
    elif score >= 60:
        level = "Developing"
    else:
        level = "Weak"
    
    return {'score': score, 'level': level, 'reasons': reasons[:2], 'fixes': fixes[:2]}

def analyze_narrative_alignment(text):
    """Analyze narrative consistency and clarity"""
    score = 72
    reasons = []
    fixes = []
    
    word_count = len(text.split())
    
    if word_count < 20:
        score -= 15
        reasons.append("Profile is too short - lacks enough information for clear positioning")
        fixes.append("Expand your bio to 60-80 words that tell a complete story")
    elif word_count < 50:
        score -= 8
        reasons.append("Profile length is adequate but could be more comprehensive")
        fixes.append("Add 2-3 sentences about your mission or impact")
    else:
        score += 5
        reasons.append("Profile length provides sufficient detail")
    
    competitive_words = ['also', 'additionally', 'in addition', 'furthermore']
    has_competitive = any(word in text.lower() for word in competitive_words)
    
    if has_competitive:
        score -= 8
        reasons.append("Multiple competing narratives dilute your core positioning")
        fixes.append("Identify ONE core story and remove conflicting messages")
    
    score = max(0, min(100, score))
    
    if score >= 80:
        level = "Aligned"
    elif score >= 60:
        level = "Developing"
    else:
        level = "Fragmented"
    
    return {'score': score, 'level': level, 'reasons': reasons[:2], 'fixes': fixes[:2]}

def analyze_visibility_footprint(text):
    """Analyze public visibility and third-party validation"""
    score = 60
    reasons = []
    fixes = []
    
    media_words = ['spoke at', 'presented at', 'keynote', 'published', 'article', 'interview', 'podcast', 'featured']
    has_media = any(word in text.lower() for word in media_words)
    
    if not has_media:
        score -= 18
        reasons.append("No visible speaking engagements, media mentions, or published content")
        fixes.append("Target 1 bylined article or podcast appearance in the next 90 days")
    else:
        score += 8
        reasons.append("Media presence detected - good for credibility")
        fixes.append("Expand to 2-3 mentions across different platforms")
    
    assoc_words = ['board', 'advisor', 'member', 'fellow', 'committee', 'chair']
    has_associations = any(word in text.lower() for word in assoc_words)
    
    if not has_associations:
        score -= 10
        reasons.append("Missing visible association markers like board seats or advisory roles")
        fixes.append("Add any board positions, advisory roles, or selective memberships to your profile")
    else:
        score += 5
    
    score = max(0, min(100, score))
    
    if score >= 80:
        level = "Strong"
    elif score >= 60:
        level = "Building"
    else:
        level = "Under-Optimised"
    
    return {'score': score, 'level': level, 'reasons': reasons[:2], 'fixes': fixes[:2]}

def analyze_validation_signal(text):
    """Analyze social proof and third-party validation"""
    score = 65
    reasons = []
    fixes = []
    
    proof_words = ['recommend', 'endorse', 'client', 'partner', 'award', 'recognition']
    has_proof = any(word in text.lower() for word in proof_words)
    
    if not has_proof:
        score -= 15
        reasons.append("No visible social proof, client mentions, or endorsements")
        fixes.append("Collect 3-5 LinkedIn recommendations from credible colleagues or clients")
    else:
        score += 5
        reasons.append("Some social proof detected")
        fixes.append("Add specific client results or partner testimonials")
    
    result_words = ['increased', 'grew', 'saved', 'generated', 'achieved', 'won']
    has_results = any(word in text.lower() for word in result_words)
    
    if not has_results:
        score -= 8
        reasons.append("Missing measurable results or specific achievements")
        fixes.append("Add quantitative outcomes (e.g., 'grew revenue by X%' or 'saved Y hours')")
    
    score = max(0, min(100, score))
    
    if score >= 80:
        level = "Strong"
    elif score >= 60:
        level = "Developing"
    else:
        level = "Weak"
    
    return {'score': score, 'level': level, 'reasons': reasons[:2], 'fixes': fixes[:2]}

# ================= PERCEPTION GAP REPORT GENERATION =================

def generate_perception_gap_report(client_data, profile_text):
    """Generate professional perception gap report"""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, 
                           topMargin=72, bottomMargin=72, 
                           leftMargin=72, rightMargin=72)
    styles = getSampleStyleSheet()
    story = []
    
    # Professional styles
    title_style = ParagraphStyle('Title', parent=styles['Title'], fontSize=26, textColor=colors.HexColor('#0a1628'), alignment=1, spaceAfter=8, fontName='Helvetica-Bold')
    subtitle_style = ParagraphStyle('Subtitle', parent=styles['Normal'], fontSize=9, textColor=colors.HexColor('#8a9bb0'), alignment=1, spaceAfter=24)
    section_header = ParagraphStyle('SectionHeader', parent=styles['Heading2'], fontSize=14, textColor=colors.HexColor('#0a1628'), spaceAfter=12, spaceBefore=20, fontName='Helvetica-Bold')
    subsection = ParagraphStyle('Subsection', parent=styles['Heading3'], fontSize=12, textColor=colors.HexColor('#0a1628'), spaceAfter=8, spaceBefore=12, fontName='Helvetica-Bold')
    body_text = ParagraphStyle('BodyText', parent=styles['Normal'], fontSize=10, textColor=colors.HexColor('#2c3e50'), spaceAfter=8, leading=16)
    highlight = ParagraphStyle('Highlight', parent=styles['Normal'], fontSize=10, textColor=colors.HexColor('#c9a03d'), spaceAfter=8, leading=16, fontName='Helvetica-Bold')
    bullet = ParagraphStyle('Bullet', parent=styles['Normal'], fontSize=10, textColor=colors.HexColor('#2c3e50'), spaceAfter=6, leftIndent=16)
    
    # Analyze profile text
    if profile_text and len(profile_text.strip()) > 20:
        authority = analyze_authority_signal(profile_text)
        narrative = analyze_narrative_alignment(profile_text)
        visibility = analyze_visibility_footprint(profile_text)
        validation = analyze_validation_signal(profile_text)
    else:
        # Default for sample
        authority = {'score': 68, 'level': 'Developing', 'reasons': ['Lacks decision-making language'], 'fixes': ['Add leadership verbs to headline']}
        narrative = {'score': 71, 'level': 'Developing', 'reasons': ['No clear positioning statement'], 'fixes': ['Create consistent master bio']}
        visibility = {'score': 59, 'level': 'Under-Optimised', 'reasons': ['No media mentions detected'], 'fixes': ['Target bylined article']}
        validation = {'score': 65, 'level': 'Developing', 'reasons': ['No social proof visible'], 'fixes': ['Collect LinkedIn recommendations']}
    
    overall_score = (authority['score'] + narrative['score'] + visibility['score'] + validation['score']) / 4
    
    if overall_score >= 80:
        perceived_level = "Decision-Maker"
        target_level = "Strategic Leader"
        gap_description = "Small refinement needed"
        gap_color = "#16a34a"
    elif overall_score >= 65:
        perceived_level = "Operator / Contributor"
        target_level = "Decision-Maker"
        gap_description = "Moderate gap - authority signals need strengthening"
        gap_color = "#ea580c"
    else:
        perceived_level = "Individual Contributor"
        target_level = "Executive / Decision-Maker"
        gap_description = "Large gap - foundational repositioning required"
        gap_color = "#dc2626"
    
    client_name = client_data.get('full_name', 'Private Client')
    
    # PAGE 1
    story.append(Paragraph("CONFIDENTIAL", ParagraphStyle('Confidential', parent=styles['Normal'], fontSize=8, textColor=colors.HexColor('#c9a03d'), alignment=2, spaceAfter=6)))
    story.append(Spacer(1, 0.05*inch))
    story.append(Paragraph("VETTIFY INTELLIGENCE", title_style))
    story.append(Paragraph("Perception Gap Report", subtitle_style))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#c9a03d')))
    story.append(Spacer(1, 0.2*inch))
    
    story.append(Paragraph(f"Prepared for: <b>{client_name}</b>", body_text))
    story.append(Paragraph(f"Date: {datetime.now().strftime('%d %B %Y')}", body_text))
    story.append(Paragraph("Classification: Private & Confidential", body_text))
    story.append(Spacer(1, 0.2*inch))
    
    story.append(Paragraph("1. PERCEPTION GAP ANALYSIS", section_header))
    story.append(Paragraph(f"<b>Current Perception Level:</b> {perceived_level}", body_text))
    story.append(Paragraph(f"<b>Target Perception Level:</b> {target_level}", body_text))
    story.append(Paragraph(f"<b>Gap:</b> {gap_description}", ParagraphStyle('Gap', parent=body_text, textColor=colors.HexColor(gap_color), fontName='Helvetica-Bold')))
    story.append(Spacer(1, 0.1*inch))
    story.append(Paragraph(f"<b>Overall Perception Score:</b> {int(overall_score)} / 100", highlight))
    story.append(Spacer(1, 0.15*inch))
    
    story.append(Paragraph("2. BENCHMARK COMPARISON", section_header))
    benchmark_data = [
        ["Comparison Group", "Score", "Analysis"],
        ["Your Score", f"{int(overall_score)}/100", ""],
        ["Industry Average", "72/100", f"{'+' if overall_score > 72 else ''}{int(overall_score - 72)} vs average"],
        ["Top 10% Tier", "88/100", f"Need {88 - int(overall_score)} points to reach top tier"],
    ]
    bench_table = Table(benchmark_data, colWidths=[2.2*inch, 1.2*inch, 2.8*inch])
    bench_table.setStyle(TableStyle([
        ('FONTNAME', (0,0), (-1,-1), 'Helvetica'),
        ('FONTSIZE', (0,0), (-1,-1), 9),
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#0a1628')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('ALIGN', (1,0), (1,-1), 'CENTER'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e2e8f0')),
        ('TOPPADDING', (0,0), (-1,-1), 10),
        ('BOTTOMPADDING', (0,0), (-1,-1), 10),
    ]))
    story.append(bench_table)
    story.append(Spacer(1, 0.2*inch))
    
    # PAGE 2
    story.append(Paragraph("3. SCORE BREAKDOWN", section_header))
    breakdown_data = [
        ["Dimension", "Score", "Status", "What This Means"],
        ["Authority Positioning", f"{authority['score']}/100", authority['level'], "How decision-makers perceive your leadership weight"],
        ["Narrative Alignment", f"{narrative['score']}/100", narrative['level'], "Whether your story is consistent across platforms"],
        ["Visibility Footprint", f"{visibility['score']}/100", visibility['level'], "Your presence in media and public platforms"],
        ["Third-Party Validation", f"{validation['score']}/100", validation['level'], "External credibility signals and social proof"],
    ]
    breakdown_table = Table(breakdown_data, colWidths=[1.6*inch, 0.9*inch, 1.1*inch, 2.4*inch])
    breakdown_table.setStyle(TableStyle([
        ('FONTNAME', (0,0), (-1,-1), 'Helvetica'),
        ('FONTSIZE', (0,0), (-1,-1), 8),
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#0a1628')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('ALIGN', (1,0), (2,-1), 'CENTER'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e2e8f0')),
        ('TOPPADDING', (0,0), (-1,-1), 10),
        ('BOTTOMPADDING', (0,0), (-1,-1), 10),
    ]))
    story.append(breakdown_table)
    story.append(Spacer(1, 0.2*inch))
    
    story.append(Paragraph("4. DETAILED FINDINGS", section_header))
    
    story.append(Paragraph("Authority Positioning", subsection))
    story.append(Paragraph(f"<b>Score:</b> {authority['score']}/100 — {authority['level']}", body_text))
    for reason in authority['reasons']:
        story.append(Paragraph(f"• {reason}", body_text))
    story.append(Paragraph(f"<b>Action:</b> {authority['fixes'][0] if authority['fixes'] else 'Continue current approach'}", highlight))
    story.append(Spacer(1, 0.1*inch))
    
    story.append(Paragraph("Narrative Alignment", subsection))
    story.append(Paragraph(f"<b>Score:</b> {narrative['score']}/100 — {narrative['level']}", body_text))
    for reason in narrative['reasons']:
        story.append(Paragraph(f"• {reason}", body_text))
    story.append(Paragraph(f"<b>Action:</b> {narrative['fixes'][0] if narrative['fixes'] else 'Continue current approach'}", highlight))
    story.append(Spacer(1, 0.1*inch))
    
    # PAGE 3
    story.append(Paragraph("Visibility Footprint", subsection))
    story.append(Paragraph(f"<b>Score:</b> {visibility['score']}/100 — {visibility['level']}", body_text))
    for reason in visibility['reasons']:
        story.append(Paragraph(f"• {reason}", body_text))
    story.append(Paragraph(f"<b>Action:</b> {visibility['fixes'][0] if visibility['fixes'] else 'Continue current approach'}", highlight))
    story.append(Spacer(1, 0.1*inch))
    
    story.append(Paragraph("Third-Party Validation", subsection))
    story.append(Paragraph(f"<b>Score:</b> {validation['score']}/100 — {validation['level']}", body_text))
    for reason in validation['reasons']:
        story.append(Paragraph(f"• {reason}", body_text))
    story.append(Paragraph(f"<b>Action:</b> {validation['fixes'][0] if validation['fixes'] else 'Continue current approach'}", highlight))
    story.append(Spacer(1, 0.2*inch))
    
    story.append(Paragraph("5. ACTION PLAN", section_header))
    story.append(Paragraph("Complete these actions in priority order to close your perception gap:", body_text))
    story.append(Spacer(1, 0.05*inch))
    
    if authority['fixes']:
        story.append(Paragraph(f"1. {authority['fixes'][0]}", bullet))
    if narrative['fixes']:
        story.append(Paragraph(f"2. {narrative['fixes'][0]}", bullet))
    if visibility['fixes']:
        story.append(Paragraph(f"3. {visibility['fixes'][0]}", bullet))
    if validation['fixes']:
        story.append(Paragraph(f"4. {validation['fixes'][0]}", bullet))
    
    total_gain = 0
    if authority['score'] < 80:
        total_gain += 12
    if narrative['score'] < 80:
        total_gain += 8
    if visibility['score'] < 80:
        total_gain += 15
    if validation['score'] < 80:
        total_gain += 6
    
    new_score = min(100, int(overall_score) + total_gain)
    
    story.append(Spacer(1, 0.1*inch))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor('#e2e8f0')))
    story.append(Spacer(1, 0.05*inch))
    story.append(Paragraph(f"<b>Total Potential Improvement:</b> +{total_gain} points → {new_score}/100", highlight))
    story.append(Spacer(1, 0.2*inch))
    
    story.append(Paragraph("6. FINAL ASSESSMENT", section_header))
    if overall_score >= 80:
        story.append(Paragraph("You are already perceived as a decision-maker. Focus on expanding visibility and validation to reach strategic leader status.", body_text))
    elif overall_score >= 65:
        story.append(Paragraph("You are perceived as an operator. To be seen as a decision-maker, add leadership language to your profile and build external validation.", body_text))
    else:
        story.append(Paragraph("Your current positioning does not yet signal executive authority. Systematic rebuild of narrative, visibility, and validation signals is recommended.", body_text))
    story.append(Spacer(1, 0.15*inch))
    
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor('#e2e8f0')))
    story.append(Spacer(1, 0.05*inch))
    story.append(Paragraph(f"Confidential · Prepared for {client_name} · Valid for 60 days", 
                         ParagraphStyle('Footer', parent=styles['Normal'], fontSize=7, 
                                       textColor=colors.HexColor('#8a9bb0'), alignment=1, spaceAfter=4)))
    story.append(Paragraph("VETTIFY INTELLIGENCE — Perception Gap Engine", 
                         ParagraphStyle('Footer', parent=styles['Normal'], fontSize=7, 
                                       textColor=colors.HexColor('#8a9bb0'), alignment=1)))
    
    doc.build(story)
    buffer.seek(0)
    return buffer

# ================= SAMPLE REPORT =================

@app.route('/download-sample-report')
def download_sample_report():
    """Download sample perception gap report"""
    sample_data = {'full_name': 'Sample Client', 'position': 'Executive'}
    sample_text = """
    I am the founder of a B2B SaaS company in the fintech compliance space. 
    Previously I was Head of Operations at a major bank for 6 years leading a team of 45. 
    I have spoken at industry conferences and been featured in tech publications. 
    Currently raising a Series A round and expanding my board network.
    """
    pdf_buffer = generate_perception_gap_report(sample_data, sample_text)
    return send_file(pdf_buffer, as_attachment=True, download_name="perception_gap_report.pdf")

# ================= FRONTEND ROUTES =================

@app.route('/')
def home():
    return render_template_string('''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Vettify | Perception Intelligence</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root { --gold: #c9a03d; --dark: #0a1628; --cream: #faf8f5; }
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Inter', sans-serif; background: var(--cream); color: var(--dark); }
        .container { max-width: 1200px; margin: 0 auto; padding: 0 48px; }
        .navbar { padding: 32px 0; border-bottom: 1px solid rgba(0,0,0,0.05); }
        .navbar .container { display: flex; justify-content: space-between; align-items: center; }
        .logo { font-size: 24px; font-weight: 700; color: var(--dark); text-decoration: none; }
        .logo span { font-weight: 300; color: var(--gold); }
        .badge { background: #e8d5a3; padding: 4px 12px; border-radius: 30px; font-size: 10px; }
        .hero { padding: 80px 0; text-align: center; }
        .hero h1 { font-size: 48px; font-weight: 600; margin-bottom: 20px; }
        .hero p { font-size: 18px; color: #5b6e8c; max-width: 600px; margin: 0 auto; }
        .btn-primary { background: var(--dark); color: white; border: none; padding: 14px 36px; font-size: 14px; font-weight: 500; cursor: pointer; margin-top: 32px; }
        .btn-primary:hover { background: var(--gold); color: var(--dark); }
        .btn-outline { background: transparent; border: 1px solid var(--dark); padding: 14px 36px; font-size: 14px; cursor: pointer; margin-left: 16px; }
        .pricing { padding: 80px 0; background: white; }
        .pricing h2 { text-align: center; font-size: 32px; margin-bottom: 48px; }
        .pricing-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 32px; }
        .pricing-card { background: var(--cream); padding: 40px; border: 1px solid #e2e8f0; }
        .pricing-card:hover { border-color: var(--gold); }
        .pricing-tier { font-size: 12px; letter-spacing: 2px; color: var(--gold); margin-bottom: 16px; }
        .pricing-price { font-size: 36px; font-weight: 700; margin-bottom: 24px; }
        .btn-card { width: 100%; background: transparent; border: 1px solid var(--dark); padding: 12px; cursor: pointer; }
        .btn-card:hover { background: var(--dark); color: white; }
        .card-premium { border-top: 3px solid var(--gold); }
        .cta { background: var(--dark); color: white; padding: 80px 0; text-align: center; }
        .cta h2 { font-size: 28px; margin-bottom: 16px; }
        .btn-cta { background: var(--gold); color: var(--dark); border: none; padding: 16px 48px; font-weight: 600; cursor: pointer; }
        .footer { padding: 48px 0; text-align: center; border-top: 1px solid #e2e8f0; color: #8a9bb0; font-size: 12px; }
        @media (max-width: 900px) { .container { padding: 0 24px; } .hero h1 { font-size: 32px; } .pricing-grid { grid-template-columns: 1fr; } }
    </style>
</head>
<body>
    <nav class="navbar"><div class="container"><a href="/" class="logo">VETTIFY <span>INTELLIGENCE</span></a><span class="badge">Private Advisory</span></div></nav>
    <section class="hero"><div class="container"><h1>How are you perceived in high-trust environments?</h1><p>We measure perception gaps, benchmark against peers, and tell you exactly what to fix.</p><div><button class="btn-primary" onclick="openApplication()">Request Perception Audit →</button><button class="btn-outline" onclick="window.location.href='/download-sample-report'">View Sample Report →</button></div></div></section>
    <section class="pricing"><div class="container"><h2>Perception Intelligence Tiers</h2><div class="pricing-grid"><div class="pricing-card"><div class="pricing-tier">PROFESSIONAL</div><div class="pricing-price">R9,900<span style="font-size:14px;">/month</span></div><button class="btn-card" onclick="openApplication()">Request Access</button></div><div class="pricing-card"><div class="pricing-tier">EXECUTIVE</div><div class="pricing-price">R24,900<span style="font-size:14px;">/month</span></div><button class="btn-card" onclick="openApplication()">Request Access</button></div><div class="pricing-card card-premium"><div class="pricing-tier">ELITE ADVISORY</div><div class="pricing-price">R49,900<span style="font-size:14px;">/month</span></div><button class="btn-card" onclick="openApplication()">Request Access</button></div></div></div></section>
    <section class="cta"><div class="container"><h2>Applications reviewed manually. Limited capacity.</h2><button class="btn-cta" onclick="openApplication()">Request Perception Audit →</button></div></section>
    <footer class="footer"><div class="container"><p>VETTIFY INTELLIGENCE — PERCEPTION GAP ENGINE</p></div></footer>
    <script>function openApplication(){window.location.href='/apply';}</script>
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
    <title>Apply | Vettify</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600&display=swap" rel="stylesheet">
    <style>
        *{margin:0;padding:0;box-sizing:border-box}
        body{font-family:'Inter',sans-serif;background:#faf8f5;padding:60px 20px}
        .container{max-width:600px;margin:0 auto;background:white;padding:48px;border:1px solid #e2e8f0}
        h1{font-size:28px;margin-bottom:8px}
        .sub{color:#8a9bb0;margin-bottom:32px;font-size:13px}
        .form-group{margin-bottom:24px}
        label{display:block;font-size:11px;text-transform:uppercase;margin-bottom:8px;font-weight:600}
        input,select,textarea{width:100%;padding:12px;border:1px solid #e2e8f0;font-size:14px;font-family:inherit}
        input:focus,select:focus,textarea:focus{outline:none;border-color:#c9a03d}
        .btn-submit{width:100%;background:#0a1628;color:white;border:none;padding:14px;font-size:14px;font-weight:500;cursor:pointer;margin-top:16px}
        .btn-submit:hover{background:#c9a03d;color:#0a1628}
        .loading{display:none;text-align:center;margin-top:16px;color:#c9a03d}
        .note{font-size:11px;color:#8a9bb0;text-align:center;margin-top:24px}
        @media(max-width:600px){.container{padding:24px}}
    </style>
</head>
<body>
<div class="container">
    <h1>Apply for Perception Audit</h1>
    <div class="sub">Applications reviewed manually. Limited capacity.</div>
    <form id="applicationForm">
        <div class="form-group"><label>Full Name</label><input type="text" id="full_name" required></div>
        <div class="form-group"><label>Email</label><input type="email" id="email" required></div>
        <div class="form-group"><label>LinkedIn URL</label><input type="url" id="linkedin_url"></div>
        <div class="form-group"><label>Current Position</label><input type="text" id="position" placeholder="Founder, CEO, Executive..."></div>
        <div class="form-group"><label>If raising capital, what amount?</label><select id="funding_amount"><option>Not raising</option><option>Under R5M</option><option>R5M-R20M</option><option>R20M-R100M</option><option>R100M+</option></select></div>
        <div class="form-group"><label>Paste your LinkedIn profile text or bio</label><textarea id="profile_text" rows="6" placeholder="Paste your LinkedIn summary, bio, or profile description here..."></textarea></div>
        <button type="submit" class="btn-submit" id="submitBtn">Request Perception Audit →</button>
        <div class="loading" id="loading">Submitting...</div>
        <div class="note">Your application will be reviewed. Selected clients will receive a full perception gap report.</div>
    </form>
</div>
<script>
document.getElementById('applicationForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const btn = document.getElementById('submitBtn');
    const loading = document.getElementById('loading');
    btn.style.display = 'none';
    loading.style.display = 'block';
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
        if (res.ok) { alert('Application received. We will review and respond within 24 hours.'); window.location.href = '/'; }
        else { alert('Error submitting. Please try again.'); btn.style.display = 'block'; loading.style.display = 'none'; }
    } catch(err) { alert('Error submitting. Please try again.'); btn.style.display = 'block'; loading.style.display = 'none'; }
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
    conn.execute('''INSERT INTO applications (id, full_name, email, linkedin_url, position, funding_amount
