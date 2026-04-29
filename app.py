from flask import Flask, request, jsonify, send_file, session
from flask_cors import CORS
import io
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from datetime import datetime, timedelta
import json
import os
import uuid

app = Flask(__name__)
app.secret_key = os.urandom(24)
CORS(app)

# Data storage
LEADS_FILE = 'leads.json'
USAGE_FILE = 'usage.json'

def load_data(filename):
    if os.path.exists(filename):
        with open(filename, 'r') as f:
            return json.load(f)
    return {}

def save_data(filename, data):
    with open(filename, 'w') as f:
        json.dump(data, f)

def get_user_usage(email):
    usage = load_data(USAGE_FILE)
    if email not in usage:
        usage[email] = {'count': 0, 'first_use': datetime.now().isoformat()}
        save_data(USAGE_FILE, usage)
    return usage[email]['count']

def increment_usage(email):
    usage = load_data(USAGE_FILE)
    if email not in usage:
        usage[email] = {'count': 0, 'first_use': datetime.now().isoformat()}
    usage[email]['count'] += 1
    save_data(USAGE_FILE, usage)
    return usage[email]['count']

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
        return "High", "Significant risk factors - full underwriting required", 25, "#dc2626", "High Risk - Possible Decline/Loading"
    elif risk_score >= 1:
        return "Moderate", "Some risk factors present - standard underwriting likely", 55, "#ea580c", "Moderate Risk - Standard Review"
    else:
        return "Low", "Favorable risk profile - preferred rates possible", 85, "#16a34a", "Low Risk - Preferred Rates"

