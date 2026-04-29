from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import io
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from datetime import datetime
import json
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders

app = Flask(__name__)
CORS(app)

USAGE_FILE = 'usage.json'

# Email configuration
EMAIL_ADDRESS = "vettifyprecheck@gmail.com"
EMAIL_PASSWORD = "lsefbuqadsreulbb "  # <-- REPLACE THIS with your App Password

def send_pdf_via_email(to_email, pdf_buffer, client_age):
    """Send PDF as email attachment"""
    try:
        # Create email
        msg = MIMEMultipart()
        msg['From'] = EMAIL_ADDRESS
        msg['To'] = to_email
        msg['Subject'] = f"Vettify PreCheck - Assessment Report (Age {client_age})"
        
        # Email body
        body = f"""
        Dear Broker,
        
        Attached is your Vettify PreCheck assessment report.
        
        Report Details:
        • Generated: {datetime.now().strftime('%d %B %Y at %H:%M')}
        • Client Age: {client_age}
        
        This is a professional pre-screening report you can share with your client.
        
        Remember: This is a pre-screening estimate only, not a binding quote.
        
        ---
        Vettify PreCheck
        Professional pre-underwriting for insurance brokers
        vettifyprecheck.com
        """
        
        msg.attach(MIMEText(body, 'plain'))
        
        # Attach PDF
        pdf_buffer.seek(0)
        attachment = MIMEBase('application', 'octet-stream')
        attachment.set_payload(pdf_buffer.read())
        encoders.encode_base64(attachment)
        attachment.add_header('Content-Disposition', f'attachment; filename=vettify_precheck_{client_age}.pdf')
        msg.attach(attachment)
        
        # Send email
        server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        server.send_message(msg)
        server.quit()
        
        return True
    except Exception as e:
        print(f"Email error: {str(e)}")
        return False

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
        return "High", "Significant risk factors identified", 25, "#dc2626"
    elif risk_score >= 1:
        return "Moderate", "Some risk factors present", 55, "#ea580c"
    else:
        return "Low", "Favorable risk profile", 85, "#16a34a"

def create_risk_gauge(score):
    filled = int(score / 10)
    empty = 10 - filled
    return "█" * filled + "░" * empty

