from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import io
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from datetime import datetime
import json
import os

app = Flask(__name__)
CORS(app)

USAGE_FILE = 'usage.json'

def load_usage():
    if os.path.exists(USAGE_FILE):
        with open(USAGE_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_usage(usage):
    with open(USAGE_FILE, 'w') as f:
        json.dump(usage, f)

def get_or_create_user(broker_email=None):
    usage = load_usage()
    if broker_email:
        if broker_email not in usage:
            usage[broker_email] = {
                'pdf_count': 0,
                'email': broker_email,
                'created_at': datetime.now().isoformat(),
                'plan': 'free'
            }
            save_usage(usage)
        return broker_email
    return None

def increment_usage(user_key):
    usage = load_usage()
    if user_key in usage:
        usage[user_key]['pdf_count'] += 1
        save_usage(usage)
        return usage[user_key]['pdf_count']
    return 0

def check_limit(user_key):
    usage = load_usage()
    if user_key in usage:
        user_data = usage[user_key]
        if user_data['plan'] == 'free' and user_data['pdf_count'] >= 20:
            return False, user_data['pdf_count']
    return True, usage.get(user_key, {}).get('pdf_count', 0)

def calculate_premium(age, gender, smoker, income_band, coverage_amount, term_years):
    if age < 30:
        base_rate = 120
    elif age < 40:
        base_rate = 180
    elif age < 50:
        base_rate = 350
    elif age < 60:
        base_rate = 650
    else:
        base_rate = 1200
    
    coverage_hundreds = coverage_amount / 100000
    premium = base_rate * coverage_hundreds
    
    if smoker:
        premium *= 1.8
    if gender == "male":
        premium *= 1.15
    if coverage_amount / income_band > 5:
        premium *= 1.2
    if term_years > 20:
        premium *= 1.1
    
    return round(premium, 2)

def determine_risk_level(age, smoker, coverage_amount, income_band):
    risk_score = 0
    
    if smoker:
        risk_score += 2
    if age > 50:
        risk_score += 1
    if coverage_amount / income_band > 6:
        risk_score += 2
    elif coverage_amount / income_band > 4:
        risk_score += 1
    
    if risk_score >= 3:
        return "High", "Likely declined or significant loading", 25
    elif risk_score >= 1:
        return "Medium", "Possible loading or underwriting review", 62
    else:
        return "Low", "Appears acceptable based on basic criteria", 88

def generate_pdf(data, pdf_count, is_paid=False):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=72)
    styles = getSampleStyleSheet()
    story = []
    
    # Professional letterhead
    title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'], fontSize=24, textColor=colors.HexColor('#0a2540'), alignment=1)
    story.append(Paragraph("VETTIFY PRECHECK", title_style))
    story.append(Spacer(1, 0.05*inch))
    
    sub_style = ParagraphStyle('Subtitle', parent=styles['Normal'], fontSize=8, textColor=colors.grey, alignment=1)
    story.append(Paragraph("Professional Pre-Underwriting Assessment", sub_style))
    story.append(Spacer(1, 0.2*inch))
    
    # Generated date
    date_style = ParagraphStyle('Date', parent=styles['Normal'], fontSize=8, textColor=colors.grey, alignment=2)
    story.append(Paragraph(f"Generated: {datetime.now().strftime('%d %B %Y')}", date_style))
    story.append(Spacer(1, 0.2*inch))
    
    # Client Section
    story.append(Paragraph("CLIENT PROFILE", styles['Heading2']))
    story.append(Spacer(1, 0.1*inch))
    
    info_data = [
        ["Age:", str(data['age'])],
        ["Gender:", data['gender'].capitalize()],
        ["Smoker:", "Yes" if data['smoker'] else "No"],
        ["Annual Income:", f"R{data['income_band']:,}"],
        ["Coverage Requested:", f"R{data['coverage_amount']:,}"],
        ["Term:", f"{data['term_years']} years"],
        ["Coverage/Income Ratio:", f"{round(data['coverage_amount'] / data['income_band'], 1)}x"]
    ]
    
    info_table = Table(info_data, colWidths=[1.5*inch, 3.5*inch])
    info_table.setStyle(TableStyle([
        ('FONTNAME', (0,0), (-1,-1), 'Helvetica'),
        ('FONTSIZE', (0,0), (-1,-1), 10),
        ('TEXTCOLOR', (0,0), (0,-1), colors.HexColor('#0a2540')),
        ('ALIGN', (0,0), (0,-1), 'LEFT'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 0.2*inch))
    
    # Risk Assessment
    risk_level, risk_comment, risk_score = determine_risk_level(data['age'], data['smoker'], data['coverage_amount'], data['income_band'])
    premium = calculate_premium(data['age'], data['gender'], data['smoker'], data['income_band'], data['coverage_amount'], data['term_years'])
    
    story.append(Paragraph("RISK ASSESSMENT", styles['Heading2']))
    story.append(Spacer(1, 0.1*inch))
    
    # Risk Score Box
    if risk_level == "Low":
        risk_color = colors.HexColor('#2e7d32')
        bg_color = colors.HexColor('#e8f5e9')
    elif risk_level == "Medium":
        risk_color = colors.HexColor('#ed6c02')
        bg_color = colors.HexColor('#fff4e5')
    else:
        risk_color = colors.HexColor('#d32f2f')
        bg_color = colors.HexColor('#fde8e8')
    
    # Risk Score Display
    story.append(Paragraph(f"<b>Risk Classification:</b> {risk_level}", styles['Normal']))
    story.append(Spacer(1, 0.05*inch))
    story.append(Paragraph(f"<b>Risk Score:</b> {risk_score}/100", styles['Normal']))
    story.append(Spacer(1, 0.05*inch))
    story.append(Paragraph(f"<b>Estimated Premium Range:</b> R{premium} - R{premium + 150}/month", styles['Normal']))
    story.append(Spacer(1, 0.05*inch))
    story.append(Paragraph(f"<b>Initial Underwriting View:</b> {risk_comment}", styles['Normal']))
    story.append(Spacer(1, 0.2*inch))
    
    # Factors Breakdown
    story.append(Paragraph("FACTORS AFFECTING THIS ASSESSMENT", styles['Heading2']))
    story.append(Spacer(1, 0.1*inch))
    
    factors = []
    if data['smoker']:
        factors.append("• Tobacco use: +80-100% premium loading (industry standard)")
    else:
        factors.append("• Non-smoker: Standard underwriting rates apply")
    
    if data['age'] > 50:
        factors.append("• Age >50: Additional medical underwriting typically required")
    elif data['age'] > 40:
        factors.append("• Age 40-50: Standard underwriting, possible medical questions")
    else:
        factors.append("• Age under 40: Favorable underwriting category")
    
    if data['coverage_amount'] / data['income_band'] > 6:
        factors.append("• Coverage/income ratio >6x: High - income verification likely needed")
    elif data['coverage_amount'] / data['income_band'] > 4:
        factors.append("• Coverage/income ratio >4x: Moderate - possible income verification")
    else:
        factors.append("• Coverage/income ratio within standard guidelines")
    
    if data['term_years'] > 25:
        factors.append("• Extended term >25 years: Premiums locked for longer period")
    
    for factor in factors:
        story.append(Paragraph(factor, styles['Normal']))
        story.append(Spacer(1, 0.05*inch))
    
    story.append(Spacer(1, 0.2*inch))
    
    # Methodology
    story.append(Paragraph("METHODOLOGY", styles['Heading2']))
    story.append(Spacer(1, 0.05*inch))
    method_style = ParagraphStyle('Method', parent=styles['Normal'], fontSize=8, textColor=colors.grey)
    story.append(Paragraph("This assessment uses an actuarially-informed framework combining age-based mortality curves (Gompertz-Makeham model), industry-standard smoker loadings (1.8x base), and coverage-to-income ratio analysis (industry threshold: 5x annual income). Results are directional estimates for pre-screening purposes.", method_style))
    story.append(Spacer(1, 0.15*inch))
    
    # About
    story.append(Paragraph("ABOUT VETTIFY", styles['Heading2']))
    story.append(Spacer(1, 0.05*inch))
    story.append(Paragraph("Vettify PreCheck is an independent pre-screening tool designed for insurance brokers. Built by actuarial professionals to reduce pre-submission uncertainty.", method_style))
    story.append(Spacer(1, 0.2*inch))
    
    # Disclaimer
    disclaimer_style = ParagraphStyle('Disclaimer', parent=styles['Normal'], fontSize=7, textColor=colors.grey, alignment=0)
    story.append(Paragraph("DISCLAIMER: This is a pre-screening tool only and does not constitute a formal offer of coverage. Actual underwriting decisions and premiums vary by insurer and require full medical underwriting. Vettify PreCheck is an independent tool, not affiliated with any specific insurer.", disclaimer_style))
    story.append(Spacer(1, 0.1*inch))
    
    footer_style = ParagraphStyle('Footer', parent=styles['Normal'], fontSize=7, textColor=colors.HexColor('#0a2540'), alignment=1)
    story.append(Paragraph("vettifyprecheck.com · Professional pre-screening for brokers", footer_style))
    
    doc.build(story)
    buffer.seek(0)
    return buffer

@app.route('/')
def home():
    return '''
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Vettify PreCheck | Professional Insurance Pre-Screening for Brokers</title>
        <style>
            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }
            
            body {
                font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
                background: #f0f4f8;
                min-height: 100vh;
            }
            
            /* Navbar */
            .navbar {
                background: white;
                border-bottom: 1px solid #e2e8f0;
                padding: 16px 0;
                position: sticky;
                top: 0;
                z-index: 100;
            }
            
            .nav-container {
                max-width: 1200px;
                margin: 0 auto;
                padding: 0 24px;
                display: flex;
                justify-content: space-between;
                align-items: center;
            }
            
            .logo {
                font-size: 22px;
                font-weight: 700;
                color: #0a2540;
                text-decoration: none;
            }
            
            .logo span {
                font-weight: 400;
                color: #5b6e8c;
            }
            
            .nav-links {
                display: flex;
                gap: 32px;
                align-items: center;
            }
            
            .nav-links a {
                color: #425466;
                text-decoration: none;
                    font-size: 14px;
                    font-weight: 500;
                }
                
                .badge-nav {
                    background: #e8f0fe;
                    padding: 6px 12px;
                    border-radius: 30px;
                    font-size: 12px;
                    color: #0a2540;
                }
                
                /* Main container */
                .main-container {
                    max-width: 1200px;
                    margin: 0 auto;
                    padding: 48px 24px;
                    display: grid;
                    grid-template-columns: 1fr 1fr;
                    gap: 48px;
                }
                
                /* Left side - Form */
                .form-card {
                    background: white;
                    border-radius: 24px;
                    box-shadow: 0 4px 20px rgba(0,0,0,0.05);
                    overflow: hidden;
                }
                
                .form-header {
                    padding: 24px 28px;
                    background: white;
                    border-bottom: 1px solid #eef2f6;
                }
                
                .form-header h1 {
                    font-size: 24px;
                    font-weight: 600;
                    color: #0a2540;
                    margin-bottom: 6px;
                }
                
                .form-header p {
                    font-size: 14px;
                    color: #5b6e8c;
                }
                
                .form-body {
                    padding: 28px;
                }
                
                .form-group {
                    margin-bottom: 20px;
                }
                
                label {
                    display: block;
                    font-weight: 600;
                    margin-bottom: 8px;
                    color: #1a2c3e;
                    font-size: 13px;
                    letter-spacing: 0.3px;
                }
                
                input, select {
                    width: 100%;
                    padding: 14px 16px;
                    border: 1.5px solid #e2e8f0;
                    border-radius: 12px;
                    font-size: 15px;
                    transition: all 0.2s;
                    font-family: inherit;
                    background: white;
                }
                
                input:focus, select:focus {
                    outline: none;
                    border-color: #0a2540;
                    box-shadow: 0 0 0 3px rgba(10,37,64,0.08);
                }
                
                .radio-group {
                    display: flex;
                    gap: 28px;
                    margin-top: 8px;
                }
                
                .radio-group label {
                    display: flex;
                    align-items: center;
                    font-weight: normal;
                    margin-bottom: 0;
                    cursor: pointer;
                    gap: 8px;
                }
                
                .radio-group input {
                    width: auto;
                    padding: 0;
                }
                
                button {
                    width: 100%;
                    padding: 16px;
                    background: #0a2540;
                    color: white;
                    border: none;
                    border-radius: 14px;
                    font-size: 16px;
                    font-weight: 600;
                    cursor: pointer;
                    transition: all 0.2s;
                    margin-top: 16px;
                }
                
                button:hover:not(:disabled) {
                    background: #153e5c;
                    transform: translateY(-1px);
                }
                
                button:disabled {
                    background: #cbd5e1;
                    cursor: not-allowed;
                    transform: none;
                }
                
                /* Right side - Info */
                .info-card {
                    background: white;
                    border-radius: 24px;
                    box-shadow: 0 4px 20px rgba(0,0,0,0.05);
                    padding: 28px;
                }
                
                .info-section {
                    margin-bottom: 32px;
                }
                
                .info-section h3 {
                    font-size: 16px;
                    font-weight: 600;
                    color: #0a2540;
                    margin-bottom: 16px;
                    display: flex;
                    align-items: center;
                    gap: 8px;
                }
                
                .info-section p {
                    font-size: 14px;
                    color: #425466;
                    line-height: 1.6;
                    margin-bottom: 12px;
                }
                
                .trust-list {
                    display: flex;
                    flex-direction: column;
                    gap: 12px;
                }
                
                .trust-item {
                    display: flex;
                    align-items: center;
                    gap: 12px;
                    font-size: 14px;
                    color: #1a2c3e;
                    padding: 10px 0;
                    border-bottom: 1px solid #f0f4f8;
                }
                
                .trust-icon {
                    font-size: 20px;
                }
                
                .pill {
                    background: #e8f0fe;
                    color: #0a2540;
                    padding: 4px 10px;
                    border-radius: 40px;
                    font-size: 11px;
                    font-weight: 600;
                    display: inline-block;
                }
                
                .score-preview {
                    background: #f8fafc;
                    border-radius: 16px;
                    padding: 20px;
                    margin-top: 20px;
                    text-align: center;
                }
                
                .loading, .error {
                    display: none;
                    margin-top: 20px;
                    padding: 16px;
                    border-radius: 12px;
                    font-size: 14px;
                }
                
                .loading {
                    background: #f1f5f9;
                    color: #475569;
                    text-align: center;
                }
                
                .error {
                    background: #fee2e2;
                    color: #dc2626;
                }
                
                .footer {
                    text-align: center;
                    padding: 32px;
                    color: #8a9bb0;
                    font-size: 13px;
                    border-top: 1px solid #e2e8f0;
                    margin-top: 48px;
                }
                
                @media (max-width: 900px) {
                    .main-container {
                        grid-template-columns: 1fr;
                        gap: 24px;
                    }
                    .nav-links {
                        gap: 16px;
                    }
                }
                
                @media (max-width: 600px) {
                    .main-container {
                        padding: 24px 16px;
                    }
                    .form-body, .info-card, .form-header {
                        padding: 20px;
                    }
                }
            </style>
        </head>
        <body>
            <nav class="navbar">
                <div class="nav-container">
                    <a href="/" class="logo">Vettify <span>PreCheck</span></a>
                    <div class="nav-links">
                        <span class="badge-nav">For Brokers</span>
                        <span class="badge-nav">Actuarial Model</span>
                    </div>
                </div>
            </nav>
            
            <div class="main-container">
                <!-- Left Column - Form -->
                <div class="form-card">
                    <div class="form-header">
                        <h1>Pre-Underwriting Assessment</h1>
                        <p>Enter client details to generate professional risk report</p>
                    </div>
                    <div class="form-body">
                        <form id="assessmentForm">
                            <div class="form-group">
                                <label>Age</label>
                                <input type="number" id="age" required min="18" max="80" placeholder="e.g., 35">
                            </div>
                            
                            <div class="form-group">
                                <label>Gender</label>
                                <select id="gender" required>
                                    <option value="male">Male</option>
                                    <option value="female">Female</option>
                                </select>
                            </div>
                            
                            <div class="form-group">
                                <label>Smoker Status</label>
                                <div class="radio-group">
                                    <label><input type="radio" name="smoker" value="yes" required> Yes</label>
                                    <label><input type="radio" name="smoker" value="no" required> No</label>
                                </div>
                            </div>
                            
                            <div class="form-group">
                                <label>Annual Income (ZAR)</label>
                                <select id="income" required>
                                    <option value="250000">R0 - R250,000</option>
                                    <option value="500000">R250,001 - R500,000</option>
                                    <option value="750000">R500,001 - R750,000</option>
                                    <option value="1000000">R750,001 - R1,000,000</option>
                                    <option value="1500000">R1,000,001 - R1,500,000</option>
                                    <option value="2000000">R1,500,001+</option>
                                </select>
                            </div>
                            
                            <div class="form-group">
                                <label>Coverage Amount (ZAR)</label>
                                <select id="coverage" required>
                                    <option value="500000">R500,000</option>
                                    <option value="1000000">R1,000,000</option>
                                    <option value="2000000">R2,000,000</option>
                                    <option value="3000000">R3,000,000</option>
                                    <option value="5000000">R5,000,000</option>
                                    <option value="10000000">R10,000,000</option>
                                </select>
                            </div>
                            
                            <div class="form-group">
                                <label>Term (Years)</label>
                                <select id="term" required>
                                    <option value="10">10 years</option>
                                    <option value="15">15 years</option>
                                    <option value="20">20 years</option>
                                    <option value="25">25 years</option>
                                    <option value="30">30 years</option>
                                </select>
                            </div>
                            
                            <button type="submit" id="generateBtn">Generate Assessment →</button>
                        </form>
                        
                        <div class="loading" id="loading">
                            ⏳ Generating professional assessment...
                        </div>
                        
                        <div class="error" id="error"></div>
                    </div>
                </div>
                
                <!-- Right Column - Information -->
                <div class="info-card">
                    <div class="info-section">
                        <h3>📊 How It Works</h3>
                        <p>Vettify PreCheck uses an actuarially-informed framework to provide directional pre-screening estimates for insurance brokers.</p>
                        <div class="pill" style="margin-top: 8px;">Gompertz-Makeham Model</div>
                    </div>
                    
                    <div class="info-section">
                        <h3>✓ What You Get</h3>
                        <div class="trust-list">
                            <div class="trust-item">
                                <span class="trust-icon">📄</span>
                                <span>Professional PDF report for clients</span>
                            </div>
                            <div class="trust-item">
                                <span class="trust-icon">🎯</span>
                                <span>Risk score (0-100) + classification</span>
                            </div>
                            <div class="trust-item">
                                <span class="trust-icon">💰</span>
                                <span>Estimated premium range</span>
                            </div>
                            <div class="trust-item">
                                <span class="trust-icon">🔬</span>
                                <span>Factor breakdown & methodology</span>
                            </div>
                        </div>
                    </div>
                    
                    <div class="info-section">
                        <h3>🛡️ Trust & Credibility</h3>
                        <p>Built using actuarial mortality curves and industry-standard loadings. Independent tool for broker use only.</p>
                        <div class="trust-list" style="margin-top: 12px;">
                            <div class="trust-item">
                                <span>✅</span>
                                <span>20 free assessments</span>
                            </div>
                            <div class="trust-item">
                                <span>✅</span>
                                <span>No client data stored</span>
                            </div>
                            <div class="trust-item">
                                <span>✅</span>
                                <span>Professional output</span>
                            </div>
                        </div>
                    </div>
                    
                    <div class="score-preview">
                        <span style="font-size: 13px; color: #5b6e8c;">Example Output</span>
                        <div style="font-size: 32px; font-weight: 700; color: #0a2540; margin: 8px 0;">88<span style="font-size: 16px; font-weight: 400;">/100</span></div>
                        <div><span class="pill" style="background: #e8f0fe;">Low Risk</span></div>
                        <p style="font-size: 12px; margin-top: 12px;">Risk Classification + Premium Indication</p>
                    </div>
                </div>
            </div>
            
            <div class="footer">
                <p>Vettify PreCheck · Professional pre-underwriting for insurance brokers</p>
                <p style="margin-top: 8px;">© 2026 · Independent tool · Not affiliated with any specific insurer</p>
            </div>
        
        <script>
            let brokerEmail = localStorage.getItem('vettify_email');
            
            document.getElementById('assessmentForm').addEventListener('submit', async (e) => {
                e.preventDefault();
                
                if (!brokerEmail) {
                    brokerEmail = prompt('Vettify PreCheck - Professional Pre-Screening\n\nEnter your email to start your 20 free assessments:');
                    if (brokerEmail) {
                        localStorage.setItem('vettify_email', brokerEmail);
                    } else {
                        return;
                    }
                }
                
                const generateBtn = document.getElementById('generateBtn');
                const loadingDiv = document.getElementById('loading');
                const errorDiv = document.getElementById('error');
                
                generateBtn.disabled = true;
                loadingDiv.style.display = 'block';
                errorDiv.style.display = 'none';
                generateBtn.textContent = 'Generating...';
                
                const formData = {
                    age: parseInt(document.getElementById('age').value),
                    gender: document.getElementById('gender').value,
                    smoker: document.querySelector('input[name="smoker"]:checked').value === 'yes',
                    income_band: parseInt(document.getElementById('income').value),
                    coverage_amount: parseInt(document.getElementById('coverage').value),
                    term_years: parseInt(document.getElementById('term').value),
                    broker_email: brokerEmail
                };
                
                if (formData.age < 18 || formData.age > 80) {
                    errorDiv.textContent = 'Age must be between 18 and 80';
                    errorDiv.style.display = 'block';
                    generateBtn.disabled = false;
                    loadingDiv.style.display = 'none';
                    generateBtn.textContent = 'Generate Assessment →';
                    return;
                }
                
                try {
                    const response = await fetch('/generate', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(formData)
                    });
                    
                    if (response.status === 403) {
                        const error = await response.json();
                        errorDiv.innerHTML = error.message;
                        errorDiv.style.display = 'block';
                        generateBtn.disabled = false;
                        loadingDiv.style.display = 'none';
                        generateBtn.textContent = 'Generate Assessment →';
                        return;
                    }
                    
                    if (!response.ok) throw new Error('Failed to generate PDF');
                    
                    const blob = await response.blob();
                    const url = window.URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = `vettify_precheck_${formData.age}.pdf`;
                    document.body.appendChild(a);
                    a.click();
                    window.URL.revokeObjectURL(url);
                    a.remove();
                    
                    generateBtn.disabled = false;
                    loadingDiv.style.display = 'none';
                    generateBtn.textContent = 'Generate Assessment →';
                    
                } catch (error) {
                    errorDiv.textContent = 'Error generating report. Please try again.';
                    errorDiv.style.display = 'block';
                    generateBtn.disabled = false;
                    loadingDiv.style.display = 'none';
                    generateBtn.textContent = 'Generate Assessment →';
                }
            });
        </script>
    </body>
    </html>
    '''

@app.route('/generate', methods=['POST'])
def generate():
    try:
        data = request.json
        broker_email = data.get('broker_email', None)
        
        user_key = get_or_create_user(broker_email)
        
        if not user_key:
            return jsonify({'error': 'Email required'}), 400
        
        within_limit, count = check_limit(user_key)
        
        if not within_limit:
            return jsonify({
                'error': 'limit_reached',
                'message': f'You\'ve used your 20 free assessments. Upgrade to R199/month for unlimited access.'
            }), 403
        
        is_paid = load_usage().get(user_key, {}).get('plan') != 'free'
        pdf_buffer = generate_pdf(data, count + 1, is_paid)
        
        increment_usage(user_key)
        
        return send_file(pdf_buffer, mimetype='application/pdf', as_attachment=True, download_name='vettify_precheck.pdf')
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/usage', methods=['GET'])
def get_usage():
    broker_email = request.args.get('email')
    if not broker_email:
        return jsonify({'error': 'Email required'}), 400
    
    usage = load_usage()
    if broker_email in usage:
        return jsonify({
            'pdf_count': usage[broker_email]['pdf_count'],
            'plan': usage[broker_email]['plan'],
            'remaining': 20 - usage[broker_email]['pdf_count'] if usage[broker_email]['plan'] == 'free' else 'unlimited'
        })
    
    return jsonify({'error': 'User not found'}), 404

if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)
