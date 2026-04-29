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
    
    # Professional header
    title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'], fontSize=24, textColor=colors.HexColor('#0d3b66'), alignment=1)
    story.append(Paragraph("VETTIFY PRECHECK", title_style))
    story.append(Spacer(1, 0.05*inch))
    
    sub_style = ParagraphStyle('Subtitle', parent=styles['Normal'], fontSize=9, textColor=colors.grey, alignment=1)
    story.append(Paragraph("Professional Pre-Underwriting Assessment", sub_style))
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
        ["Term:", f"{data['term_years']} years"]
    ]
    
    info_table = Table(info_data, colWidths=[1.5*inch, 3.5*inch])
    info_table.setStyle(TableStyle([
        ('FONTNAME', (0,0), (-1,-1), 'Helvetica'),
        ('FONTSIZE', (0,0), (-1,-1), 10),
        ('TEXTCOLOR', (0,0), (0,-1), colors.HexColor('#0d3b66')),
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
    
    story.append(Paragraph(f"<b>Risk Classification:</b> {risk_level}", styles['Normal']))
    story.append(Spacer(1, 0.05*inch))
    story.append(Paragraph(f"<b>Risk Score:</b> {risk_score}/100", styles['Normal']))
    story.append(Spacer(1, 0.05*inch))
    story.append(Paragraph(f"<b>Estimated Premium Range:</b> R{premium} - R{premium + 150}/month", styles['Normal']))
    story.append(Spacer(1, 0.05*inch))
    story.append(Paragraph(f"<b>Initial Underwriting View:</b> {risk_comment}", styles['Normal']))
    story.append(Spacer(1, 0.2*inch))
    
    # Factors Affecting Risk
    story.append(Paragraph("FACTORS AFFECTING THIS ASSESSMENT", styles['Heading2']))
    story.append(Spacer(1, 0.1*inch))
    
    factors = []
    if data['smoker']:
        factors.append("• Tobacco use: +80-100% premium loading (industry standard)")
    if data['age'] > 50:
        factors.append("• Age >50: Additional medical underwriting typically required")
    if data['coverage_amount'] / data['income_band'] > 5:
        factors.append("• Coverage/income ratio >5x: Income verification likely needed")
    if data['term_years'] > 25:
        factors.append("• Extended term: Premiums locked for longer period")
    
    if not factors:
        factors.append("• No major risk factors identified based on basic criteria")
        factors.append("• Standard underwriting process recommended")
    
    for factor in factors:
        story.append(Paragraph(factor, styles['Normal']))
        story.append(Spacer(1, 0.05*inch))
    
    story.append(Spacer(1, 0.2*inch))
    
    # Methodology
    story.append(Paragraph("METHODOLOGY", styles['Heading2']))
    story.append(Spacer(1, 0.05*inch))
    method_style = ParagraphStyle('Method', parent=styles['Normal'], fontSize=8, textColor=colors.grey)
    story.append(Paragraph("This assessment uses an actuarially-informed framework combining age-based mortality curves, industry-standard smoker loadings, and coverage-to-income ratios. Results are directional estimates only.", method_style))
    story.append(Spacer(1, 0.2*inch))
    
    # Disclaimer
    disclaimer_style = ParagraphStyle('Disclaimer', parent=styles['Normal'], fontSize=7, textColor=colors.grey, alignment=0)
    story.append(Paragraph("DISCLAIMER: This is a pre-screening tool only and does not constitute a formal offer of coverage. Actual underwriting decisions and premiums vary by insurer and require full medical underwriting. Vettify PreCheck is an independent tool, not affiliated with any specific insurer.", disclaimer_style))
    story.append(Spacer(1, 0.1*inch))
    
    footer_style = ParagraphStyle('Footer', parent=styles['Normal'], fontSize=7, textColor=colors.HexColor('#0d3b66'), alignment=1)
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
        <title>Vettify PreCheck | Professional Insurance Pre-Screening</title>
        <style>
            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }
            
            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Helvetica Neue', Arial, sans-serif;
                background: linear-gradient(135deg, #0d3b66 0%, #1b4d3e 100%);
                min-height: 100vh;
                padding: 40px 20px;
            }
            
            .container {
                max-width: 680px;
                margin: 0 auto;
            }
            
            .header {
                text-align: center;
                margin-bottom: 30px;
            }
            
            .header h1 {
                font-size: 36px;
                color: white;
                letter-spacing: -0.5px;
                font-weight: 700;
            }
            
            .header h1 span {
                font-weight: 400;
                opacity: 0.9;
            }
            
            .header p {
                color: rgba(255,255,255,0.8);
                margin-top: 10px;
                font-size: 16px;
            }
            
            .badge {
                display: inline-block;
                background: rgba(255,255,255,0.2);
                border-radius: 50px;
                padding: 4px 12px;
                font-size: 12px;
                margin-top: 12px;
                color: white;
            }
            
            .card {
                background: white;
                border-radius: 24px;
                box-shadow: 0 20px 40px rgba(0,0,0,0.15);
                overflow: hidden;
                margin-bottom: 20px;
            }
            
            .card-header {
                background: #f8f9fa;
                padding: 20px 30px;
                border-bottom: 1px solid #e9ecef;
            }
            
            .card-header h2 {
                font-size: 18px;
                font-weight: 600;
                color: #0d3b66;
            }
            
            .card-body {
                padding: 30px;
            }
            
            .form-group {
                margin-bottom: 20px;
            }
            
            label {
                display: block;
                font-weight: 600;
                margin-bottom: 8px;
                color: #2c3e50;
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
            }
            
            input:focus, select:focus {
                outline: none;
                border-color: #0d3b66;
                box-shadow: 0 0 0 3px rgba(13,59,102,0.1);
            }
            
            .radio-group {
                display: flex;
                gap: 24px;
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
                background: linear-gradient(135deg, #0d3b66 0%, #1b4d3e 100%);
                color: white;
                border: none;
                border-radius: 14px;
                font-size: 17px;
                font-weight: 600;
                cursor: pointer;
                transition: transform 0.2s, box-shadow 0.2s;
                margin-top: 10px;
            }
            
            button:hover:not(:disabled) {
                transform: translateY(-1px);
                box-shadow: 0 8px 20px rgba(13,59,102,0.3);
            }
            
            button:disabled {
                background: #cbd5e1;
                cursor: not-allowed;
                transform: none;
            }
            
            .loading {
                display: none;
                text-align: center;
                margin-top: 20px;
                padding: 16px;
                background: #f1f5f9;
                border-radius: 12px;
                color: #475569;
            }
            
            .error {
                display: none;
                background: #fee2e2;
                color: #dc2626;
                padding: 14px;
                border-radius: 12px;
                margin-top: 20px;
                font-size: 14px;
            }
            
            .info-box {
                background: #e8f0fe;
                padding: 16px 20px;
                border-radius: 16px;
                margin-top: 20px;
                border-left: 4px solid #0d3b66;
            }
            
            .info-box p {
                font-size: 13px;
                color: #1e293b;
                line-height: 1.5;
            }
            
            .trust-badge {
                display: flex;
                justify-content: center;
                gap: 20px;
                margin-top: 20px;
                flex-wrap: wrap;
            }
            
            .trust-item {
                background: rgba(255,255,255,0.1);
                border-radius: 30px;
                padding: 6px 14px;
                font-size: 12px;
                color: white;
            }
            
            @media (max-width: 600px) {
                body {
                    padding: 20px 16px;
                }
                .card-body {
                    padding: 20px;
                }
                .header h1 {
                    font-size: 28px;
                }
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>Vettify <span>PreCheck</span></h1>
                <p>Professional pre-underwriting assessments for life insurance brokers</p>
                <div class="badge">Powered by actuarial methodology</div>
            </div>
            
            <div class="card">
                <div class="card-header">
                    <h2>📋 Client Information</h2>
                </div>
                <div class="card-body">
                    <form id="assessmentForm">
                        <div class="form-group">
                            <label>AGE</label>
                            <input type="number" id="age" required min="18" max="80" placeholder="e.g., 35">
                        </div>
                        
                        <div class="form-group">
                            <label>GENDER</label>
                            <select id="gender" required>
                                <option value="male">Male</option>
                                <option value="female">Female</option>
                            </select>
                        </div>
                        
                        <div class="form-group">
                            <label>SMOKER STATUS</label>
                            <div class="radio-group">
                                <label><input type="radio" name="smoker" value="yes" required> Yes</label>
                                <label><input type="radio" name="smoker" value="no" required> No</label>
                            </div>
                        </div>
                        
                        <div class="form-group">
                            <label>ANNUAL INCOME (ZAR)</label>
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
                            <label>COVERAGE AMOUNT (ZAR)</label>
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
                            <label>TERM (YEARS)</label>
                            <select id="term" required>
                                <option value="10">10 years</option>
                                <option value="15">15 years</option>
                                <option value="20">20 years</option>
                                <option value="25">25 years</option>
                                <option value="30">30 years</option>
                            </select>
                        </div>
                        
                        <button type="submit" id="generateBtn">Generate Assessment Report →</button>
                    </form>
                    
                    <div class="loading" id="loading">
                        ⏳ Generating professional assessment...
                    </div>
                    
                    <div class="error" id="error"></div>
                    
                    <div class="info-box">
                        <p><strong>⚡ How it works</strong><br>
                        This tool applies an actuarially-informed framework combining age-based mortality curves, industry-standard smoker loadings, and coverage-to-income ratios to provide directional pre-screening estimates for broker use.</p>
                    </div>
                </div>
            </div>
            
            <div class="trust-badge">
                <span class="trust-item">🔒 For Broker Use Only</span>
                <span class="trust-item">📊 Actuarial Framework</span>
                <span class="trust-item">📄 Professional PDF Output</span>
                <span class="trust-item">🆓 20 Free Assessments</span>
            </div>
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
                    generateBtn.textContent = 'Generate Assessment Report →';
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
                        generateBtn.textContent = 'Generate Assessment Report →';
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
                    generateBtn.textContent = 'Generate Assessment Report →';
                    
                } catch (error) {
                    errorDiv.textContent = 'Error generating report. Please try again.';
                    errorDiv.style.display = 'block';
                    generateBtn.disabled = false;
                    loadingDiv.style.display = 'none';
                    generateBtn.textContent = 'Generate Assessment Report →';
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