def generate_full_report(data):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=72)
    styles = getSampleStyleSheet()
    story = []
    
    vettify_blue = colors.HexColor('#0a2540')
    
    risk_level, risk_comment, risk_score, risk_color_hex, risk_label = determine_risk_level(data['age'], data['smoker'], data['coverage_amount'], data['income_band'])
    premium = calculate_premium(data['age'], data['gender'], data['smoker'], data['income_band'], data['coverage_amount'], data['term_years'])
    risk_color = colors.HexColor(risk_color_hex)
    
    title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'], fontSize=28, textColor=vettify_blue, alignment=1, spaceAfter=6)
    story.append(Paragraph("VETTIFY PRECHECK", title_style))
    story.append(Paragraph("Professional Pre-Underwriting Assessment Report", styles['Normal']))
    story.append(Spacer(1, 0.2*inch))
    
    report_id = str(uuid.uuid4())[:8]
    valid_until = (datetime.now() + timedelta(days=7)).strftime('%d %B %Y')
    story.append(Paragraph(f"Report ID: {report_id}", styles['Normal']))
    story.append(Paragraph(f"Valid Until: {valid_until}", styles['Normal']))
    story.append(Paragraph(f"Generated: {datetime.now().strftime('%d %B %Y at %H:%M')}", styles['Normal']))
    story.append(Spacer(1, 0.2*inch))
    
    story.append(Paragraph("RISK ASSESSMENT", styles['Heading2']))
    score_style = ParagraphStyle('Score', parent=styles['Normal'], fontSize=48, textColor=risk_color, alignment=1, spaceAfter=6)
    story.append(Paragraph(f"{risk_score}<font size=20>/100</font>", score_style))
    story.append(Paragraph(f"{risk_label}", styles['Normal']))
    story.append(Spacer(1, 0.2*inch))
    
    story.append(Paragraph("CLIENT PROFILE", styles['Heading2']))
    info_data = [
        ["Age", str(data['age']) + " years"],
        ["Gender", data['gender'].capitalize()],
        ["Smoker", "Yes" if data['smoker'] else "No"],
        ["Annual Income", f"R{data['income_band']:,}"],
        ["Coverage Requested", f"R{data['coverage_amount']:,}"],
        ["Term", f"{data['term_years']} years"],
        ["Premium Estimate", f"R{premium} - R{premium + 150}/month"],
    ]
    info_table = Table(info_data, colWidths=[1.8*inch, 3.2*inch])
    info_table.setStyle(TableStyle([('FONTNAME', (0,0), (-1,-1), 'Helvetica'), ('FONTSIZE', (0,0), (-1,-1), 10)]))
    story.append(info_table)
    story.append(Spacer(1, 0.2*inch))
    
    story.append(Paragraph("KEY RISK DRIVERS", styles['Heading2']))
    factors = []
    if data['smoker']:
        factors.append("• Tobacco Use: +80-100% premium loading")
    else:
        factors.append("• Non-Smoker: Preferred rates apply")
    if data['age'] > 50:
        factors.append("• Age >50: Additional medical underwriting required")
    elif data['age'] > 40:
        factors.append("• Age 40-50: Standard underwriting with possible medical questions")
    else:
        factors.append("• Age <40: Favorable underwriting category")
    
    ratio = data['coverage_amount'] / data['income_band']
    if ratio > 6:
        factors.append(f"• Coverage/Income Ratio ({ratio:.1f}x): Above guideline - verification likely")
    elif ratio > 4:
        factors.append(f"• Coverage/Income Ratio ({ratio:.1f}x): Near guideline - possible review")
    else:
        factors.append(f"• Coverage/Income Ratio ({ratio:.1f}x): Within guidelines")
    
    for factor in factors:
        story.append(Paragraph(factor, styles['Normal']))
        story.append(Spacer(1, 0.05*inch))
    story.append(Spacer(1, 0.15*inch))
    
    story.append(Paragraph("UNDERWRITING EXPLANATION", styles['Heading2']))
    underwriting_text = """
    This assessment uses the Gompertz-Makeham mortality model for age-based risk calculation, combined with:
    • Industry-standard smoker loadings (1.8x base premium)
    • Coverage-to-income ratio analysis (standard threshold: 5x annual income)
    • Gender-based actuarial tables
    """
    story.append(Paragraph(underwriting_text, styles['Normal']))
    story.append(Spacer(1, 0.15*inch))
    
    story.append(Paragraph("INSURER MATCHING", styles['Heading2']))
    if risk_level == "Low":
        insurers = "Discovery, Old Mutual, Momentum, Sanlam"
        probability = "85-95%"
    elif risk_level == "Moderate":
        insurers = "Old Mutual, Momentum (standard underwriting)"
        probability = "65-80%"
    else:
        insurers = "Specialist insurers recommended"
        probability = "40-60%"
    
    story.append(Paragraph(f"• Recommended Insurers: {insurers}", styles['Normal']))
    story.append(Paragraph(f"• Estimated Approval Probability: {probability}", styles['Normal']))
    story.append(Spacer(1, 0.15*inch))
    
    story.append(Paragraph("DISCLAIMER", styles['Heading2']))
    disclaimer_style = ParagraphStyle('Disclaimer', parent=styles['Normal'], fontSize=7, textColor=colors.grey)
    story.append(Paragraph("This is a pre-screening intelligence report only. Valid for 7 days. Not a binding quote.", disclaimer_style))
    story.append(Spacer(1, 0.1*inch))
    
    footer_style = ParagraphStyle('Footer', parent=styles['Normal'], fontSize=7, textColor=vettify_blue, alignment=1)
    story.append(Paragraph("vettifyprecheck.com · Professional pre-underwriting intelligence", footer_style))
    
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
        <title>Vettify PreCheck | Insurance Underwriting Intelligence</title>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body { font-family: 'Inter', sans-serif; background: #f8fafc; }
            .navbar { background: white; border-bottom: 1px solid #e2e8f0; padding: 16px 0; position: sticky; top: 0; z-index: 100; }
            .nav-container { max-width: 1280px; margin: 0 auto; padding: 0 32px; display: flex; justify-content: space-between; align-items: center; }
            .logo { font-size: 24px; font-weight: 800; color: #0a2540; text-decoration: none; }
            .logo span { font-weight: 400; color: #5b6e8c; }
            .btn-outline { padding: 8px 20px; border: 1.5px solid #0a2540; border-radius: 30px; background: transparent; color: #0a2540; font-weight: 600; cursor: pointer; }
            .hero { background: linear-gradient(135deg, #0a2540 0%, #1b4d3e 100%); color: white; padding: 60px 32px; text-align: center; }
            .hero h1 { font-size: 48px; font-weight: 800; margin-bottom: 16px; }
            .hero p { font-size: 18px; opacity: 0.9; max-width: 600px; margin: 0 auto; }
            .hero-badge { background: rgba(255,255,255,0.2); display: inline-block; padding: 4px 12px; border-radius: 30px; font-size: 12px; margin-bottom: 24px; }
            .free-badge { background: #fef3c7; color: #92400e; padding: 4px 12px; border-radius: 30px; font-size: 11px; font-weight: 600; display: inline-block; margin-bottom: 12px; }
            .main-container { max-width: 1280px; margin: -40px auto 48px; padding: 0 32px; display: grid; grid-template-columns: 1fr 0.8fr; gap: 32px; }
            .form-card { background: white; border-radius: 28px; box-shadow: 0 8px 30px rgba(0,0,0,0.1); overflow: hidden; }
            .form-header { padding: 28px 32px; border-bottom: 1px solid #eef2f6; }
            .form-header h2 { font-size: 22px; font-weight: 700; color: #0a2540; }
            .form-body { padding: 32px; }
            .form-group { margin-bottom: 24px; }
            label { display: block; font-weight: 600; margin-bottom: 8px; color: #1a2c3e; font-size: 13px; text-transform: uppercase; }
            input, select { width: 100%; padding: 14px 16px; border: 1.5px solid #e2e8f0; border-radius: 14px; font-size: 15px; font-family: 'Inter', sans-serif; }
            input:focus, select:focus { outline: none; border-color: #0a2540; }
            .radio-group { display: flex; gap: 32px; margin-top: 8px; }
            .radio-group label { display: flex; align-items: center; font-weight: 500; text-transform: none; gap: 10px; cursor: pointer; }
            .row-group { display: flex; gap: 16px; }
            .row-group .form-group { flex: 1; }
            .btn-primary { width: 100%; padding: 16px; background: linear-gradient(135deg, #0a2540 0%, #1b4d3e 100%); color: white; border: none; border-radius: 16px; font-size: 16px; font-weight: 700; cursor: pointer; margin-top: 16px; }
            .result-card { background: white; border-radius: 28px; box-shadow: 0 8px 30px rgba(0,0,0,0.1); padding: 32px; position: sticky; top: 100px; }
            .result-score { text-align: center; padding: 24px; background: #f8fafc; border-radius: 20px; margin-bottom: 24px; }
            .score-number { font-size: 64px; font-weight: 800; line-height: 1; }
            .premium-box { background: #f0fdf4; padding: 16px; border-radius: 16px; text-align: center; }
            .premium-amount { font-size: 28px; font-weight: 800; color: #16a34a; }
            .paywall { background: #fef3c7; border-radius: 20px; padding: 24px; text-align: center; margin-top: 24px; }
            .paywall h3 { font-size: 18px; font-weight: 700; color: #92400e; margin-bottom: 12px; }
            .paywall-price { font-size: 32px; font-weight: 800; color: #0a2540; margin: 16px 0; }
            .btn-pay { width: 100%; padding: 14px; background: #f59e0b; color: white; border: none; border-radius: 12px; font-weight: 700; font-size: 16px; cursor: pointer; }
            .hidden { display: none; }
            .loading { text-align: center; padding: 40px; }
            .error { color: #dc2626; padding: 12px; background: #fee2e2; border-radius: 12px; margin-top: 16px; display: none; }
            .remaining-badge { background: #e8f0fe; padding: 8px 16px; border-radius: 30px; font-size: 12px; margin-bottom: 16px; text-align: center; }
            .footer { text-align: center; padding: 48px 32px; color: #8a9bb0; border-top: 1px solid #e2e8f0; margin-top: 48px; }
            @media (max-width: 900px) { .main-container { grid-template-columns: 1fr; } .hero h1 { font-size: 32px; } }
        </style>
    </head>
    <body>
        <nav class="navbar">
            <div class="nav-container">
                <a href="/" class="logo">VETTIFY <span>PreCheck</span></a>
                <button class="btn-outline" onclick="showBrokerModal()">For Brokers →</button>
            </div>
        </nav>
        
        <div class="hero">
            <div class="hero-badge">⚡ Pre-Underwriting Intelligence</div>
            <h1>Know before you apply</h1>
            <p>Get your professional risk assessment • 20 free assessments • Then R49/full report</p>
        </div>
        
        <div class="main-container">
            <div class="form-card">
                <div class="form-header"><h2>Client Assessment</h2></div>
                <div class="form-body">
                    <form id="assessmentForm">
                        <div class="row-group">
                            <div class="form-group"><label>Age</label><input type="number" id="age" required min="18" max="80" placeholder="35"></div>
                            <div class="form-group"><label>Gender</label><select id="gender"><option value="male">Male</option><option value="female">Female</option></select></div>
                        </div>
                        <div class="form-group"><label>Smoker</label><div class="radio-group"><label><input type="radio" name="smoker" value="yes"> Yes</label><label><input type="radio" name="smoker" value="no" checked> No</label></div></div>
                        <div class="form-group"><label>Annual Income (ZAR)</label><input type="number" id="income" required placeholder="500000"></div>
                        <div class="form-group"><label>Coverage Amount (ZAR)</label><div class="inline-group"><select id="coverage_preset"><option value="1000000">R1,000,000</option><option value="2000000">R2,000,000</option><option value="3000000">R3,000,000</option><option value="5000000">R5,000,000</option><option value="10000000">R10,000,000</option><option value="custom">Custom</option></select><input type="number" id="coverage_custom" placeholder="Enter amount" style="display:none"></div></div>
                        <div class="form-group"><label>Term (Years)</label><div class="inline-group"><select id="term_preset"><option value="10">10</option><option value="15">15</option><option value="20" selected>20</option><option value="25">25</option><option value="30">30</option><option value="custom">Custom</option></select><input type="number" id="term_custom" placeholder="Enter years" style="display:none"></div></div>
                        <button type="submit" class="btn-primary" id="calculateBtn">Calculate Risk Score →</button>
                    </form>
                    <div class="error" id="error"></div>
                </div>
            </div>
            
            <div>
                <div class="result-card" id="resultCard">
                    <div id="remainingContainer" class="remaining-badge"></div>
                    <div id="freeResult">
                        <div class="result-score"><div class="score-number" id="riskScore">—</div><div class="score-label">Risk Score (0-100)</div></div>
                        <div class="result-section"><h4>Risk Classification</h4><div id="riskLabel">Complete the form to see results</div></div>
                        <div class="result-section"><h4>Premium Estimate</h4><div id="premiumText">—</div></div>
                        <div class="result-section"><h4>Key Risk Drivers</h4><div id="driversList">—</div></div>
                        <div class="paywall" id="paywall"><h3>📄 Full Actuarial Report</h3><p>Get the complete professional report</p><div class="paywall-price">R49<span style="font-size:14px;">.00</span></div><button class="btn-pay" id="payBtn">Unlock Full Report →</button><p style="font-size:11px; margin-top:12px;">One-time payment · Instant download</p></div>
                    </div>
                    <div id="loadingResult" class="loading hidden">⏳ Calculating risk assessment...</div>
                </div>
            </div>
        </div>
        
        <div class="footer"><p>Vettify PreCheck · Professional pre-underwriting intelligence</p></div>
        
        <script>
            let currentResult = null;
            let userEmail = localStorage.getItem('vettify_email');
            let remainingFree = 20;
            
            async function checkRemaining() {
                if (!userEmail) return;
                const response = await fetch(`/usage?email=${userEmail}`);
                const data = await response.json();
                remainingFree = 20 - data.count;
                document.getElementById('remainingContainer').innerHTML = `✨ ${remainingFree} free assessments remaining`;
                if (remainingFree <= 0) {
                    document.getElementById('paywall').style.display = 'block';
                }
            }
            
            function showBrokerModal() { alert('Broker Dashboard\n\nContact: hello@vettifyprecheck.com\nR1,999/month for lead access'); }
            
            document.getElementById('assessmentForm').addEventListener('submit', async (e) => {
                e.preventDefault();
                
                if (!userEmail) {
                    userEmail = prompt('Enter your email to start your 20 free assessments:');
                    if (userEmail) {
                        localStorage.setItem('vettify_email', userEmail);
                        checkRemaining();
                    } else { return; }
                }
                
                const response = await fetch(`/usage?email=${userEmail}`);
                const usage = await response.json();
                if (usage.count >= 20) {
                    alert('You\'ve used your 20 free assessments. Please purchase the full report for R49.');
                    return;
                }
                
                const calculateBtn = document.getElementById('calculateBtn');
                const loadingDiv = document.getElementById('loadingResult');
                const resultDiv = document.getElementById('freeResult');
                const errorDiv = document.getElementById('error');
                
                calculateBtn.disabled = true;
                calculateBtn.textContent = 'Calculating...';
                loadingDiv.classList.remove('hidden');
                resultDiv.classList.add('hidden');
                errorDiv.style.display = 'none';
                
                const formData = {
                    age: parseInt(document.getElementById('age').value),
                    gender: document.getElementById('gender').value,
                    smoker: document.querySelector('input[name="smoker"]:checked').value === 'yes',
                    income_band: parseInt(document.getElementById('income').value),
                    coverage_amount: parseInt(document.getElementById('coverage_preset').value === 'custom' ? document.getElementById('coverage_custom').value : document.getElementById('coverage_preset').value),
                    term_years: parseInt(document.getElementById('term_preset').value === 'custom' ? document.getElementById('term_custom').value : document.getElementById('term_preset').value),
                    email: userEmail
                };
                
                try {
                    const response = await fetch('/calculate', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(formData) });
                    const result = await response.json();
                    currentResult = result;
                    
                    document.getElementById('riskScore').innerHTML = result.risk_score;
                    document.getElementById('riskLabel').innerHTML = `<span style="color: ${result.color}; font-weight: 700;">${result.risk_level}</span><br><small>${result.risk_comment}</small>`;
                    document.getElementById('premiumText').innerHTML = `<div class="premium-box"><span class="premium-amount">R${result.premium} - R${result.premium + 150}</span><br><small>per month</small></div>`;
                    
                    let drivers = '';
                    if (formData.smoker) drivers += '• Smoker: +80-100% premium loading<br>';
                    else drivers += '• Non-smoker: Standard rates<br>';
                    if (formData.age > 50) drivers += '• Age >50: Additional medical underwriting<br>';
                    else if (formData.age > 40) drivers += '• Age 40-50: Standard underwriting<br>';
                    else drivers += '• Age <40: Favorable rates<br>';
                    document.getElementById('driversList').innerHTML = drivers;
                    
                    loadingDiv.classList.add('hidden');
                    resultDiv.classList.remove('hidden');
                    calculateBtn.disabled = false;
                    calculateBtn.textContent = 'Calculate Risk Score →';
                    
                    const usageCheck = await fetch(`/usage?email=${userEmail}`);
                    const newUsage = await usageCheck.json();
                    document.getElementById('remainingContainer').innerHTML = `✨ ${20 - newUsage.count} free assessments remaining`;
                    
                } catch (error) {
                    errorDiv.textContent = 'Error calculating. Please try again.';
                    errorDiv.style.display = 'block';
                    calculateBtn.disabled = false;
                    calculateBtn.textContent = 'Calculate Risk Score →';
                    loadingDiv.classList.add('hidden');
                }
            });
            
            document.getElementById('payBtn').addEventListener('click', async () => {
                if (!currentResult) return;
                const email = prompt('Confirm your email to receive the full report:');
                if (!email) return;
                
                const btn = document.getElementById('payBtn');
                btn.textContent = 'Processing...';
                btn.disabled = true;
                
                try {
                    const response = await fetch('/generate-full-report', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ ...currentResult.data, email: email })
                    });
                    const blob = await response.blob();
                    const url = window.URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = `vettify_report_${currentResult.data.age}.pdf`;
                    a.click();
                    window.URL.revokeObjectURL(url);
                    alert('Report downloaded! Check your downloads folder.');
                    btn.textContent = 'Unlock Full Report →';
                    btn.disabled = false;
                } catch (error) {
                    alert('Error generating report. Please try again.');
                    btn.textContent = 'Unlock Full Report →';
                    btn.disabled = false;
                }
            });
            
            checkRemaining();
        </script>
    </body>
    </html>
    '''

@app.route('/calculate', methods=['POST'])
def calculate():
    data = request.json
    email = data.get('email')
    
    # Check usage limit
    usage = load_data(USAGE_FILE)
    if email in usage and usage[email]['count'] >= 20:
        return jsonify({'error': 'Free limit reached'}), 403
    
    # Increment usage
    if email not in usage:
        usage[email] = {'count': 0, 'first_use': datetime.now().isoformat()}
    usage[email]['count'] += 1
    save_data(USAGE_FILE, usage)
    
    risk_level, risk_comment, risk_score, color, risk_label = determine_risk_level(
        data['age'], data['smoker'], data['coverage_amount'], data['income_band']
    )
    premium = calculate_premium(
        data['age'], data['gender'], data['smoker'], 
        data['income_band'], data['coverage_amount'], data['term_years']
    )
    
    return jsonify({
        'risk_score': risk_score,
        'risk_level': risk_label,
        'risk_comment': risk_comment,
        'color': color,
        'premium': premium,
        'data': data
    })

@app.route('/generate-full-report', methods=['POST'])
def generate_full_report_route():
    data = request.json
    email = data.get('email')
    
    # Store lead
    leads = load_data(LEADS_FILE)
    lead_id = str(uuid.uuid4())
    leads[lead_id] = {
        'email': email,
        'age': data['age'],
        'gender': data['gender'],
        'smoker': data['smoker'],
        'income': data['income_band'],
        'coverage': data['coverage_amount'],
        'term': data['term_years'],
        'timestamp': datetime.now().isoformat(),
        'status': 'paid'
    }
    save_data(LEADS_FILE, leads)
    
    pdf_buffer = generate_full_report(data)
    
    return send_file(
        pdf_buffer,
        mimetype='application/pdf',
        as_attachment=True,
        download_name=f'vettify_report_{data["age"]}.pdf'
    )

@app.route('/usage', methods=['GET'])
def get_usage():
    email = request.args.get('email')
    usage = load_data(USAGE_FILE)
    count = usage[email]['count'] if email in usage else 0
    return jsonify({'count': count})

@app.route('/broker-dashboard')
def broker_dashboard():
    leads = load_data(LEADS_FILE)
    return jsonify(list(leads.values()))

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)