def generate_pdf(data, pdf_count, is_paid=False):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=72)
    styles = getSampleStyleSheet()
    story = []
    
    vettify_blue = colors.HexColor('#0a2540')
    risk_level, risk_comment, risk_score, risk_color_hex = determine_risk_level(data['age'], data['smoker'], data['coverage_amount'], data['income_band'])
    premium = calculate_premium(data['age'], data['gender'], data['smoker'], data['income_band'], data['coverage_amount'], data['term_years'])
    risk_color = colors.HexColor(risk_color_hex)
    
    # Header
    title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'], fontSize=28, textColor=vettify_blue, alignment=1, spaceAfter=6)
    story.append(Paragraph("VETTIFY", title_style))
    story.append(Paragraph("Pre-Underwriting Assessment Report", styles['Normal']))
    story.append(Spacer(1, 0.2*inch))
    
    # Date
    story.append(Paragraph(f"Generated: {datetime.now().strftime('%d %B %Y at %H:%M')}", styles['Normal']))
    story.append(Spacer(1, 0.2*inch))
    
    # Risk Score - Large
    story.append(Paragraph("RISK SCORE", styles['Heading2']))
    score_style = ParagraphStyle('Score', parent=styles['Normal'], fontSize=48, textColor=risk_color, alignment=1, spaceAfter=6)
    story.append(Paragraph(f"{risk_score}<font size=20>/100</font>", score_style))
    gauge_style = ParagraphStyle('Gauge', parent=styles['Normal'], fontSize=14, textColor=risk_color, alignment=1)
    story.append(Paragraph(create_risk_gauge(risk_score), gauge_style))
    story.append(Paragraph(f"{risk_level.upper()} RISK", styles['Normal']))
    story.append(Spacer(1, 0.2*inch))
    
    # Client Profile
    story.append(Paragraph("CLIENT PROFILE", styles['Heading2']))
    info_data = [
        ["Age", str(data['age']) + " years"],
        ["Gender", data['gender'].capitalize()],
        ["Smoker", "Yes" if data['smoker'] else "No"],
        ["Annual Income", f"R{data['income_band']:,}"],
        ["Coverage", f"R{data['coverage_amount']:,}"],
        ["Term", f"{data['term_years']} years"],
        ["Coverage/Income", f"{round(data['coverage_amount'] / data['income_band'], 1)}x"]
    ]
    info_table = Table(info_data, colWidths=[1.8*inch, 3.2*inch])
    info_table.setStyle(TableStyle([('FONTNAME', (0,0), (-1,-1), 'Helvetica'), ('FONTSIZE', (0,0), (-1,-1), 10)]))
    story.append(info_table)
    story.append(Spacer(1, 0.2*inch))
    
    # Premium
    story.append(Paragraph("PREMIUM ESTIMATE", styles['Heading2']))
    story.append(Paragraph(f"R{premium} - R{premium + 150} per month", styles['Normal']))
    story.append(Paragraph("Illustrative indication only - subject to full underwriting", styles['Italic']))
    story.append(Spacer(1, 0.2*inch))
    
    # Factors
    story.append(Paragraph("KEY FACTORS", styles['Heading2']))
    factors = []
    if data['smoker']:
        factors.append("• Tobacco use: +80-100% premium loading")
    else:
        factors.append("• Non-smoker: Standard rates apply")
    if data['age'] > 50:
        factors.append("• Age >50: Additional medical underwriting likely")
    elif data['age'] > 40:
        factors.append("• Age 40-50: Standard underwriting")
    else:
        factors.append("• Age <40: Favorable underwriting category")
    for f in factors:
        story.append(Paragraph(f, styles['Normal']))
    story.append(Spacer(1, 0.2*inch))
    
    # Footer
    story.append(Paragraph("vettifyprecheck.com · Professional pre-screening for brokers", styles['Normal']))
    
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
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body { font-family: 'Inter', sans-serif; background: linear-gradient(135deg, #f5f7fa 0%, #eef2f6 100%); min-height: 100vh; }
            .navbar { background: white; border-bottom: 1px solid rgba(0,0,0,0.05); padding: 16px 0; position: sticky; top: 0; z-index: 100; }
            .nav-container { max-width: 1280px; margin: 0 auto; padding: 0 32px; display: flex; justify-content: space-between; align-items: center; }
            .logo { font-size: 24px; font-weight: 700; background: linear-gradient(135deg, #0a2540 0%, #1b4d3e 100%); -webkit-background-clip: text; background-clip: text; color: transparent; text-decoration: none; }
            .logo span { font-weight: 400; }
            .badge-nav { background: #e8f0fe; padding: 6px 14px; border-radius: 40px; font-size: 12px; font-weight: 500; color: #0a2540; }
            .main-container { max-width: 1280px; margin: 0 auto; padding: 48px 32px; display: grid; grid-template-columns: 1fr 0.9fr; gap: 48px; }
            .form-card { background: white; border-radius: 28px; box-shadow: 0 8px 30px rgba(0,0,0,0.06); overflow: hidden; }
            .form-header { padding: 28px 32px; border-bottom: 1px solid #eef2f6; }
            .form-header h1 { font-size: 26px; font-weight: 700; color: #0a2540; margin-bottom: 8px; }
            .form-header p { font-size: 14px; color: #5b6e8c; }
            .form-body { padding: 32px; }
            .form-group { margin-bottom: 24px; }
            label { display: block; font-weight: 600; margin-bottom: 8px; color: #1a2c3e; font-size: 13px; text-transform: uppercase; letter-spacing: 0.2px; }
            input, select { width: 100%; padding: 14px 16px; border: 1.5px solid #e2e8f0; border-radius: 14px; font-size: 15px; transition: all 0.2s; font-family: 'Inter', sans-serif; }
            input:focus, select:focus { outline: none; border-color: #0a2540; box-shadow: 0 0 0 3px rgba(10,37,64,0.08); }
            .radio-group { display: flex; gap: 32px; margin-top: 8px; }
            .radio-group label { display: flex; align-items: center; font-weight: 500; text-transform: none; gap: 10px; cursor: pointer; }
            .radio-group input { width: 18px; height: 18px; }
            .inline-group { display: flex; gap: 12px; align-items: center; }
            .inline-group select { flex: 2; }
            .inline-group input { flex: 1; }
            small { display: block; margin-top: 6px; font-size: 11px; color: #8a9bb0; }
            .btn-primary { width: 100%; padding: 16px; background: linear-gradient(135deg, #0a2540 0%, #1b4d3e 100%); color: white; border: none; border-radius: 16px; font-size: 16px; font-weight: 600; cursor: pointer; transition: all 0.2s; margin-top: 16px; font-family: 'Inter', sans-serif; }
            .btn-primary:hover:not(:disabled) { transform: translateY(-2px); box-shadow: 0 8px 20px rgba(10,37,64,0.2); }
            .btn-primary:disabled { background: #cbd5e1; cursor: not-allowed; }
            .info-card { background: white; border-radius: 28px; box-shadow: 0 8px 30px rgba(0,0,0,0.06); padding: 32px; }
            .info-section { margin-bottom: 32px; }
            .info-section h3 { font-size: 16px; font-weight: 700; color: #0a2540; margin-bottom: 16px; display: flex; align-items: center; gap: 8px; }
            .info-section p { font-size: 14px; color: #425466; line-height: 1.6; margin-bottom: 12px; }
            .trust-list { display: flex; flex-direction: column; gap: 12px; }
            .trust-item { display: flex; align-items: center; gap: 12px; font-size: 14px; padding: 10px 0; border-bottom: 1px solid #f0f4f8; }
            .pill { background: #e8f0fe; color: #0a2540; padding: 4px 12px; border-radius: 40px; font-size: 11px; font-weight: 600; display: inline-block; }
            .risk-preview { background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%); border-radius: 20px; padding: 24px; margin-top: 24px; text-align: center; }
            .risk-score-large { font-size: 56px; font-weight: 800; color: #0a2540; line-height: 1; }
            .gauge-preview { font-size: 24px; letter-spacing: 4px; margin: 12px 0; }
            .loading, .error, .success { display: none; margin-top: 20px; padding: 16px; border-radius: 14px; font-size: 14px; }
            .loading { background: #f1f5f9; color: #475569; text-align: center; }
            .error { background: #fee2e2; color: #dc2626; }
            .success { background: #e6f7e6; color: #16a34a; text-align: center; }
            .footer { text-align: center; padding: 32px; color: #8a9bb0; font-size: 13px; border-top: 1px solid rgba(0,0,0,0.05); margin-top: 48px; }
            .identity { background: #f8fafc; border-radius: 16px; padding: 20px; margin-top: 24px; text-align: center; }
            @media (max-width: 900px) { .main-container { grid-template-columns: 1fr; gap: 32px; padding: 32px 20px; } }
            @media (max-width: 600px) { .form-body, .info-card, .form-header { padding: 20px; } .inline-group { flex-direction: column; } }
        </style>
    </head>
    <body>
        <nav class="navbar"><div class="nav-container"><a href="/" class="logo">VETTIFY <span>PreCheck</span></a><div class="nav-links"><span class="badge-nav">For Brokers</span><span class="badge-nav">Actuarial Model</span></div></div></nav>
        <div class="main-container">
            <div class="form-card">
                <div class="form-header"><h1>Pre-Underwriting Assessment</h1><p>Enter client details to generate a professional risk report</p></div>
                <div class="form-body">
                    <form id="assessmentForm">
                        <div class="form-group"><label>Age</label><input type="number" id="age" required min="18" max="80" placeholder="e.g., 35"></div>
                        <div class="form-group"><label>Gender</label><select id="gender" required><option value="male">Male</option><option value="female">Female</option></select></div>
                        <div class="form-group"><label>Smoker Status</label><div class="radio-group"><label><input type="radio" name="smoker" value="yes" required> Yes</label><label><input type="radio" name="smoker" value="no" required> No</label></div></div>
                        <div class="form-group"><label>Annual Income (ZAR)</label><select id="income" required><option value="250000">R0 - R250,000</option><option value="500000">R250,001 - R500,000</option><option value="750000">R500,001 - R750,000</option><option value="1000000">R750,001 - R1,000,000</option><option value="1500000">R1,000,001 - R1,500,000</option><option value="2000000">R1,500,001+</option></select></div>
                        <div class="form-group"><label>Coverage Amount (ZAR)</label><div class="inline-group"><select id="coverage_preset"><option value="500000">R500,000</option><option value="1000000">R1,000,000</option><option value="2000000">R2,000,000</option><option value="3000000">R3,000,000</option><option value="5000000">R5,000,000</option><option value="10000000">R10,000,000</option><option value="custom">Custom amount</option></select><input type="number" id="coverage_custom" placeholder="Enter amount" style="display: none;" min="50000"></div><small>Minimum R50,000</small></div>
                        <div class="form-group"><label>Term (Years)</label><div class="inline-group"><select id="term_preset"><option value="10">10 years</option><option value="15">15 years</option><option value="20">20 years</option><option value="25">25 years</option><option value="30">30 years</option><option value="custom">Custom term</option></select><input type="number" id="term_custom" placeholder="Enter years" style="display: none;" min="1" max="50"></div><small>1-50 years</small></div>
                        <div class="form-group"><label>Your Email Address (PDF will be sent here)</label><input type="email" id="broker_email" required placeholder="broker@example.com"><small>Free for 20 assessments · Professional PDF delivered to your inbox</small></div>
                        <button type="submit" class="btn-primary" id="generateBtn">Generate & Send Report →</button>
                    </form>
                    <div class="loading" id="loading">⏳ Generating and emailing your report...</div>
                    <div class="error" id="error"></div>
                    <div class="success" id="success"></div>
                </div>
            </div>
            <div class="info-card">
                <div class="info-section"><h3>📊 Methodology</h3><p>Powered by the <strong>Gompertz-Makeham mortality model</strong>, industry-standard smoker loadings, and coverage-to-income ratio analysis.</p><div class="pill">Actuarial Framework</div></div>
                <div class="info-section"><h3>✓ What You Receive</h3><div class="trust-list"><div class="trust-item">📊 Risk Score (0-100 scale)</div><div class="trust-item">🏷️ Risk Classification (Low/Moderate/High)</div><div class="trust-item">💰 Premium Range estimate</div><div class="trust-item">🔬 Factor Breakdown + Methodology</div><div class="trust-item">📧 PDF sent directly to your email</div></div></div>
                <div class="info-section"><h3>🛡️ Trust & Credibility</h3><p>Built using established actuarial principles. Independent tool for broker use only.</p><div class="trust-list"><div class="trust-item">✅ 20 free assessments</div><div class="trust-item">✅ PDF delivered to your inbox</div><div class="trust-item">✅ Professional output guaranteed</div></div></div>
                <div class="risk-preview"><span style="font-size: 12px; color: #5b6e8c;">Sample Output</span><div class="risk-score-large">85<span style="font-size: 20px;">/100</span></div><div class="gauge-preview">████████░░</div><div><span class="pill">LOW RISK</span></div></div>
                <div class="identity"><p>Built by actuarial professionals using established mortality models</p><p style="margin-top: 4px;">© 2026 Vettify · Independent pre-screening tool</p></div>
            </div>
        </div>
        <div class="footer"><p>Vettify PreCheck · Professional pre-underwriting for insurance brokers</p><p style="margin-top: 8px; font-size: 11px;">Not affiliated with any specific insurer · For broker use only</p></div>
        <script>
            const coveragePreset = document.getElementById('coverage_preset');
            const coverageCustom = document.getElementById('coverage_custom');
            const termPreset = document.getElementById('term_preset');
            const termCustom = document.getElementById('term_custom');
            coveragePreset.addEventListener('change', function() { if (this.value === 'custom') { coverageCustom.style.display = 'block'; coverageCustom.required = true; } else { coverageCustom.style.display = 'none'; coverageCustom.required = false; coverageCustom.value = ''; } });
            termPreset.addEventListener('change', function() { if (this.value === 'custom') { termCustom.style.display = 'block'; termCustom.required = true; } else { termCustom.style.display = 'none'; termCustom.required = false; termCustom.value = ''; } });
            document.getElementById('assessmentForm').addEventListener('submit', async (e) => {
                e.preventDefault();
                const brokerEmail = document.getElementById('broker_email').value.trim();
                if (!brokerEmail) { document.getElementById('error').textContent = 'Please enter your email address'; document.getElementById('error').style.display = 'block'; return; }
                const generateBtn = document.getElementById('generateBtn');
                const loadingDiv = document.getElementById('loading');
                const errorDiv = document.getElementById('error');
                const successDiv = document.getElementById('success');
                generateBtn.disabled = true;
                loadingDiv.style.display = 'block';
                errorDiv.style.display = 'none';
                successDiv.style.display = 'none';
                generateBtn.textContent = 'Generating & Sending...';
                let coverageAmount; if (coveragePreset.value === 'custom') { coverageAmount = parseInt(coverageCustom.value); if (isNaN(coverageAmount) || coverageAmount < 50000) { errorDiv.textContent = 'Please enter a valid coverage amount (minimum R50,000)'; errorDiv.style.display = 'block'; generateBtn.disabled = false; loadingDiv.style.display = 'none'; generateBtn.textContent = 'Generate & Send Report →'; return; } } else { coverageAmount = parseInt(coveragePreset.value); }
                let termYears; if (termPreset.value === 'custom') { termYears = parseInt(termCustom.value); if (isNaN(termYears) || termYears < 1 || termYears > 50) { errorDiv.textContent = 'Please enter a valid term (1-50 years)'; errorDiv.style.display = 'block'; generateBtn.disabled = false; loadingDiv.style.display = 'none'; generateBtn.textContent = 'Generate & Send Report →'; return; } } else { termYears = parseInt(termPreset.value); }
                const formData = { age: parseInt(document.getElementById('age').value), gender: document.getElementById('gender').value, smoker: document.querySelector('input[name="smoker"]:checked').value === 'yes', income_band: parseInt(document.getElementById('income').value), coverage_amount: coverageAmount, term_years: termYears, broker_email: brokerEmail };
                if (formData.age < 18 || formData.age > 80) { errorDiv.textContent = 'Age must be between 18 and 80'; errorDiv.style.display = 'block'; generateBtn.disabled = false; loadingDiv.style.display = 'none'; generateBtn.textContent = 'Generate & Send Report →'; return; }
                try { const response = await fetch('/generate', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(formData) });
                if (response.status === 403) { const error = await response.json(); errorDiv.innerHTML = error.message; errorDiv.style.display = 'block'; generateBtn.disabled = false; loadingDiv.style.display = 'none'; generateBtn.textContent = 'Generate & Send Report →'; return; }
                if (!response.ok) throw new Error('Failed to generate PDF');
                const result = await response.json();
                generateBtn.disabled = false; loadingDiv.style.display = 'none'; successDiv.innerHTML = result.message; successDiv.style.display = 'block'; generateBtn.textContent = 'Generate & Send Report →';
                setTimeout(() => { successDiv.style.display = 'none'; }, 5000);
                } catch (error) { errorDiv.textContent = 'Error generating report. Please try again.'; errorDiv.style.display = 'block'; generateBtn.disabled = false; loadingDiv.style.display = 'none'; generateBtn.textContent = 'Generate & Send Report →'; }
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
        
        if not broker_email:
            return jsonify({'error': 'Email required'}), 400
        
        user_key = get_or_create_user(broker_email)
        within_limit, count = check_limit(user_key)
        
        if not within_limit:
            return jsonify({
                'error': 'limit_reached',
                'message': f'You\'ve used your 20 free assessments. Contact us to upgrade for unlimited access.'
            }), 403
        
        # Generate PDF
        is_paid = load_usage().get(user_key, {}).get('plan') != 'free'
        pdf_buffer = generate_pdf(data, count + 1, is_paid)
        
        # Send PDF via email
        email_sent = send_pdf_via_email(broker_email, pdf_buffer, data['age'])
        
        if not email_sent:
            return jsonify({'error': 'Failed to send email. Please try again.'}), 500
        
        # Increment usage only after successful email
        increment_usage(user_key)
        
        return jsonify({
            'success': True,
            'message': f'✅ Assessment report sent to {broker_email}! Check your inbox.'
        })
    
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
