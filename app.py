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
# Each dimension: score (0-100), reasons, fixes

def analyze_authority_signal(text):
    """Analyze how well the profile signals decision-making authority"""
    score = 70
    reasons = []
    fixes = []
    
    # Check for decision-making language
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
    
    # Ensure score stays in range
    score = max(0, min(100, score))
    
    # Determine level
    if score >= 80:
        level = "Strong"
    elif score >= 60:
        level = "Developing"
    else:
        level = "Weak"
    
    return {
        'score': score,
        'level': level,
        'reasons': reasons[:2],
        'fixes': fixes[:2]
    }

def analyze_narrative_alignment(text):
    """Analyze narrative consistency and clarity"""
    score = 72
    reasons = []
    fixes = []
    
    # Check for clear positioning
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
    
    # Check for competing narratives
    competitive_words = ['also', 'additionally', 'in addition', 'furthermore']
    has_competitive = any(word in text.lower() for word in competitive_words)
    
    if has_competitive:
        score -= 8
        reasons.append("Multiple competing narratives dilute your core positioning")
        fixes.append("Identify ONE core story and remove conflicting messages")
    
    # Ensure score stays in range
    score = max(0, min(100, score))
    
    if score >= 80:
        level = "Aligned"
    elif score >= 60:
        level = "Developing"
    else:
        level = "Fragmented"
    
    return {
        'score': score,
        'level': level,
        'reasons': reasons[:2],
        'fixes': fixes[:2]
    }

def analyze_visibility_footprint(text):
    """Analyze public visibility and third-party validation"""
    score = 60
    reasons = []
    fixes = []
    
    # Check for media mentions
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
    
    # Check for associations
    assoc_words = ['board', 'advisor', 'member', 'fellow', 'committee', 'chair']
    has_associations = any(word in text.lower() for word in assoc_words)
    
    if not has_associations:
        score -= 10
        reasons.append("Missing visible association markers like board seats or advisory roles")
        fixes.append("Add any board positions, advisory roles, or selective memberships to your profile")
    else:
        score += 5
    
    # Ensure score stays in range
    score = max(0, min(100, score))
    
    if score >= 80:
        level = "Strong"
    elif score >= 60:
        level = "Building"
    else:
        level = "Under-Optimised"
    
    return {
        'score': score,
        'level': level,
        'reasons': reasons[:2],
        'fixes': fixes[:2]
    }

def analyze_validation_signal(text):
    """Analyze social proof and third-party validation"""
    score = 65
    reasons = []
    fixes = []
    
    # Check for social proof
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
    
    # Check for measurable results
    result_words = ['increased', 'grew', 'saved', 'generated', 'achieved', 'won']
    has_results = any(word in text.lower() for word in result_words)
    
    if not has_results:
        score -= 8
        reasons.append("Missing measurable results or specific achievements")
        fixes.append("Add quantitative outcomes (e.g., 'grew revenue by X%' or 'saved Y hours')")
    
    # Ensure score stays in range
    score = max(0, min(100, score))
    
    if score >= 80:
        level = "Strong"
    elif score >= 60:
        level = "Developing"
    else:
        level = "Weak"
    
    return {
        'score': score,
        'level': level,
        'reasons': reasons[:2],
        'fixes': fixes[:2]
    }

# ================= PERCEPTION GAP REPORT GENERATION =================

