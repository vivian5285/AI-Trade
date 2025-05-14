from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
import os
from datetime import datetime
from dotenv import load_dotenv
import json
import pandas as pd
import plotly
import plotly.graph_objs as go
from binance.client import Client
import requests
import hmac
import hashlib
import time

# 加载环境变量
load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-secret-key')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///trading.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# 初始化数据库
db = SQLAlchemy(app)

# 确保实例文件夹存在
try:
    os.makedirs(app.instance_path)
except OSError:
    pass

# 确保数据库文件存在
with app.app_context():
    db.create_all()

# API密钥模型
class APIKey(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    exchange = db.Column(db.String(20), nullable=False)  # MT4, Binance, LBank
    api_key = db.Column(db.String(100), nullable=False)
    api_secret = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)

# 交易历史模型
class TradeHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    exchange = db.Column(db.String(20), nullable=False)
    symbol = db.Column(db.String(20), nullable=False)
    side = db.Column(db.String(10), nullable=False)  # BUY, SELL
    price = db.Column(db.Float, nullable=False)
    quantity = db.Column(db.Float, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), nullable=False)  # OPEN, CLOSED, CANCELLED

# 路由：首页/仪表盘
@app.route('/')
def dashboard():
    api_keys = APIKey.query.all()
    trades = TradeHistory.query.order_by(TradeHistory.timestamp.desc()).limit(10).all()
    return render_template('dashboard.html', api_keys=api_keys, trades=trades)

# 路由：API密钥管理
@app.route('/api-keys', methods=['GET', 'POST'])
def api_keys():
    if request.method == 'POST':
        exchange = request.form.get('exchange')
        api_key = request.form.get('api_key')
        api_secret = request.form.get('api_secret')
        
        # 验证API密钥
        if not validate_api_key(exchange, api_key, api_secret):
            flash('无效的API凭证')
            return redirect(url_for('api_keys'))
            
        new_key = APIKey(
            exchange=exchange,
            api_key=api_key,
            api_secret=api_secret
        )
        db.session.add(new_key)
        db.session.commit()
        flash('API密钥添加成功')
        
    api_keys = APIKey.query.all()
    return render_template('api_keys.html', api_keys=api_keys)

# 路由：交易历史
@app.route('/trades')
def trades():
    trades = TradeHistory.query.order_by(TradeHistory.timestamp.desc()).all()
    return render_template('trades.html', trades=trades)

# 路由：设置
@app.route('/settings')
def settings():
    return render_template('settings.html')

# API密钥验证函数
def validate_api_key(exchange, api_key, api_secret):
    # TODO: 实现实际的API密钥验证逻辑
    return True

# 加载配置
def load_config():
    if os.path.exists('config.json'):
        with open('config.json', 'r') as f:
            return json.load(f)
    return {
        'binance_api_key': '',
        'binance_api_secret': '',
        'lbank_api_key': '',
        'lbank_api_secret': '',
        'trading_settings': {
            'trading_pair': 'BTC-USDT',
            'leverage': '10',
            'quantity': '0.001',
            'stop_loss': '0.3',
            'take_profit': '0.6'
        }
    }

def save_config(config):
    with open('config.json', 'w') as f:
        json.dump(config, f, indent=4)

# API函数
def get_binance_balance(config):
    try:
        client = Client(config['binance_api_key'], config['binance_api_secret'])
        account = client.futures_account_balance()
        return {balance['asset']: float(balance['balance']) for balance in account}
    except Exception as e:
        flash(f'获取Binance余额失败: {str(e)}')
        return None

def get_lbank_balance(config):
    try:
        timestamp = str(int(time.time() * 1000))
        params = {
            'api_key': config['lbank_api_key'],
            'timestamp': timestamp
        }
        sign = generate_lbank_sign(params, config['lbank_api_secret'])
        params['sign'] = sign
        
        response = requests.get('https://api.lbank.info/v2/user/account', params=params)
        data = response.json()
        
        if data['result']:
            return {balance['asset']: float(balance['balance']) for balance in data['data']}
        return None
    except Exception as e:
        flash(f'获取LBank余额失败: {str(e)}')
        return None

def get_binance_trades(config):
    try:
        client = Client(config['binance_api_key'], config['binance_api_secret'])
        trades = client.futures_account_trades()
        return trades
    except Exception as e:
        flash(f'获取Binance交易记录失败: {str(e)}')
        return []

def get_lbank_trades(config):
    try:
        timestamp = str(int(time.time() * 1000))
        params = {
            'api_key': config['lbank_api_key'],
            'timestamp': timestamp
        }
        sign = generate_lbank_sign(params, config['lbank_api_secret'])
        params['sign'] = sign
        
        response = requests.get('https://api.lbank.info/v2/order_history', params=params)
        data = response.json()
        
        if data['result']:
            return data['data']
        return []
    except Exception as e:
        flash(f'获取LBank交易记录失败: {str(e)}')
        return []

def generate_lbank_sign(params, api_secret):
    sorted_params = sorted(params.items(), key=lambda x: x[0])
    sign_str = '&'.join([f"{k}={v}" for k, v in sorted_params])
    return hmac.new(
        api_secret.encode(),
        sign_str.encode(),
        hashlib.sha256
    ).hexdigest()

