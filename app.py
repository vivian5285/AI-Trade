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
import logging

# 加载环境变量
load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-secret-key')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///trading.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# 初始化数据库
db = SQLAlchemy(app)

# API密钥模型
class APIKey(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    exchange = db.Column(db.String(20), nullable=False)  # LBank
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

# 确保实例文件夹存在
try:
    os.makedirs(app.instance_path)
except OSError:
    pass

# 创建数据库表
with app.app_context():
    db.create_all()
    
    # 检查是否需要添加默认API密钥
    if not APIKey.query.first():
        default_key = APIKey(
            exchange='LBank',
            api_key=os.getenv('BINANCE_API_KEY'),
            api_secret=os.getenv('BINANCE_API_SECRET'),
            is_active=True
        )
        db.session.add(default_key)
        db.session.commit()

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
    # 从.env文件加载设置
    settings = load_config()
    
    # 获取API密钥（只显示部分）
    binance_api_key = os.getenv('BINANCE_API_KEY', '')
    lbank_api_key = os.getenv('LBANK_API_KEY', '')
    
    # 获取当前选择的交易所
    current_exchange = os.getenv('CURRENT_EXCHANGE', 'binance')
    
    return render_template('settings.html', 
                         settings=settings,
                         binance_api_key=binance_api_key,
                         lbank_api_key=lbank_api_key,
                         current_exchange=current_exchange)

# 路由：保存基础设置
@app.route('/settings/basic', methods=['POST'])
def save_basic_settings():
    try:
        # 更新环境变量
        os.environ['TRADING_PAIR'] = request.form.get('trading_pair')
        os.environ['LEVERAGE'] = request.form.get('leverage')
        os.environ['QUANTITY'] = request.form.get('quantity')
        
        # 更新.env文件
        update_env_file({
            'TRADING_PAIR': request.form.get('trading_pair'),
            'LEVERAGE': request.form.get('leverage'),
            'QUANTITY': request.form.get('quantity')
        })
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

# 路由：保存策略设置
@app.route('/settings/strategy', methods=['POST'])
def save_strategy_settings():
    try:
        # 更新环境变量
        os.environ['TREND_EMA_FAST'] = request.form.get('trend_ema_fast')
        os.environ['TREND_EMA_SLOW'] = request.form.get('trend_ema_slow')
        os.environ['GRID_SIZE'] = request.form.get('grid_size')
        os.environ['GRID_SPACING'] = request.form.get('grid_spacing')
        os.environ['SCALPING_PROFIT_TARGET'] = request.form.get('scalping_profit_target')
        os.environ['SCALPING_STOP_LOSS'] = request.form.get('scalping_stop_loss')
        
        # 更新.env文件
        update_env_file({
            'TREND_EMA_FAST': request.form.get('trend_ema_fast'),
            'TREND_EMA_SLOW': request.form.get('trend_ema_slow'),
            'GRID_SIZE': request.form.get('grid_size'),
            'GRID_SPACING': request.form.get('grid_spacing'),
            'SCALPING_PROFIT_TARGET': request.form.get('scalping_profit_target'),
            'SCALPING_STOP_LOSS': request.form.get('scalping_stop_loss')
        })
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

# 路由：保存风险控制设置
@app.route('/settings/risk', methods=['POST'])
def save_risk_settings():
    try:
        # 更新环境变量
        os.environ['MAX_DAILY_TRADES'] = request.form.get('max_daily_trades')
        os.environ['MAX_DAILY_LOSS_PERCENTAGE'] = request.form.get('max_daily_loss')
        os.environ['MIN_VOLUME_THRESHOLD'] = request.form.get('min_volume')
        
        # 更新.env文件
        update_env_file({
            'MAX_DAILY_TRADES': request.form.get('max_daily_trades'),
            'MAX_DAILY_LOSS_PERCENTAGE': request.form.get('max_daily_loss'),
            'MIN_VOLUME_THRESHOLD': request.form.get('min_volume')
        })
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

# 路由：保存通知设置
@app.route('/settings/notification', methods=['POST'])
def save_notification_settings():
    try:
        # 更新环境变量
        os.environ['NOTIFICATION_EMAIL'] = request.form.get('email')
        os.environ['TELEGRAM_BOT_TOKEN'] = request.form.get('telegram')
        os.environ['EMAIL_NOTIFICATIONS'] = 'true' if request.form.get('email_notifications') else 'false'
        os.environ['TELEGRAM_NOTIFICATIONS'] = 'true' if request.form.get('telegram_notifications') else 'false'
        
        # 更新.env文件
        update_env_file({
            'NOTIFICATION_EMAIL': request.form.get('email'),
            'TELEGRAM_BOT_TOKEN': request.form.get('telegram'),
            'EMAIL_NOTIFICATIONS': 'true' if request.form.get('email_notifications') else 'false',
            'TELEGRAM_NOTIFICATIONS': 'true' if request.form.get('telegram_notifications') else 'false'
        })
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/settings/exchange', methods=['POST'])
def save_exchange_settings():
    try:
        exchange = request.form.get('exchange')
        logger.info(f"Received exchange selection: {exchange}")  # 添加日志
        
        if not exchange:
            return jsonify({'success': False, 'error': '未选择交易所'})
            
        if exchange not in ['binance', 'lbank']:
            return jsonify({'success': False, 'error': f'无效的交易所选择: {exchange}'})
            
        # 更新.env文件
        env_path = os.path.join(os.path.dirname(__file__), '.env')
        env_vars = {}
        
        # 读取现有的.env文件
        if os.path.exists(env_path):
            with open(env_path, 'r') as f:
                for line in f:
                    if '=' in line:
                        key, value = line.strip().split('=', 1)
                        env_vars[key] = value
        
        # 更新交易所选择
        env_vars['CURRENT_EXCHANGE'] = exchange
        
        # 写入.env文件
        with open(env_path, 'w') as f:
            for key, value in env_vars.items():
                f.write(f'{key}={value}\n')
        
        # 更新环境变量
        os.environ['CURRENT_EXCHANGE'] = exchange
        
        logger.info(f"Successfully saved exchange selection: {exchange}")  # 添加日志
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Error saving exchange settings: {str(e)}")  # 添加错误日志
        return jsonify({'success': False, 'error': str(e)})

def update_env_file(updates):
    """更新.env文件"""
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
    
    # 读取现有的.env文件
    if os.path.exists(env_path):
        with open(env_path, 'r') as f:
            lines = f.readlines()
    else:
        lines = []
    
    # 更新或添加新的环境变量
    new_lines = []
    updated_keys = set()
    
    for line in lines:
        key = line.split('=')[0].strip()
        if key in updates:
            new_lines.append(f"{key}={updates[key]}\n")
            updated_keys.add(key)
        else:
            new_lines.append(line)
    
    # 添加新的环境变量
    for key, value in updates.items():
        if key not in updated_keys:
            new_lines.append(f"{key}={value}\n")
    
    # 写入.env文件
    with open(env_path, 'w') as f:
        f.writelines(new_lines)

# API密钥验证函数
def validate_api_key(exchange, api_key, api_secret):
    try:
        timestamp = str(int(time.time() * 1000))
        params = {
            'api_key': api_key,
            'timestamp': timestamp
        }
        sign = generate_lbank_sign(params, api_secret)
        params['sign'] = sign
        
        response = requests.get('https://api.lbank.info/v2/user/account', params=params)
        data = response.json()
        
        return data.get('result', False)
    except Exception as e:
        print(f"API验证错误: {str(e)}")
        return False

# 加载配置
def load_config():
    config = {
        'lbank_api_key': os.getenv('BINANCE_API_KEY'),
        'lbank_api_secret': os.getenv('BINANCE_API_SECRET'),
        'trading_settings': {
            # 基础交易设置
            'trading_pair': os.getenv('TRADING_PAIR', 'ETHUSDT'),
            'leverage': os.getenv('LEVERAGE', '50'),
            'quantity': os.getenv('QUANTITY', '0.2'),
            
            # 高频交易策略参数
            'trend_ema_fast': os.getenv('TREND_EMA_FAST', '1'),  # 1分钟快速EMA
            'trend_ema_slow': os.getenv('TREND_EMA_SLOW', '3'),  # 3分钟慢速EMA
            'grid_size': os.getenv('GRID_SIZE', '50'),  # 网格数量
            'grid_spacing': os.getenv('GRID_SPACING', '0.05'),  # 网格间距0.05%
            'scalping_profit_target': os.getenv('SCALPING_PROFIT_TARGET', '0.1'),  # 0.1%止盈
            'scalping_stop_loss': os.getenv('SCALPING_STOP_LOSS', '0.05'),  # 0.05%止损
            
            # 风险控制参数
            'stop_loss': os.getenv('STOP_LOSS_PERCENTAGE', '0.2'),  # 0.2%止损
            'take_profit': os.getenv('TAKE_PROFIT_PERCENTAGE', '0.4'),  # 0.4%止盈
            'max_daily_trades': os.getenv('MAX_DAILY_TRADES', '500'),  # 每日最大交易次数
            'max_daily_loss': os.getenv('MAX_DAILY_LOSS_PERCENTAGE', '5'),  # 每日最大亏损5%
            'min_volume': os.getenv('MIN_VOLUME_THRESHOLD', '1000000'),  # 最小交易量100万USDT
            
            # 通知设置
            'notification_email': os.getenv('NOTIFICATION_EMAIL', ''),
            'telegram_bot_token': os.getenv('TELEGRAM_BOT_TOKEN', ''),
            'email_notifications': os.getenv('EMAIL_NOTIFICATIONS', 'false').lower() == 'true',
            'telegram_notifications': os.getenv('TELEGRAM_NOTIFICATIONS', 'false').lower() == 'true'
        }
    }
    return config

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
        print(f'获取LBank余额失败: {str(e)}')
        return None

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
        print(f'获取LBank交易记录失败: {str(e)}')
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