def generate_perception_gap_report(client_data, profile_text):
    """Generate professional perception gap report"""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, 
                           topMargin=72, bottomMargin=72, 
                           leftMargin=72, rightMargin=72)
    styles = getSampleStyleSheet()
    story = []
    
    # Custom styles for professional look
    title_style = ParagraphStyle('Title', parent=styles['Title'], fontSize=26, textColor=colors.HexColor('#0a1628'), alignment=1, spaceAfter=8, fontName='Helvetica-Bold')
    subtitle_style = ParagraphStyle('Subtitle', parent=styles['Normal'], fontSize=9, textColor=colors.HexColor('#8a9bb0'), alignment=1, spaceAfter=24)
    section_header = ParagraphStyle('SectionHeader', parent=styles['Heading2'], fontSize=14, textColor=colors.HexColor('#0a1628'), spaceAfter=12, spaceBefore=20, fontName='Helvetica-Bold')
    subsection = ParagraphStyle('Subsection', parent=styles['Heading3'], fontSize=12, textColor=colors.HexColor('#0a1628'), spaceAfter=8, spaceBefore=12, fontName='Helvetica-Bold')
    body_text = ParagraphStyle('BodyText', parent=styles['Normal'], fontSize=10, textColor=colors.HexColor('#2c3e50'), spaceAfter=8, leading=16)
    highlight = ParagraphStyle('Highlight', parent=styles['Normal'], fontSize=10, textColor=colors.HexColor('#c9a03d'), spaceAfter=8, leading=16, fontName='Helvetica-Bold')
    bullet = ParagraphStyle('Bullet', parent=styles['Normal'], fontSize=10, textColor=colors.HexColor('#2c3e50'), spaceAfter=6, leftIndent=16, bulletIndent=0)
    
    # Run all analyses
    authority = analyze_authority_signal(profile_text)
    narrative = analyze_narrative_alignment(profile_text)
    visibility = analyze_visibility_footprint(profile_text)
    validation = analyze_validation_signal(profile_text)
    
    # Calculate overall score
    overall_score = (authority['score'] + narrative['score'] + visibility['score'] + validation['score']) / 4
    
    # Determine perception levels
    if overall_score >= 80:
        perceived_level = "Decision-Maker"
        target_level = "Strategic Leader"
        gap_description = "Small refinement needed"
        gap_color = "#16a34a"
    elif overall_score >= 65:
        perceived_level = "Operator / Contributor"
        target_level = "Decision-Maker"
        gap_description = "Moderate - authority signals need strengthening"
        gap_color = "#ea580c"
    else:
        perceived_level = "Individual Contributor"
        target_level = "Executive / Decision-Maker"
        gap_description = "Large - foundational repositioning required"
        gap_color = "#dc2626"
    
    client_name = client_data.get('full_name', 'Private Client')
    
    # ================= PAGE 1 =================
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
    
    # Section 1: Perception Gap
    story.append(Paragraph("1. PERCEPTION GAP ANALYSIS", section_header))
    story.append(Paragraph(f"<b>Current Perception Level:</b> {perceived_level}", body_text))
    story.append(Paragraph(f"<b>Target Perception Level:</b> {target_level}", body_text))
    story.append(Paragraph(f"<b>Gap:</b> {gap_description}", ParagraphStyle('Gap', parent=body_text, textColor=colors.HexColor(gap_color), fontName='Helvetica-Bold')))
    story.append(Spacer(1, 0.1*inch))
    story.append(Paragraph(f"<b>Overall Perception Score:</b> {int(overall_score)} / 100", highlight))
    story.append(Spacer(1, 0.15*inch))
    
    # Section 2: Benchmark Comparison
    story.append(Paragraph("2. BENCHMARK COMPARISON", section_header))
    
    benchmark_data = [
        ["Comparison Group", "Score", "Analysis"],
        ["Your Score", f"{int(overall_score)}/100", ""],
        ["Industry Average (Founders)", "72/100", f"{'+' if overall_score > 72 else ''}{int(overall_score - 72)} points vs average"],
        ["Top 10% Tier", "88/100", f"Need {88 - int(overall_score)} points to reach top tier"],
    ]
    
    bench_table = Table(benchmark_data, colWidths=[2.2*inch, 1.2*inch, 2.8*inch])
    bench_table.setStyle(TableStyle([
        ('FONTNAME', (0,0), (-1,-1), 'Helvetica'),
        ('FONTSIZE', (0,0), (-1,-1), 9),
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#0a1628')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('ALIGN', (1,0), (1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e2e8f0')),
        ('TOPPADDING', (0,0), (-1,-1), 10),
        ('BOTTOMPADDING', (0,0), (-1,-1), 10),
        ('LEFTPADDING', (0,0), (-1,-1), 12),
        ('RIGHTPADDING', (0,0), (-1,-1), 12),
    ]))
    story.append(bench_table)
    story.append(Spacer(1, 0.2*inch))
    
    # ================= PAGE 2 =================
    story.append(Paragraph("3. SCORE BREAKDOWN", section_header))
    
    breakdown_data = [
        ["Dimension", "Score", "Status", "Description"],
        ["Authority Positioning", f"{authority['score']}/100", authority['level'], "How decision-makers perceive your leadership weight"],
        ["Narrative Alignment", f"{narrative['score']}/100", narrative['level'], "Consistency of your story across platforms"],
        ["Visibility Footprint", f"{visibility['score']}/100", visibility['level'], "Your presence in media, speaking, and public platforms"],
        ["Third-Party Validation", f"{validation['score']}/100", validation['level'], "External credibility signals and social proof"],
    ]
    
    breakdown_table = Table(breakdown_data, colWidths=[1.6*inch, 0.9*inch, 1.1*inch, 2.4*inch])
    breakdown_table.setStyle(TableStyle([
        ('FONTNAME', (0,0), (-1,-1), 'Helvetica'),
        ('FONTSIZE', (0,0), (-1,-1), 9),
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#0a1628')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('ALIGN', (1,0), (2,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e2e8f0')),
        ('TOPPADDING', (0,0), (-1,-1), 10),
        ('BOTTOMPADDING', (0,0), (-1,-1), 10),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
        ('RIGHTPADDING', (0,0), (-1,-1), 8),
    ]))
    story.append(breakdown_table)
    story.append(Spacer(1, 0.2*inch))
    
    # Section 4: Detailed Analysis
    story.append(Paragraph("4. DETAILED ANALYSIS", section_header))
    
    # Authority Positioning
    story.append(Paragraph("Authority Positioning", subsection))
    story.append(Paragraph(f"<b>Current Score:</b> {authority['score']}/100 — {authority['level']}", body_text))
    for reason in authority['reasons']:
        story.append(Paragraph(f"• {reason}", bullet))
    story.append(Paragraph("<b>Recommended Action:</b> " + authority['fixes'][0] if authority['fixes'] else "", highlight))
    story.append(Spacer(1, 0.1*inch))
    
    # Narrative Alignment
    story.append(Paragraph("Narrative Alignment", subsection))
    story.append(Paragraph(f"<b>Current Score:</b> {narrative['score']}/100 — {narrative['level']}", body_text))
    for reason in narrative['reasons']:
        story.append(Paragraph(f"• {reason}", bullet))
    story.append(Paragraph("<b>Recommended Action:</b> " + narrative['fixes'][0] if narrative['fixes'] else "", highlight))
    story.append(Spacer(1, 0.1*inch))
    
    # ================= PAGE 3 =================
    # Visibility Footprint
    story.append(Paragraph("Visibility Footprint", subsection))
    story.append(Paragraph(f"<b>Current Score:</b> {visibility['score']}/100 — {visibility['level']}", body_text))
    for reason in visibility['reasons']:
        story.append(Paragraph(f"• {reason}", bullet))
    story.append(Paragraph("<b>Recommended Action:</b> " + visibility['fixes'][0] if visibility['fixes'] else "", highlight))
    story.append(Spacer(1, 0.1*inch))
    
    # Third-Party Validation
    story.append(Paragraph("Third-Party Validation", subsection))
    story.append(Paragraph(f"<b>Current Score:</b> {validation['score']}/100 — {validation['level']}", body_text))
    for reason in validation['reasons']:
        story.append(Paragraph(f"• {reason}", bullet))
    story.append(Paragraph("<b>Recommended Action:</b> " + validation['fixes'][0] if validation['fixes'] else "", highlight))
    story.append(Spacer(1, 0.2*inch))
    
    # Section 5: Action Plan
    story.append(Paragraph("5. ACTIONABLE IMPROVEMENT PLAN", section_header))
    
    # Collect all actions with priority levels
    action_items = []
    
    if authority['fixes']:
        action_items.append({
            'priority': 'HIGH',
            'action': authority['fixes'][0],
            'impact': '+12 to +15 points',
            'timeline': '24-48 hours'
        })
    
    if narrative['fixes']:
        action_items.append({
            'priority': 'HIGH',
            'action': narrative['fixes'][0],
            'impact': '+8 to +10 points',
            'timeline': '1 week'
        })
    
    if visibility['fixes']:
        action_items.append({
            'priority': 'MEDIUM',
            'action': visibility['fixes'][0],
            'impact': '+15 to +20 points',
            'timeline': '60-90 days'
        })
    
    if validation['fixes']:
        action_items.append({
            'priority': 'MEDIUM',
            'action': validation['fixes'][0],
            'impact': '+6 to +10 points',
            'timeline': '30 days'
        })
    
    for item in action_items:
        story.append(Paragraph(f"<b>{item['priority']} PRIORITY</b>", subsection))
        story.append(Paragraph(f"<b>Action:</b> {item['action']}", body_text))
        story.append(Paragraph(f"<b>Expected Impact:</b> {item['impact']} to your perception score", body_text))
        story.append(Paragraph(f"<b>Timeline:</b> {item['timeline']}", body_text))
        story.append(Spacer(1, 0.08*inch))
    
    # Calculate total potential gain
    total_gain = 0
    if authority['fixes']:
        total_gain += 12
    if narrative['fixes']:
        total_gain += 8
    if visibility['fixes']:
        total_gain += 15
    if validation['fixes']:
        total_gain += 6
    
    new_score = min(100, int(overall_score) + total_gain)
    
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor('#e2e8f0')))
    story.append(Spacer(1, 0.08*inch))
    story.append(Paragraph(f"<b>Total Potential Improvement:</b> +{total_gain} points → {new_score}/100", highlight))
    
    if new_score >= 80:
        story.append(Paragraph("This would place you in the top tier of perception scores among your peers.", body_text))
    elif new_score >= 70:
        story.append(Paragraph("This would place you above the industry average for founders and executives.", body_text))
    
    story.append(Spacer(1, 0.2*inch))
    
    # Section 6: Cost of Gap
    story.append(Paragraph("6. COST OF THIS GAP", section_header))
    story.append(Paragraph("If left unaddressed, current perception gaps may result in:", body_text))
    story.append(Spacer(1, 0.05*inch))
    story.append(Paragraph("• Slower trust-building with investors, partners, and key stakeholders", bullet))
    story.append(Paragraph("• Potential underestimation of your capability in competitive environments", bullet))
    story.append(Paragraph("• Missed opportunities that favor individuals with stronger authority signals", bullet))
    story.append(Paragraph("• Extended time required to establish credibility in new relationships", bullet))
    story.append(Spacer(1, 0.15*inch))
    
    # Section 7: Final Diagnostic
    story.append(Paragraph("7. FINAL DIAGNOSTIC", section_header))
    story.append(Paragraph("Your current positioning is not weak — it is under-amplified relative to your actual capability.", highlight))
    story.append(Spacer(1, 0.05*inch))
    story.append(Paragraph("The gap between how you are perceived and how you should be perceived is measurable and solvable. With systematic execution of the actions above, perception alignment is achievable within 90 days.", body_text))
    story.append(Spacer(1, 0.2*inch))
    
    # Footer
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor('#e2e8f0')))
    story.append(Spacer(1, 0.05*inch))
    story.append(Paragraph(f"Confidential Briefing · Prepared for {client_name} · Valid for 60 days", 
                         ParagraphStyle('Footer', parent=styles['Normal'], fontSize=7, 
                                       textColor=colors.HexColor('#8a9bb0'), alignment=1, spaceAfter=4)))
    story.append(Paragraph("VETTIFY INTELLIGENCE — Perception Gap Engine", 
                         ParagraphStyle('Footer', parent=styles['Normal'], fontSize=7, 
                                       textColor=colors.HexColor('#8a9bb0'), alignment=1)))
    
    doc.build(story)
    buffer.seek(0)
    return buffer

