from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from datetime import datetime, date
import os
import uuid
from supabase import create_client, Client
from dotenv import load_dotenv
import re

load_dotenv()

app = Flask(__name__, static_folder='build', static_url_path='')
app.secret_key = os.urandom(24).hex()
CORS(app)

# Supabase setup
SUPABASE_URL = os.getenv('SUPABASE_URL', 'your_supabase_url')
SUPABASE_KEY = os.getenv('SUPABASE_KEY', 'your_supabase_key')
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ================= TRADE RISK ENGINE =================

def calculate_risk_metrics(account_size, entry_price, stop_loss, position_type, lot_size=None):
    """Calculate all risk metrics for a trade"""
    if not lot_size:
        # Default lot size calculation (1% risk recommendation)
        risk_amount = account_size * 0.01
        pip_distance = abs(entry_price - stop_loss)
        pip_value = 10  # Standard for 1 standard lot on major pairs
        lot_size = risk_amount / (pip_distance * pip_value)
        lot_size = round(max(0.01, min(lot_size, 10)), 2)  # Cap between 0.01 and 10
    
    pip_distance = abs(entry_price - stop_loss)
    pip_value_per_lot = 10  # $10 per pip for 1 standard lot
    position_value = lot_size * 100000  # 1 lot = 100,000 units
    
    potential_loss = pip_distance * pip_value_per_lot * lot_size
    potential_profit = abs(entry_price - stop_loss) / stop_loss * position_value if take_profit else 0
    
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
    else:  # sell
        risk = stop_loss - entry_price
        reward = entry_price - take_profit
    
    if risk <= 0:
        return 0
    
    rr_ratio = round(reward / risk, 2)
    return rr_ratio

def generate_ai_feedback(trade_data, user_rules, risk_metrics):
    """Generate intelligent AI coaching feedback"""
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
    rr_ratio = calculate_rr_ratio(
        trade_data['entry_price'],
        trade_data['stop_loss'],
        trade_data.get('take_profit'),
        trade_data['position_type']
    )
    
    min_rr = user_rules.get('min_rr_ratio', 1.5)
    if trade_data.get('take_profit') and rr_ratio < min_rr:
        warnings.append(f"⚠️ Low RR Ratio: {rr_ratio}:1 < {min_rr}:1 minimum")
        feedback.append(f"Risk-to-reward is {rr_ratio}:1. Your minimum is {min_rr}:1. Widen your target or tighten stop loss.")
        is_pass = False
    elif trade_data.get('take_profit') and rr_ratio >= 2:
        feedback.append(f"🎯 Excellent RR ratio of {rr_ratio}:1! This offers good expectancy.")
    elif trade_data.get('take_profit'):
        feedback.append(f"📊 RR ratio of {rr_ratio}:1 meets your minimum requirement.")
    
    # Leverage check
    if risk_metrics['recommended_lot_size'] > 1:
        feedback.append("⚠️ Using larger lot sizes increases drawdown risk.")
    
    # Confidence level psychology
    confidence = trade_data.get('confidence', 5)
    if confidence < 4:
        feedback.append("🧠 Low confidence suggests uncertainty. Consider waiting for clearer setup.")
    elif confidence > 8:
        feedback.append("🔥 High confidence trade. Don't let it lead to overleveraging.")
    
    # Revenge trading detection (based on recent trades - would need history)
    if user_rules.get('recent_losses', 0) >= 3:
        warnings.append("⚠️ POSSIBLE REVENGE TRADING DETECTED")
        feedback.append("You've had 3+ recent losses. Take a break and review your strategy.")
        is_pass = False
    
    # Daily loss limit
    daily_loss = user_rules.get('daily_loss_today', 0)
    max_daily_loss = user_rules.get('max_daily_loss', 1000)
    if daily_loss + risk_metrics['potential_loss'] > max_daily_loss:
        warnings.append(f"⚠️ Would exceed daily loss limit by ${(daily_loss + risk_metrics['potential_loss']) - max_daily_loss}")
        feedback.append(f"This trade would exceed your ${max_daily_loss} daily loss limit. Stop trading for today.")
        is_pass = False
    
    # Overtrading detection
    trades_today = user_rules.get('trades_today', 0)
    max_trades = user_rules.get('max_trades_per_day', 5)
    if trades_today >= max_trades:
        warnings.append(f"⚠️ Overtrading detected: {trades_today}/{max_trades} trades today")
        feedback.append(f"You've reached your {max_trades} trade limit for today. Discipline means stopping here.")
        is_pass = False
    elif trades_today >= max_trades - 1:
        feedback.append(f"⚠️ This is your {trades_today + 1} trade today. Be extra selective.")
    
    if not feedback:
        feedback.append("✅ Trade aligns with your rules. Good discipline!")
    
    return {
        'feedback': " | ".join(feedback[:3]),
        'warnings': warnings,
        'pass_status': is_pass,
        'rr_ratio': rr_ratio if trade_data.get('take_profit') else None
    }

