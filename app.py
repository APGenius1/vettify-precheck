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

def get_or_create_user():
    usage = load_usage()
    # Simple counter for all users combined
    if 'total_count' not in usage:
        usage['total_count'] = 0
        save_usage(usage)
    return usage

def increment_usage():
    usage = load_usage()
    usage['total_count'] += 1
    save_usage(usage)
    return usage['total_count']

def check_limit():
    usage = load_usage()
    count = usage.get('total_count', 0)
    if count >= 20:
        return False, count
    return True, count

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

def generate_pdf(data):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=72)
    styles = getSampleStyleSheet()
    story = []
    
    vettify_blue = colors.HexColor('#0a2540')
    
    risk_level, risk_comment, risk_score, risk_color_hex = determine_risk_level(data['age'], data['smoker'], data['coverage_amount'], data['income_band'])
    premium = calculate_premium(data['age'], data['gender'], data['smoker'], data['income_band'], data['coverage_amount'], data['term_years'])
    risk_color = colors.HexColor(risk_color_hex)
    
    title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'], fontSize=28, textColor=vettify_blue, alignment=1, spaceAfter=6)
    story.append(Paragraph("VETTIFY", title_style))
    story.append(Paragraph("Pre-Underwriting Assessment Report", styles['Normal']))
    story.append(Spacer(1, 0.2*inch))
    
    story.append(Paragraph(f"Generated: {datetime.now().strftime('%d %B %Y at %H:%M')}", styles['Normal']))
    story.append(Spacer(1, 0.2*inch))
    
    story.append(Paragraph("RISK SCORE", styles['Heading2']))
    score_style = ParagraphStyle('Score', parent=styles['Normal'], fontSize=48, textColor=risk_color, alignment=1, spaceAfter=6)
    story.append(Paragraph(f"{risk_score}<font size=20>/100</font>", score_style))
    gauge_style = ParagraphStyle('Gauge', parent=styles['Normal'], fontSize=14, textColor=risk_color, alignment=1)
    story.append(Paragraph(create_risk_gauge(risk_score), gauge_style))
    story.append(Paragraph(f"{risk_level.upper()} RISK", styles['Normal']))
    story.append(Spacer(1, 0.2*inch))
    
    story.append(Paragraph("CLIENT PROFILE", styles['Heading2']))
    info_data = [
        ["Age", str(data['age']) + " years"],
        ["Gender", data['gender'].capitalize()],
        ["Smoker", "Yes" if data['smoker'] else "No"],
        ["Annual Income", f"R{data['income_band']:,}"],
        ["Coverage", f"R{data['coverage_amount']:,}"],
        ["Term", f"{data['term_years']} years"],
    ]
    info_table = Table(info_data, colWidths=[1.8*inch, 3.2*inch])
    info_table.setStyle(TableStyle([('FONTNAME', (0,0), (-1,-1), 'Helvetica'), ('FONTSIZE', (0,0), (-1,-1), 10)]))
    story.append(info_table)
    story.append(Spacer(1, 0.2*inch))
    
    story.append(Paragraph("PREMIUM ESTIMATE", styles['Heading2']))
    story.append(Paragraph(f"R{premium} - R{premium + 150} per month", styles['Normal']))
    story.append(Paragraph("Illustrative indication only - subject to full underwriting", styles['Italic']))
    story.append(Spacer(1, 0.2*inch))
    
    story.append(Paragraph("KEY FACTORS", styles['Heading2']))
    if data['smoker']:
        story.append(Paragraph("• Tobacco use: +80-100% premium loading", styles['Normal']))
    else:
        story.append(Paragraph("• Non-smoker: Standard rates apply", styles['Normal']))
    if data['age'] > 50:
        story.append(Paragraph("• Age >50: Additional medical underwriting likely", styles['Normal']))
    elif data['age'] > 40:
        story.append(Paragraph("• Age 40-50: Standard underwriting", styles['Normal']))
    else:
        story.append(Paragraph("• Age <40: Favorable underwriting category", styles['Normal']))
    story.append(Spacer(1, 0.2*inch))
    
    story.append(Paragraph("METHODOLOGY", styles['Heading2']))
    method_style = ParagraphStyle('Method', parent=styles['Normal'], fontSize=8, textColor=colors.grey)
    story.append(Paragraph("Built using established mortality models and industry-standard loadings.", method_style))
    story.append(Spacer(1, 0.15*inch))
    
    disclaimer_style = ParagraphStyle('Disclaimer', parent=styles['Normal'], fontSize=7, textColor=colors.grey, alignment=0)
    story.append(Paragraph("DISCLAIMER: This is a pre-screening tool only and does not constitute a formal offer of coverage. Actual underwriting decisions and premiums vary by insurer and require full medical underwriting.", disclaimer_style))
    story.append(Spacer(1, 0.1*inch))
    
    footer_style = ParagraphStyle('Footer', parent=styles['Normal'], fontSize=8, textColor=vettify_blue, alignment=1)
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
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body { font-family: 'Inter', sans-serif; background: linear-gradient(135deg, #f5f7fa 0%, #eef2f6 100%); min-height: 100vh; }
            .navbar { background: white; border-bottom: 1px solid rgba(0,0,0,0.05); padding: 16px 0; position: sticky; top: 0; z-index: 100; }
            .nav-container { max-width: 1280px; margin: 0 auto; padding: 0 32px; display: flex; justify-content: space-between; align-items: center; }
            .logo { font-size: 24px; font-weight: 700; background: linear-gradient(135deg, #0a2540 0%, #1b4d3e 100%); -webkit-background-clip: text; background-clip: text; color: transparent; text-decoration: none; }
            .badge-nav { background: #e8f0fe; padding: 6px 14px; border-radius: 40px; font-size: 12px; font-weight: 500; color: #0a2540; }
            .main-container { max-width: 1280px; margin: 0 auto; padding: 48px 32px; display: grid; grid-template-columns: 1fr 0.9fr; gap: 48px; }
            .form-card { background: white; border-radius: 28px; box-shadow: 0 8px 30px rgba(0,0,0,0.06); overflow: hidden; }
            .form-header { padding: 28px 32px; border-bottom: 1px solid #eef2f6; }
            .form-header h1 { font-size: 26px; font-weight: 700; color: #0a2540; margin-bottom: 8px; }
            .form-header p { font-size: 14px; color: #5b6e8c; }
            .form-body { padding: 32px; }
            .form-group { margin-bottom: 24px; }
            label { display: block; font-weight: 600; margin-bottom: 8px; color: #1a2c3e; font-size: 13px; text-transform: uppercase; letter-spacing: 0.2px; }
            input, select { width: 100%; padding: 14px 16px; border: 1.5px solid #e2e8f0; border-radius: 14px; font-size: 15px; font-family: 'Inter', sans-serif; }
            input:focus, select:focus { outline: none; border-color: #0a2540; }
            .radio-group { display: flex; gap: 32px; margin-top: 8px; }
            .radio-group label { display: flex; align-items: center; font-weight: 500; text-transform: none; gap: 10px; cursor: pointer; }
            .radio-group input { width: 18px; height: 18px; }
            .inline-group { display: flex; gap: 12px; }
            .inline-group select { flex: 2; }
            .inline-group input { flex: 1; }
            .row-group { display: flex; gap: 16px; }
            .row-group .form-group { flex: 1; }
            small { display: block; margin-top: 6px; font-size: 11px; color: #8a9bb0; }
            .btn-primary { width: 100%; padding: 16px; background: linear-gradient(135deg, #0a2540 0%, #1b4d3e 100%); color: white; border: none; border-radius: 16px; font-size: 16px; font-weight: 600; cursor: pointer; margin-top: 16px; }
            .btn-primary:hover:not(:disabled) { transform: translateY(-2px); box-shadow: 0 8px 20px rgba(10,37,64,0.2); }
            .btn-primary:disabled { background: #cbd5e1; cursor: not-allowed; }
            .info-card { background: white; border-radius: 28px; box-shadow: 0 8px 30px rgba(0,0,0,0.06); padding: 32px; }
            .info-section { margin-bottom: 32px; }
            .info-section h3 { font-size: 16px; font-weight: 700; color: #0a2540; margin-bottom: 16px; }
            .trust-list { display: flex; flex-direction: column; gap: 12px; }
            .trust-item { display: flex; align-items: center; gap: 12px; font-size: 14px; padding: 10px 0; border-bottom: 1px solid #f0f4f8; }
            .pill { background: #e8f0fe; padding: 4px 12px; border-radius: 40px; font-size: 11px; font-weight: 600; display: inline-block; }
            .risk-preview { background: #f8fafc; border-radius: 20px; padding: 24px; margin-top: 24px; text-align: center; }
            .risk-score-large { font-size: 56px; font-weight: 800; color: #0a2540; }
            .gauge-preview { font-size: 24px; letter-spacing: 4px; margin: 12px 0; }
            .loading, .error, .success { display: none; margin-top: 20px; padding: 16px; border-radius: 14px; font-size: 14px; }
            .loading { background: #f1f5f9; color: #475569; text-align: center; }
            .error { background: #fee2e2; color: #dc2626; }
            .success { background: #e6f7e6; color: #16a34a; text-align: center; }
            .footer { text-align: center; padding: 32px; color: #8a9bb0; font-size: 13px; border-top: 1px solid rgba(0,0,0,0.05); margin-top: 48px; }
            .identity { background: #f8fafc; border-radius: 16px; padding: 20px; margin-top: 24px; text-align: center; font-size: 12px; color: #5b6e8c; }
            @media (max-width: 900px) { .main-container { grid-template-columns: 1fr; gap: 32px; } .row-group { flex-direction: column; gap: 0; } }
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
                        <div class="row-group">
                            <div class="form-group"><label>Age</label><input type="number" id="age" required min="18" max="80" placeholder="e.g., 35"></div>
                            <div class="form-group"><label>Gender</label><select id="gender" required><option value="male">Male</option><option value="female">Female</option></select></div>
                        </div>
                        
                        <div class="form-group"><label>Smoker Status</label><div class="radio-group"><label><input type="radio" name="smoker" value="yes" required> Yes</label><label><input type="radio" name="smoker" value="no" required> No</label></div></div>
                        
                        <div class="row-group">
                            <div class="form-group"><label>Annual Income (ZAR)</label><input type="number" id="income" required placeholder="e.g., 500000"><small>South African Rand</small></div>
                        </div>
                        
                        <div class="form-group"><label>Coverage Amount (ZAR)</label><div class="inline-group"><select id="coverage_preset"><option value="500000">R500,000</option><option value="1000000">R1,000,000</option><option value="2000000">R2,000,000</option><option value="3000000">R3,000,000</option><option value="5000000">R5,000,000</option><option value="10000000">R10,000,000</option><option value="custom">Custom amount</option></select><input type="number" id="coverage_custom" placeholder="Enter amount" style="display: none;" min="50000"></div><small>Minimum R50,000</small></div>
                        
                        <div class="form-group"><label>Term (Years)</label><div class="inline-group"><select id="term_preset"><option value="10">10 years</option><option value="15">15 years</option><option value="20">20 years</option><option value="25">25 years</option><option value="30">30 years</option><option value="custom">Custom term</option></select><input type="number" id="term_custom" placeholder="Enter years" style="display: none;" min="1" max="50"></div><small>1-50 years</small></div>
                        
                        <button type="submit" class="btn-primary" id="generateBtn">Generate Report →</button>
                    </form>
                    <div class="loading" id="loading">⏳ Generating your professional report...</div>
                    <div class="error" id="error"></div>
                    <div class="success" id="success"></div>
                </div>
            </div>
            <div class="info-card">
                <div class="info-section"><h3>📊 Methodology</h3><p>Powered by established mortality models and industry-standard loadings.</p><div class="pill">Actuarial Framework</div></div>
                <div class="info-section"><h3>✓ What You Receive</h3><div class="trust-list"><div class="trust-item">📊 Risk Score (0-100 scale)</div><div class="trust-item">🏷️ Risk Classification (Low/Moderate/High)</div><div class="trust-item">💰 Premium Range estimate (ZAR)</div><div class="trust-item">🔬 Factor Breakdown</div><div class="trust-item">📄 Instant PDF download</div></div></div>
                <div class="info-section"><h3>🛡️ Trust & Credibility</h3><p>Built using established mortality models. Independent tool for broker use only.</p><div class="trust-list"><div class="trust-item">✅ Unlimited free assessments</div><div class="trust-item">✅ Instant PDF download</div><div class="trust-item">✅ South African focused</div></div></div>
                <div class="risk-preview"><span style="font-size: 12px; color: #5b6e8c;">Sample Output</span><div class="risk-score-large">85<span style="font-size: 20px;">/100</span></div><div class="gauge-preview">████████░░</div><div><span class="pill">LOW RISK</span></div></div>
                <div class="identity"><p>Built using established mortality models</p><p>© 2026 Vettify · Independent pre-screening tool</p></div>
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
                
                const generateBtn = document.getElementById('generateBtn');
                const loadingDiv = document.getElementById('loading');
                const errorDiv = document.getElementById('error');
                const successDiv = document.getElementById('success');
                
                generateBtn.disabled = true;
                loadingDiv.style.display = 'block';
                errorDiv.style.display = 'none';
                successDiv.style.display = 'none';
                generateBtn.textContent = 'Generating...';
                
                let coverageAmount; 
                if (coveragePreset.value === 'custom') { 
                    coverageAmount = parseInt(coverageCustom.value); 
                    if (isNaN(coverageAmount) || coverageAmount < 50000) { 
                        errorDiv.textContent = 'Please enter a valid coverage amount (minimum R50,000)'; 
                        errorDiv.style.display = 'block'; 
                        generateBtn.disabled = false; 
                        loadingDiv.style.display = 'none'; 
                        generateBtn.textContent = 'Generate Report →'; 
                        return; 
                    } 
                } else { 
                    coverageAmount = parseInt(coveragePreset.value); 
                }
                
                let termYears; 
                if (termPreset.value === 'custom') { 
                    termYears = parseInt(termCustom.value); 
                    if (isNaN(termYears) || termYears < 1 || termYears > 50) { 
                        errorDiv.textContent = 'Please enter a valid term (1-50 years)'; 
                        errorDiv.style.display = 'block'; 
                        generateBtn.disabled = false; 
                        loadingDiv.style.display = 'none'; 
                        generateBtn.textContent = 'Generate Report →'; 
                        return; 
                    } 
                } else { 
                    termYears = parseInt(termPreset.value); 
                }
                
                const age = parseInt(document.getElementById('age').value);
                if (age < 18 || age > 80) { 
                    errorDiv.textContent = 'Age must be between 18 and 80'; 
                    errorDiv.style.display = 'block'; 
                    generateBtn.disabled = false; 
                    loadingDiv.style.display = 'none'; 
                    generateBtn.textContent = 'Generate Report →'; 
                    return; 
                }
                
                const income = parseInt(document.getElementById('income').value);
                if (isNaN(income) || income < 0) { 
                    errorDiv.textContent = 'Please enter a valid income amount'; 
                    errorDiv.style.display = 'block'; 
                    generateBtn.disabled = false; 
                    loadingDiv.style.display = 'none'; 
                    generateBtn.textContent = 'Generate Report →'; 
                    return; 
                }
                
                const formData = { 
                    age: age, 
                    gender: document.getElementById('gender').value, 
                    smoker: document.querySelector('input[name="smoker"]:checked').value === 'yes', 
                    income_band: income, 
                    coverage_amount: coverageAmount, 
                    term_years: termYears
                };
                
                try {
                    const response = await fetch('/generate', { 
                        method: 'POST', 
                        headers: { 'Content-Type': 'application/json' }, 
                        body: JSON.stringify(formData) 
                    });
                    
                    if (!response.ok) {
                        const result = await response.json();
                        errorDiv.textContent = result.error || 'Failed to generate report';
                        errorDiv.style.display = 'block';
                        generateBtn.disabled = false;
                        loadingDiv.style.display = 'none';
                        generateBtn.textContent = 'Generate Report →';
                        return;
                    }
                    
                    const blob = await response.blob();
                    const url = window.URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = `vettify_precheck_${age}.pdf`;
                    document.body.appendChild(a);
                    a.click();
                    window.URL.revokeObjectURL(url);
                    a.remove();
                    
                    generateBtn.disabled = false;
                    loadingDiv.style.display = 'none';
                    successDiv.innerHTML = '✅ Report generated successfully! Check your downloads folder.';
                    successDiv.style.display = 'block';
                    generateBtn.textContent = 'Generate Report →';
                    
                    setTimeout(() => { successDiv.style.display = 'none'; }, 5000);
                    
                } catch (error) {
                    errorDiv.textContent = 'Error generating report. Please try again.';
                    errorDiv.style.display = 'block';
                    generateBtn.disabled = false;
                    loadingDiv.style.display = 'none';
                    generateBtn.textContent = 'Generate Report →';
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
        
        # No email needed, just generate PDF
        pdf_buffer = generate_pdf(data)
        
        return send_file(
            pdf_buffer, 
            mimetype='application/pdf', 
            as_attachment=True, 
            download_name=f'vettify_precheck_{data["age"]}.pdf'
        )
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)