# ================= SAMPLE REPORT ENDPOINT =================

@app.route('/download-sample-report')
def download_sample_report():
    """Download sample perception gap report"""
    sample_data = {'full_name': 'Sample Client', 'position': 'Executive'}
    sample_text = """
    I am a founder building a SaaS company in the fintech space. Previously worked in operations 
    at a large bank for 8 years. Looking to raise my Series A round and expand my network with 
    institutional investors. I have a team of 12 people and we've grown 200% year over year.
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
        :root {
            --gold: #c9a03d;
            --dark: #0a1628;
            --cream: #faf8f5;
        }
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        body {
            font-family: 'Inter', sans-serif;
            background: var(--cream);
            color: var(--dark);
            line-height: 1.5;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 0 48px;
        }
        .navbar {
            padding: 32px 0;
            border-bottom: 1px solid rgba(0,0,0,0.05);
        }
        .navbar .container {
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .logo {
            font-size: 24px;
            font-weight: 700;
            color: var(--dark);
            text-decoration: none;
        }
        .logo span {
            font-weight: 300;
            color: var(--gold);
        }
        .badge {
            background: #e8d5a3;
            padding: 4px 12px;
            border-radius: 30px;
            font-size: 10px;
            letter-spacing: 1px;
        }
        .hero {
            padding: 80px 0;
            text-align: center;
        }
        .hero h1 {
            font-size: 48px;
            font-weight: 600;
            margin-bottom: 20px;
            line-height: 1.2;
        }
        .hero p {
            font-size: 18px;
            color: #5b6e8c;
            max-width: 600px;
            margin: 0 auto;
        }
        .btn-primary {
            background: var(--dark);
            color: white;
            border: none;
            padding: 14px 36px;
            font-size: 14px;
            font-weight: 500;
            cursor: pointer;
            margin-top: 32px;
            transition: all 0.3s;
        }
        .btn-primary:hover {
            background: var(--gold);
            color: var(--dark);
        }
        .btn-outline {
            background: transparent;
            border: 1px solid var(--dark);
            color: var(--dark);
            padding: 14px 36px;
            font-size: 14px;
            cursor: pointer;
            margin-left: 16px;
            transition: all 0.3s;
        }
        .btn-outline:hover {
            background: var(--dark);
            color: white;
        }
        .pricing {
            padding: 80px 0;
            background: white;
        }
        .pricing h2 {
            text-align: center;
            font-size: 32px;
            margin-bottom: 48px;
        }
        .pricing-grid {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 32px;
        }
        .pricing-card {
            background: var(--cream);
            padding: 40px;
            border: 1px solid #e2e8f0;
            transition: all 0.3s;
        }
        .pricing-card:hover {
            transform: translateY(-4px);
            border-color: var(--gold);
        }
        .pricing-tier {
            font-size: 12px;
            letter-spacing: 2px;
            color: var(--gold);
            margin-bottom: 16px;
        }
        .pricing-price {
            font-size: 36px;
            font-weight: 700;
            margin-bottom: 24px;
        }
        .pricing-price small {
            font-size: 14px;
            font-weight: 400;
        }
        .btn-card {
            width: 100%;
            background: transparent;
            border: 1px solid var(--dark);
            padding: 12px;
            cursor: pointer;
            transition: all 0.3s;
        }
        .btn-card:hover {
            background: var(--dark);
            color: white;
        }
        .card-premium {
            border-top: 3px solid var(--gold);
        }
        .cta {
            background: var(--dark);
            color: white;
            padding: 80px 0;
            text-align: center;
        }
        .cta h2 {
            font-size: 28px;
            margin-bottom: 16px;
        }
        .btn-cta {
            background: var(--gold);
            color: var(--dark);
            border: none;
            padding: 16px 48px;
            font-weight: 600;
            cursor: pointer;
            font-size: 14px;
            transition: all 0.3s;
        }
        .btn-cta:hover {
            opacity: 0.9;
        }
        .footer {
            padding: 48px 0;
            text-align: center;
            border-top: 1px solid #e2e8f0;
            color: #8a9bb0;
            font-size: 12px;
        }
        @media (max-width: 900px) {
            .container {
                padding: 0 24px;
            }
            .hero h1 {
                font-size: 32px;
            }
            .pricing-grid {
                grid-template-columns: 1fr;
            }
        }
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
            <h1>How are you perceived in high-trust environments?</h1>
            <p>We measure perception gaps, benchmark against peers, and tell you exactly what to fix.</p>
            <div>
                <button class="btn-primary" onclick="openApplication()">Request Perception Audit →</button>
                <button class="btn-outline" onclick="window.location.href='/download-sample-report'">View Sample Report →</button>
            </div>
        </div>
    </section>

    <section class="pricing">
        <div class="container">
            <h2>Perception Intelligence Tiers</h2>
            <div class="pricing-grid">
                <div class="pricing-card">
                    <div class="pricing-tier">PROFESSIONAL</div>
                    <div class="pricing-price">R9,900<span style="font-size:14px;">/month</span></div>
                    <button class="btn-card" onclick="openApplication()">Request Access</button>
                </div>
                <div class="pricing-card">
                    <div class="pricing-tier">EXECUTIVE</div>
                    <div class="pricing-price">R24,900<span style="font-size:14px;">/month</span></div>
                    <button class="btn-card" onclick="openApplication()">Request Access</button>
                </div>
                <div class="pricing-card card-premium">
                    <div class="pricing-tier">ELITE ADVISORY</div>
                    <div class="pricing-price">R49,900<span style="font-size:14px;">/month</span></div>
                    <button class="btn-card" onclick="openApplication()">Request Access</button>
                </div>
            </div>
        </div>
    </section>

    <section class="cta">
        <div class="container">
            <h2>Applications reviewed manually. Limited capacity.</h2>
            <button class="btn-cta" onclick="openApplication()">Request Perception Audit →</button>
        </div>
    </section>

    <footer class="footer">
        <div class="container">
            <p>VETTIFY INTELLIGENCE — PERCEPTION GAP ENGINE</p>
        </div>
    </footer>

    <script>
        function openApplication() {
            window.location.href = '/apply';
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
    <title>Apply | Vettify Intelligence</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600&display=swap" rel="stylesheet">
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        body {
            font-family: 'Inter', sans-serif;
            background: #faf8f5;
            padding: 60px 20px;
        }
        .container {
            max-width: 600px;
            margin: 0 auto;
            background: white;
            padding: 48px;
            border: 1px solid #e2e8f0;
        }
        h1 {
            font-size: 28px;
            margin-bottom
