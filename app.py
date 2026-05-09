from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from datetime import datetime
import os
import uuid
import json

app = Flask(__name__)
app.secret_key = os.urandom(24).hex()
CORS(app)

# ================= TRADE RISK ENGINE =================

def calculate_risk_metrics(account_size, entry_price, stop_loss, position_type, lot_size=None):
    """Calculate all risk metrics for a trade"""
    if not lot_size:
        # Default lot size calculation (1% risk recommendation)
        risk_amount = account_size * 0.01
        pip_distance = abs(entry_price - stop_loss)
        pip_value = 10  # Standard for 1 standard lot on major pairs
        lot_size = risk_amount / (pip_distance * pip_value)
        lot_size = round(max(0.01, min(lot_size, 10)), 2)
    
    pip_distance = abs(entry_price - stop_loss)
    pip_value_per_lot = 10
    position_value = lot_size * 100000
    
    potential_loss = pip_distance * pip_value_per_lot * lot_size
    risk_percent = (potential_loss / account_size) * 100
    risk_percent = round(risk_percent, 2)
    
    return {
        'risk_percent': risk_percent,
        'recommended_lot_size': round(lot_size, 2),
        'potential_loss': round(potential_loss, 2),
        'pip_distance': round(pip_distance, 1),
        'is_risky': risk_percent > 2
    }

def calculate_rr_ratio(entry_price, stop_loss, take_profit, position_type):
    """Calculate Risk-to-Reward ratio"""
    if not take_profit:
        return 0
    
    if position_type == 'buy':
        risk = entry_price - stop_loss
        reward = take_profit - entry_price
    else:
        risk = stop_loss - entry_price
        reward = entry_price - take_profit
    
    if risk <= 0:
        return 0
    
    rr_ratio = round(reward / risk, 2)
    return rr_ratio

def generate_ai_feedback(trade_data, user_rules, risk_metrics, rr_ratio):
    """Generate intelligent AI coaching feedback for TrayDay Discipline"""
    feedback = []
    warnings = []
    is_pass = True
    
    # Risk percentage check
    if risk_metrics['risk_percent'] > user_rules.get('max_risk_per_trade', 2):
        warnings.append(f"⚠️ Risk is too high: {risk_metrics['risk_percent']}% > {user_rules.get('max_risk_per_trade', 2)}% limit")
        feedback.append("This trade risks more than your maximum per-trade rule. Reduce position size.")
        is_pass = False
    elif risk_metrics['risk_percent'] > 2:
        warnings.append(f"⚠️ High risk: {risk_metrics['risk_percent']}% of account")
        feedback.append("Risk level is elevated. Consider reducing lot size.")
    else:
        feedback.append("✅ Risk is well-controlled for your account size.")
    
    # RR Ratio check
    min_rr = user_rules.get('min_rr_ratio', 1.5)
    if trade_data.get('take_profit') and rr_ratio < min_rr:
        warnings.append(f"⚠️ Low RR Ratio: {rr_ratio}:1 < {min_rr}:1 minimum")
        feedback.append(f"Risk-to-reward is {rr_ratio}:1. Your minimum is {min_rr}:1. Widen your target or tighten stop loss.")
        is_pass = False
    elif trade_data.get('take_profit') and rr_ratio >= 2:
        feedback.append(f"🎯 Excellent RR ratio of {rr_ratio}:1! This offers good expectancy.")
    elif trade_data.get('take_profit'):
        feedback.append(f"📊 RR ratio of {rr_ratio}:1 meets your minimum requirement.")
    
    # Confidence level psychology
    confidence = trade_data.get('confidence', 5)
    if confidence < 4:
        feedback.append("🧠 Low confidence suggests uncertainty. Consider waiting for clearer setup.")
    elif confidence > 8:
        feedback.append("🔥 High confidence trade. Don't let it lead to overleveraging.")
    
    if not feedback:
        feedback.append("✅ Trade aligns with your TrayDay Discipline rules. Good discipline!")
    
    return {
        'feedback': " | ".join(feedback[:3]),
        'warnings': warnings,
        'pass_status': is_pass,
        'rr_ratio': rr_ratio if trade_data.get('take_profit') else None
    }

def get_user_rules(user_id):
    """Get user's trading rules"""
    rules_file = f'trades_db/rules_{user_id}.json'
    if os.path.exists(rules_file):
        with open(rules_file, 'r') as f:
            return json.load(f)
    
    return {
        'max_daily_loss': 1000,
        'max_risk_per_trade': 2,
        'min_rr_ratio': 1.5,
        'max_trades_per_day': 5
    }

def save_user_rules(user_id, rules):
    """Save user's trading rules"""
    if not os.path.exists('trades_db'):
        os.makedirs('trades_db')
    
    rules_file = f'trades_db/rules_{user_id}.json'
    with open(rules_file, 'w') as f:
        json.dump(rules, f)