# ================= ROUTES =================

@app.route('/api/save-trade', methods=['POST'])
def save_trade():
    try:
        data = request.json
        trade_id = str(uuid.uuid4())
        
        # Get user rules
        user_id = data.get('user_id', 'anonymous')
        user_rules = get_user_rules(user_id)
        
        # Calculate metrics
        account_size = float(data['account_size'])
        risk_metrics = calculate_risk_metrics(
            account_size,
            float(data['entry_price']),
            float(data['stop_loss']),
            data['position_type'],
            float(data.get('lot_size', 0))
        )
        
        rr_ratio = calculate_rr_ratio(
            float(data['entry_price']),
            float(data['stop_loss']),
            float(data.get('take_profit')) if data.get('take_profit') else None,
            data['position_type']
        )
        
        # Generate AI feedback
        ai_data = generate_ai_feedback(data, user_rules, risk_metrics)
        
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
            'warnings': ','.join(ai_data['warnings'])
        }
        
        # Save to Supabase (or local DB if Supabase not configured)
        try:
            supabase.table('trades').insert(trade_record).execute()
        except:
            # Fallback to simple storage (for demo without Supabase)
            if not os.path.exists('trades_db'):
                os.makedirs('trades_db')
            import json
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
    limit = int(request.args.get('limit', 50))
    
    try:
        result = supabase.table('trades').select('*').eq('user_id', user_id).order('date', desc=True).limit(limit).execute()
        trades = result.data
    except:
        # Fallback to local storage
        import json
        trades_file = f'trades_db/{user_id}.json'
        if os.path.exists(trades_file):
            with open(trades_file, 'r') as f:
                trades = json.load(f)
            trades = sorted(trades, key=lambda x: x['date'], reverse=True)[:limit]
        else:
            trades = []
    
    # Calculate stats
    total_trades = len(trades)
    if total_trades > 0:
        # Filter completed trades with results
        completed = [t for t in trades if t.get('result') in ['win', 'loss']]
        wins = len([t for t in completed if t.get('result') == 'win'])
        win_rate = (wins / len(completed) * 100) if completed else 0
        
        avg_rr = sum([t.get('rr_ratio', 0) for t in trades if t.get('rr_ratio')]) / len([t for t in trades if t.get('rr_ratio')]) if [t for t in trades if t.get('rr_ratio')] else 0
        
        # Calculate current streak
        streak = 0
        for t in sorted(trades, key=lambda x: x.get('date', ''), reverse=True):
            if t.get('result') == 'win':
                streak += 1
            elif t.get('result') == 'loss':
                break
            else:
                break
    else:
        win_rate = 0
        avg_rr = 0
        streak = 0
    
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
        
        try:
            supabase.table('user_rules').upsert({'user_id': user_id, 'rules': rules}).execute()
        except:
            import json
            rules_file = f'trades_db/rules_{user_id}.json'
            with open(rules_file, 'w') as f:
                json.dump(rules, f)
        
        return jsonify({'success': True, 'rules': rules})
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

def get_user_rules(user_id):
    try:
        result = supabase.table('user_rules').select('rules').eq('user_id', user_id).execute()
        if result.data:
            return result.data[0]['rules']
    except:
        import json
        rules_file = f'trades_db/rules_{user_id}.json'
        if os.path.exists(rules_file):
            with open(rules_file, 'r') as f:
                return json.load(f)
    
    return {
        'max_daily_loss': 1000,
        'max_risk_per_trade': 2,
        'min_rr_ratio': 1.5,
        'max_trades_per_day': 5,
        'trades_today': 0,
        'daily_loss_today': 0
    }

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
            float(data.get('lot_size', 0))
        )
        
        ai_feedback = generate_ai_feedback(data, user_rules, risk_metrics)
        rr_ratio = calculate_rr_ratio(
            float(data['entry_price']),
            float(data['stop_loss']),
            float(data.get('take_profit')) if data.get('take_profit') else None,
            data['position_type']
        )
        
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

@app.route('/api/update-trade-result', methods=['POST'])
def update_trade_result():
    """Update a trade with win/loss result"""
    try:
        data = request.json
        trade_id = data['trade_id']
        result = data['result']  # 'win' or 'loss'
        
        try:
            supabase.table('trades').update({'result': result}).eq('id', trade_id).execute()
        except:
            # Update in local storage
            import json
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

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve(path):
    if path != "" and os.path.exists(os.path.join('build', path)):
        return send_from_directory('build', path)
    else:
        return send_from_directory('build', 'index.html')

if __name__ == '__main__':
    app.run(debug=True, port=5000)