def create_balance_chart(trades):
    if not trades:
        return None
        
    df = pd.DataFrame(trades)
    df['timestamp'] = pd.to_datetime(df['time'], unit='ms')
    df['balance'] = df['realizedPnl'].cumsum()
    
    trace = go.Scatter(
        x=df['timestamp'],
        y=df['balance'],
        mode='lines',
        name='余额'
    )
    
    layout = go.Layout(
        title='账户余额变化',
        xaxis={'title': '时间'},
        yaxis={'title': '余额 (USDT)'}
    )
    
    fig = go.Figure(data=[trace], layout=layout)
    return json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)

# API路由：市场数据
@app.route('/api/market-data')
def market_data():
    try:
        # 获取Binance行情数据
        client = Client()
        btc_ticker = client.get_symbol_ticker(symbol='BTCUSDT')
        eth_ticker = client.get_symbol_ticker(symbol='ETHUSDT')
        
        # 获取24小时价格变化
        btc_24h = client.get_ticker(symbol='BTCUSDT')
        eth_24h = client.get_ticker(symbol='ETHUSDT')
        
        return jsonify({
            'btc': {
                'price': f"{float(btc_ticker['price']):,.2f}",
                'change': f"{float(btc_24h['priceChangePercent']):.2f}"
            },
            'eth': {
                'price': f"{float(eth_ticker['price']):,.2f}",
                'change': f"{float(eth_24h['priceChangePercent']):.2f}"
            }
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# API路由：账户数据
@app.route('/api/account-data')
def account_data():
    try:
        config = load_config()
        total_balance = 0
        daily_pnl = 0
        open_positions = 0
        total_position = 0
        
        # 获取Binance账户数据
        if config['binance_api_key'] and config['binance_api_secret']:
            client = Client(config['binance_api_key'], config['binance_api_secret'])
            account = client.futures_account()
            positions = client.futures_position_information()
            
            # 计算总余额
            for asset in account['assets']:
                if asset['asset'] == 'USDT':
                    total_balance += float(asset['walletBalance'])
                    daily_pnl += float(asset['unrealizedProfit'])
            
            # 计算持仓
            for position in positions:
                if float(position['positionAmt']) != 0:
                    open_positions += 1
                    total_position += abs(float(position['positionAmt']) * float(position['entryPrice']))
        
        return jsonify({
            'balance': f"{total_balance:,.2f}",
            'daily_pnl': f"{daily_pnl:,.2f}",
            'open_positions': open_positions,
            'total_position': f"{total_position:,.2f}"
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# API路由：图表数据
@app.route('/api/chart-data')
def chart_data():
    try:
        config = load_config()
        equity_data = []
        trade_stats = {
            'labels': ['盈利', '亏损', '平局'],
            'values': [0, 0, 0]
        }
        
        # 获取Binance交易数据
        if config['binance_api_key'] and config['binance_api_secret']:
            client = Client(config['binance_api_key'], config['binance_api_secret'])
            trades = client.futures_account_trades()
            
            # 处理交易数据
            balance = 0
            for trade in trades:
                balance += float(trade['realizedPnl'])
                equity_data.append({
                    'timestamp': trade['time'],
                    'value': balance
                })
                
                # 统计交易结果
                if float(trade['realizedPnl']) > 0:
                    trade_stats['values'][0] += 1
                elif float(trade['realizedPnl']) < 0:
                    trade_stats['values'][1] += 1
                else:
                    trade_stats['values'][2] += 1
        
        return jsonify({
            'equity': {
                'timestamps': [t['timestamp'] for t in equity_data],
                'values': [t['value'] for t in equity_data]
            },
            'stats': trade_stats
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# API路由：获取单个API密钥
@app.route('/api/keys/<int:key_id>', methods=['GET'])
def get_api_key(key_id):
    try:
        key = APIKey.query.get_or_404(key_id)
        return jsonify({
            'id': key.id,
            'exchange': key.exchange,
            'api_key': key.api_key,
            'api_secret': key.api_secret
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# API路由：更新API密钥
@app.route('/api/keys/<int:key_id>', methods=['PUT'])
def update_api_key(key_id):
    try:
        key = APIKey.query.get_or_404(key_id)
        data = request.get_json()
        
        # 验证API密钥
        if not validate_api_key(key.exchange, data['api_key'], data['api_secret']):
            return jsonify({'error': '无效的API凭证'}), 400
            
        key.api_key = data['api_key']
        key.api_secret = data['api_secret']
        db.session.commit()
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# API路由：删除API密钥
@app.route('/api/keys/<int:key_id>', methods=['DELETE'])
def delete_api_key(key_id):
    try:
        key = APIKey.query.get_or_404(key_id)
        db.session.delete(key)
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# API路由：切换API密钥状态
@app.route('/api/keys/<int:key_id>/toggle', methods=['POST'])
def toggle_api_key(key_id):
    try:
        key = APIKey.query.get_or_404(key_id)
        key.is_active = not key.is_active
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True) 