# ================= ROUTES =================

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/api/analyze-trade', methods=['POST'])
def analyze_trade():
    """Real-time trade analysis without saving"""
    try:
        data = request.json
        user_id = data.get('user_id', 'anonymous')
        user_rules = get_user_rules(user_id)
        
        account_size = float(data['account_size'])
        risk_metrics = calculate_risk_metrics(
            account_size,
            float(data['entry_price']),
            float(data['stop_loss']),
            data['position_type'],
            float(data.get('lot_size', 0)) if data.get('lot_size') else None
        )
        
        rr_ratio = calculate_rr_ratio(
            float(data['entry_price']),
            float(data['stop_loss']),
            float(data['take_profit']) if data.get('take_profit') else None,
            data['position_type']
        )
        
        ai_feedback = generate_ai_feedback(data, user_rules, risk_metrics, rr_ratio)
        
        return jsonify({
            'success': True,
            'risk_metrics': risk_metrics,
            'ai_feedback': ai_feedback['feedback'],
            'pass_status': ai_feedback['pass_status'],
            'warnings': ai_feedback['warnings'],
            'rr_ratio': rr_ratio
        })
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/save-trade', methods=['POST'])
def save_trade():
    try:
        data = request.json
        trade_id = str(uuid.uuid4())
        user_id = data.get('user_id', 'anonymous')
        
        # Get user rules
        user_rules = get_user_rules(user_id)
        
        # Calculate metrics
        account_size = float(data['account_size'])
        risk_metrics = calculate_risk_metrics(
            account_size,
            float(data['entry_price']),
            float(data['stop_loss']),
            data['position_type'],
            float(data.get('lot_size', 0)) if data.get('lot_size') else None
        )
        
        rr_ratio = calculate_rr_ratio(
            float(data['entry_price']),
            float(data['stop_loss']),
            float(data.get('take_profit')) if data.get('take_profit') else None,
            data['position_type']
        )
        
        # Generate AI feedback
        ai_data = generate_ai_feedback(data, user_rules, risk_metrics, rr_ratio)
        
        trade_record = {
            'id': trade_id,
            'user_id': user_id,
            'date': datetime.now().isoformat(),
            'currency_pair': data['currency_pair'],
            'position_type': data['position_type'],
            'account_size': account_size,
            'entry_price': float(data['entry_price']),
            'stop_loss': float(data['stop_loss']),
            'take_profit': float(data['take_profit']) if data.get('take_profit') else None,
            'lot_size': risk_metrics['recommended_lot_size'],
            'confidence': data.get('confidence', 5),
            'notes': data.get('notes', ''),
            'risk_percent': risk_metrics['risk_percent'],
            'rr_ratio': rr_ratio,
            'potential_loss': risk_metrics['potential_loss'],
            'ai_feedback': ai_data['feedback'],
            'passed_rules': ai_data['pass_status'],
            'warnings': ','.join(ai_data['warnings']),
            'result': None
        }
        
        # Save to local storage
        if not os.path.exists('trades_db'):
            os.makedirs('trades_db')
        
        trades_file = f'trades_db/{user_id}.json'
        existing = []
        if os.path.exists(trades_file):
            with open(trades_file, 'r') as f:
                existing = json.load(f)
        existing.append(trade_record)
        with open(trades_file, 'w') as f:
            json.dump(existing, f)
        
        return jsonify({
            'success': True,
            'trade_id': trade_id,
            'risk_metrics': risk_metrics,
            'ai_feedback': ai_data['feedback'],
            'pass_status': ai_data['pass_status'],
            'warnings': ai_data['warnings'],
            'rr_ratio': rr_ratio
        })
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/get-trades', methods=['GET'])
def get_trades():
    user_id = request.args.get('user_id', 'anonymous')
    limit = int(request.args.get('limit', 100))
    
    trades_file = f'trades_db/{user_id}.json'
    if os.path.exists(trades_file):
        with open(trades_file, 'r') as f:
            trades = json.load(f)
        trades = sorted(trades, key=lambda x: x['date'], reverse=True)[:limit]
    else:
        trades = []
    
    # Calculate stats
    total_trades = len(trades)
    completed = [t for t in trades if t.get('result') in ['win', 'loss']]
    wins = len([t for t in completed if t.get('result') == 'win'])
    win_rate = (wins / len(completed) * 100) if completed else 0
    
    rr_values = [t.get('rr_ratio', 0) for t in trades if t.get('rr_ratio')]
    avg_rr = sum(rr_values) / len(rr_values) if rr_values else 0
    
    # Calculate current streak
    streak = 0
    for t in sorted(trades, key=lambda x: x.get('date', ''), reverse=True):
        if t.get('result') == 'win':
            streak += 1
        elif t.get('result') == 'loss':
            break
        else:
            break
    
    return jsonify({
        'trades': trades,
        'stats': {
            'total_trades': total_trades,
            'win_rate': round(win_rate, 1),
            'avg_rr': round(avg_rr, 2),
            'current_streak': streak
        }
    })

@app.route('/api/save-rules', methods=['POST'])
def save_rules():
    try:
        data = request.json
        user_id = data.get('user_id', 'anonymous')
        
        rules = {
            'max_daily_loss': data.get('max_daily_loss', 1000),
            'max_risk_per_trade': data.get('max_risk_per_trade', 2),
            'min_rr_ratio': data.get('min_rr_ratio', 1.5),
            'max_trades_per_day': data.get('max_trades_per_day', 5)
        }
        
        save_user_rules(user_id, rules)
        
        return jsonify({'success': True, 'rules': rules})
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/get-rules', methods=['GET'])
def get_rules():
    user_id = request.args.get('user_id', 'anonymous')
    rules = get_user_rules(user_id)
    return jsonify(rules)

@app.route('/api/update-trade-result', methods=['POST'])
def update_trade_result():
    try:
        data = request.json
        trade_id = data['trade_id']
        result = data['result']
        user_id = data.get('user_id', 'anonymous')
        
        trades_file = f'trades_db/{user_id}.json'
        if os.path.exists(trades_file):
            with open(trades_file, 'r') as f:
                trades = json.load(f)
            
            for trade in trades:
                if trade['id'] == trade_id:
                    trade['result'] = result
                    break
            
            with open(trades_file, 'w') as f:
                json.dump(trades, f)
        
        return jsonify({'success': True})
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

if __name__ == '__main__':
    if not os.path.exists('trades_db'):
        os.makedirs('trades_db')
    app.run(debug=True, port=5000)
