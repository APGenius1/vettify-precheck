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
        return "High", "Likely declined or significant loading - full underwriting required"
    elif risk_score >= 1:
        return "Medium", "Possible loading or underwriting review - subject to full assessment"
    else:
        return "Low", "Appears acceptable based on basic criteria - underwriting still applies"

def generate_pdf(data, pdf_count, is_paid=False):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=72)
    styles = getSampleStyleSheet()
    story = []
    
    title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'], fontSize=24, textColor=colors.HexColor('#1a5490'), alignment=1)
    story.append(Paragraph("Vettify PreCheck Assessment", title_style))
    story.append(Spacer(1, 0.1*inch))
    
    sub_style = ParagraphStyle('Subtitle', parent=styles['Normal'], fontSize=10, textColor=colors.grey, alignment=1)
    story.append(Paragraph("Professional Pre-Screening Report", sub_style))
    story.append(Spacer(1, 0.1*inch))
    
    date_style = ParagraphStyle('Date', parent=styles['Normal'], fontSize=10, textColor=colors.grey, alignment=1)
    story.append(Paragraph(datetime.now().strftime("%d %B %Y"), date_style))
    story.append(Spacer(1, 0.3*inch))
    
    story.append(Paragraph("Client Information", styles['Heading2']))
    story.append(Spacer(1, 0.1*inch))
    
    info_data = [
        ["Age:", str(data['age'])],
        ["Gender:", data['gender'].capitalize()],
        ["Smoker:", "Yes" if data['smoker'] else "No"],
        ["Income Band:", f"R{data['income_band']:,}"],
        ["Coverage Amount:", f"R{data['coverage_amount']:,}"],
        ["Term:", f"{data['term_years']} years"]
    ]
    
    info_table = Table(info_data, colWidths=[1.5*inch, 3*inch])
    info_table.setStyle(TableStyle([
        ('FONTNAME', (0,0), (-1,-1), 'Helvetica'),
        ('FONTSIZE', (0,0), (-1,-1), 11),
        ('TEXTCOLOR', (0,0), (0,-1), colors.HexColor('#1a5490')),
        ('ALIGN', (0,0), (0,-1), 'LEFT'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 0.2*inch))
    
    risk_level, risk_comment = determine_risk_level(data['age'], data['smoker'], data['coverage_amount'], data['income_band'])
    premium = calculate_premium(data['age'], data['gender'], data['smoker'], data['income_band'], data['coverage_amount'], data['term_years'])
    
    story.append(Paragraph("Initial Screening Assessment", styles['Heading2']))
    story.append(Spacer(1, 0.1*inch))
    
    if risk_level == "Low":
        risk_color = colors.HexColor('#28a745')
    elif risk_level == "Medium":
        risk_color = colors.HexColor('#ffc107')
    else:
        risk_color = colors.HexColor('#dc3545')
    
    risk_style = ParagraphStyle('Risk', parent=styles['Normal'], fontSize=14, textColor=risk_color)
    story.append(Paragraph(f"<b>Screening Result:</b> {risk_level}", risk_style))
    story.append(Spacer(1, 0.05*inch))
    story.append(Paragraph(f"<b>Illustrative Indication:</b> R{premium} - R{premium + 150} per month", styles['Normal']))
    story.append(Spacer(1, 0.05*inch))
    story.append(Paragraph(f"<b>Initial Assessment:</b> {risk_comment}", styles['Normal']))
    story.append(Spacer(1, 0.2*inch))
    
    story.append(Paragraph("Key Considerations", styles['Heading2']))
    story.append(Spacer(1, 0.1*inch))
    
    flags = []
    if data['smoker']:
        flags.append("• Smoker status significantly increases premiums (typical industry loading: +50-100%)")
    if data['age'] > 50:
        flags.append("• Age over 50 typically triggers additional medical underwriting requirements")
    if data['coverage_amount'] / data['income_band'] > 5:
        flags.append("• Coverage amount high relative to income - possible income verification required")
    if data['term_years'] > 25:
        flags.append("• Extended term length - premium guaranteed for longer period, affects pricing")
    
    if not flags:
        flags.append("• No immediate red flags based on basic criteria")
    
    for flag in flags:
        story.append(Paragraph(flag, styles['Normal']))
        story.append(Spacer(1, 0.05*inch))
    
    story.append(Spacer(1, 0.2*inch))
    
    disclaimer_title_style = ParagraphStyle('DisclaimerTitle', parent=styles['Normal'], fontSize=10, textColor=colors.HexColor('#dc3545'), alignment=0)
    story.append(Paragraph("<b>⚠️ IMPORTANT - THIS IS NOT ACTUARIAL PRICING</b>", disclaimer_title_style))
    story.append(Spacer(1, 0.05*inch))
    
    disclaimer_style = ParagraphStyle('Disclaimer', parent=styles['Normal'], fontSize=8, textColor=colors.black, alignment=0)
    story.append(Paragraph("Vettify PreCheck uses simplified rules for pre-screening purposes only:", disclaimer_style))
    story.append(Paragraph("• Not based on actual mortality/morbidity tables or insurer-specific underwriting", disclaimer_style))
    story.append(Paragraph("• Not a binding quote or guaranteed premium", disclaimer_style))
    story.append(Paragraph("• Actual premiums and decisions vary significantly by insurer, medical history, family history, lifestyle, and full underwriting", disclaimer_style))
    story.append(Paragraph("• For broker internal use as a conversation starter - not for client guarantees", disclaimer_style))
    story.append(Spacer(1, 0.2*inch))
    
    if not is_paid and pdf_count >= 15:
        warning_style = ParagraphStyle('Warning', parent=styles['Normal'], fontSize=10, textColor=colors.HexColor('#dc3545'), alignment=1)
        story.append(Paragraph(f"⚠️ You've used {pdf_count}/20 free assessments. Visit vettifyprecheck.com to upgrade for unlimited access.", warning_style))
        story.append(Spacer(1, 0.2*inch))
    
    footer_style = ParagraphStyle('Footer', parent=styles['Normal'], fontSize=7, textColor=colors.HexColor('#1a5490'), alignment=1)
    story.append(Paragraph("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", footer_style))
    story.append(Paragraph("Vettify PreCheck", footer_style))
    story.append(Paragraph("Pre-screening estimates for broker use only", footer_style))
    story.append(Paragraph("Get your free assessments → vettifyprecheck.com ←", footer_style))
    story.append(Paragraph("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", footer_style))
    
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
        <title>Vettify PreCheck | Insurance Pre-Screening Tool for Brokers</title>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif; background: linear-gradient(135deg, #1a5490 0%, #2a6eb0 100%); min-height: 100vh; padding: 20px; }
            .container { max-width: 600px; margin: 0 auto; background: white; border-radius: 20px; box-shadow: 0 20px 60px rgba(0,0,0,0.3); overflow: hidden; }
            .header { background: #1a5490; color: white; padding: 30px; text-align: center; }
            .header h1 { font-size: 28px; margin-bottom: 10px; }
            .header h1 span { font-weight: 300; }
            .header p { font-size: 14px; opacity: 0.9; }
            .form-container { padding: 30px; }
            .form-group { margin-bottom: 20px; }
            label { display: block; font-weight: 600; margin-bottom: 8px; color: #333; font-size: 14px; }
            input, select { width: 100%; padding: 12px; border: 2px solid #e0e0e0; border-radius: 8px; font-size: 16px; }
            input:focus, select:focus { outline: none; border-color: #1a5490; }
            .radio-group { display: flex; gap: 20px; margin-top: 8px; }
            .radio-group label { display: flex; align-items: center; font-weight: normal; margin-bottom: 0; cursor: pointer; }
            .radio-group input { width: auto; margin-right: 8px; }
            button { width: 100%; padding: 14px; background: #1a5490; color: white; border: none; border-radius: 8px; font-size: 18px; font-weight: 600; cursor: pointer; margin-top: 10px; transition: background 0.3s; }
            button:hover { background: #0e3a66; }
            button:disabled { background: #ccc; cursor: not-allowed; }
            .loading { display: none; text-align: center; margin-top: 20px; padding: 15px; background: #f0f0f0; border-radius: 8px; color: #666; }
            .error { display: none; background: #fee; color: #c33; padding: 12px; border-radius: 8px; margin-top: 20px; font-size: 14px; }
            .info { background: #e3f2fd; padding: 15px; border-radius: 8px; margin-bottom: 25px; font-size: 13px; color: #1a5490; line-height: 1.5; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>Vettify <span>PreCheck</span></h1>
                <p>Professional pre-screening reports in 10 seconds</p>
            </div>
            <div class="form-container">
                <div class="info">
                    <strong>⚡ For Broker Use Only</strong><br>
                    Generate client-ready PDF assessments instantly.<br>
                    <strong>Free for 20 reports</strong> — then R199/month for unlimited access.
                </div>
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
                        <label>Smoker?</label>
                        <div class="radio-group">
                            <label><input type="radio" name="smoker" value="yes" required> Yes</label>
                            <label><input type="radio" name="smoker" value="no" required> No</label>
                        </div>
                    </div>
                    <div class="form-group">
                        <label>Annual Income Band (ZAR)</label>
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
                    <button type="submit" id="generateBtn">Generate Vettify Report →</button>
                </form>
                <div class="loading" id="loading">Generating your PDF report... ⏳</div>
                <div class="error" id="error"></div>
            </div>
        </div>
        <script>
            let brokerEmail = localStorage.getItem('vettify_email');
            
            document.getElementById('assessmentForm').addEventListener('submit', async (e) => {
                e.preventDefault();
                
                if (!brokerEmail) {
                    brokerEmail = prompt('Try Vettify PreCheck free for 20 reports\n\nEnter your email to get started:');
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
                    
                } catch (error) {
                    errorDiv.textContent = 'Error generating report. Please try again.';
                    errorDiv.style.display = 'block';
                    generateBtn.disabled = false;
                    loadingDiv.style.display = 'none';
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
