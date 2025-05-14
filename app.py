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
import subprocess
import signal
from functools import lru_cache

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

# 配置日志记录
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('app.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# 创建数据库表
try:
    with app.app_context():
        db.create_all()
        
        # 检查是否需要添加默认API密钥
        if not APIKey.query.first():
            # 获取环境变量
            binance_api_key = os.getenv('BINANCE_API_KEY')
            binance_api_secret = os.getenv('BINANCE_API_SECRET')
            lbank_api_key = os.getenv('LBANK_API_KEY')
            lbank_api_secret = os.getenv('LBANK_API_SECRET')
            
            if not all([binance_api_key, binance_api_secret, lbank_api_key, lbank_api_secret]):
                logger.warning("Some API keys are missing in .env file")
            
            # 添加Binance默认密钥
            binance_key = APIKey(
                exchange='Binance',
                api_key=binance_api_key or '',
                api_secret=binance_api_secret or '',
                is_active=True
            )
            db.session.add(binance_key)
            
            # 添加LBank默认密钥
            lbank_key = APIKey(
                exchange='LBank',
                api_key=lbank_api_key or '',
                api_secret=lbank_api_secret or '',
                is_active=True
            )
            db.session.add(lbank_key)
            
            try:
                db.session.commit()
                logger.info("Successfully initialized database with API keys")
            except Exception as e:
                logger.error(f"Error initializing database: {str(e)}")
                db.session.rollback()
except Exception as e:
    logger.error(f"Error during database initialization: {str(e)}")

# 添加全局变量来跟踪交易机器人进程
trading_bot_process = None

# 交易机器人状态管理
trading_bot_running = False

# 路由：首页/仪表盘
@app.route('/')
def dashboard():
    try:
        api_keys = APIKey.query.all()
        trades = TradeHistory.query.order_by(TradeHistory.timestamp.desc()).limit(10).all()
        return render_template('dashboard.html', api_keys=api_keys, trades=trades)
    except Exception as e:
        logger.error(f"Error in dashboard route: {str(e)}")
        return render_template('error.html', error=str(e)), 500

# 路由：API密钥管理
@app.route('/api-keys', methods=['GET', 'POST'])
def api_keys():
    try:
        if request.method == 'POST':
            data = request.get_json()
            if not data:
                return jsonify({'success': False, 'error': '无效的请求数据'}), 400
                
            exchange = data.get('exchange')
            api_key = data.get('api_key')
            api_secret = data.get('api_secret')
            
            if not all([exchange, api_key, api_secret]):
                return jsonify({'success': False, 'error': '请填写所有必填字段'}), 400
            
            # 验证API密钥
            if not validate_api_key(exchange, api_key, api_secret):
                return jsonify({'success': False, 'error': '无效的API凭证'}), 400
                
            new_key = APIKey(
                exchange=exchange,
                api_key=api_key,
                api_secret=api_secret
            )
            db.session.add(new_key)
            db.session.commit()
            return jsonify({'success': True, 'message': 'API密钥添加成功'})
            
        api_keys = APIKey.query.all()
        return render_template('api_keys.html', api_keys=api_keys)
    except Exception as e:
        logger.error(f"Error in api_keys route: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

# 路由：交易历史
@app.route('/trades')
def trades():
    trades = TradeHistory.query.order_by(TradeHistory.timestamp.desc()).all()
    return render_template('trades.html', trades=trades)

# 路由：设置
@app.route('/settings')
def settings():
    try:
        # 获取当前设置
        current_settings = {
            'current_exchange': os.getenv('CURRENT_EXCHANGE', 'binance'),
            'scalpingEnabled': os.getenv('SCALPING_ENABLED', 'false'),
            'supertrendEnabled': os.getenv('SUPERTREND_ENABLED', 'false'),
            'rsiEnabled': os.getenv('RSI_ENABLED', 'false'),
            'bbEnabled': os.getenv('BB_ENABLED', 'false'),
            'tradingPair': os.getenv('TRADING_PAIR', 'BTCUSDT'),
            'leverage': os.getenv('LEVERAGE', '10'),
            'quantity': os.getenv('QUANTITY', '0.001'),
            'stopLoss': os.getenv('STOP_LOSS_PERCENTAGE', '0.3'),
            'takeProfit': os.getenv('TAKE_PROFIT_PERCENTAGE', '0.6'),
            'maxDailyTrades': os.getenv('MAX_DAILY_TRADES', '100')
        }
        
        # 获取API密钥信息
        binance_key = APIKey.query.filter_by(exchange='Binance').first()
        lbank_key = APIKey.query.filter_by(exchange='LBank').first()
        
        binance_api_key = binance_key.api_key if binance_key else ''
        lbank_api_key = lbank_key.api_key if lbank_key else ''
        
        return render_template('settings.html', 
                             settings=current_settings,
                             binance_api_key=binance_api_key,
                             lbank_api_key=lbank_api_key)
    except Exception as e:
        logger.error(f"Error in settings route: {str(e)}")
        return render_template('error.html', error=str(e)), 500

@app.route('/api/settings', methods=['GET', 'POST'])
def handle_settings():
    try:
        if request.method == 'GET':
            # 获取当前设置
            current_settings = {
                'current_exchange': os.getenv('CURRENT_EXCHANGE', 'binance'),
                'scalpingEnabled': os.getenv('SCALPING_ENABLED', 'false'),
                'supertrendEnabled': os.getenv('SUPERTREND_ENABLED', 'false'),
                'rsiEnabled': os.getenv('RSI_ENABLED', 'false'),
                'bbEnabled': os.getenv('BB_ENABLED', 'false'),
                'tradingPair': os.getenv('TRADING_PAIR', 'BTCUSDT'),
                'leverage': os.getenv('LEVERAGE', '10'),
                'quantity': os.getenv('QUANTITY', '0.001'),
                'stopLoss': os.getenv('STOP_LOSS_PERCENTAGE', '0.3'),
                'takeProfit': os.getenv('TAKE_PROFIT_PERCENTAGE', '0.6'),
                'maxDailyTrades': os.getenv('MAX_DAILY_TRADES', '100')
            }
            return jsonify({'success': True, **current_settings})
            
        elif request.method == 'POST':
            data = request.get_json()
            if not data:
                return jsonify({'success': False, 'error': '无效的请求数据'}), 400
                
            # 更新环境变量
            env_file = '.env'
            env_vars = {}
            
            # 读取现有的环境变量
            if os.path.exists(env_file):
                with open(env_file, 'r') as f:
                    for line in f:
                        if '=' in line:
                            key, value = line.strip().split('=', 1)
                            env_vars[key] = value
            
            # 更新环境变量
            for key, value in data.items():
                if key in ['current_exchange', 'scalpingEnabled', 'supertrendEnabled', 
                          'rsiEnabled', 'bbEnabled', 'tradingPair', 'leverage', 
                          'quantity', 'stopLoss', 'takeProfit', 'maxDailyTrades']:
                    env_vars[key.upper()] = str(value)
            
            # 写入环境变量文件
            with open(env_file, 'w') as f:
                for key, value in env_vars.items():
                    f.write(f"{key}={value}\n")
            
            # 重新加载环境变量
            load_dotenv(override=True)
            
            return jsonify({
                'success': True,
                'message': '设置已更新'
            })
            
    except Exception as e:
        logger.error(f"Error in handle_settings: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# API密钥验证函数
def validate_api_key(exchange, api_key, api_secret):
    try:
        if exchange.lower() == 'binance':
            client = Client(api_key, api_secret)
            # 测试API连接
            client.get_account()
            return True
        elif exchange.lower() == 'lbank':
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
        return False
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

# 路由：获取市场数据
@app.route('/api/market-data')
def get_market_data():
    try:
        # 获取当前交易所
        current_exchange = os.getenv('CURRENT_EXCHANGE', 'Binance')
        
        if current_exchange == 'Binance':
            # 获取Binance API密钥
            api_key = APIKey.query.filter_by(exchange='Binance', is_active=True).first()
            if not api_key:
                return jsonify({'error': 'No active Binance API key found'}), 401
            
            # 初始化Binance客户端
            client = Client(api_key.api_key, api_key.api_secret)
            
            # 获取BTC/USDT和ETH/USDT的24小时行情
            btc_ticker = client.get_ticker(symbol='BTCUSDT')
            eth_ticker = client.get_ticker(symbol='ETHUSDT')
            
            # 获取K线数据
            btc_klines = client.get_klines(
                symbol='BTCUSDT',
                interval=Client.KLINE_INTERVAL_1MINUTE,
                limit=100
            )
            eth_klines = client.get_klines(
                symbol='ETHUSDT',
                interval=Client.KLINE_INTERVAL_1MINUTE,
                limit=100
            )
            
            # 处理K线数据
            def process_klines(klines):
                return [{
                    'time': k[0] // 1000,  # 转换为秒级时间戳
                    'open': float(k[1]),
                    'high': float(k[2]),
                    'low': float(k[3]),
                    'close': float(k[4]),
                    'volume': float(k[5])
                } for k in klines]
            
            return jsonify({
                'btc': {
                    'price': float(btc_ticker['lastPrice']),
                    'change_24h': float(btc_ticker['priceChangePercent']),
                    'klines': process_klines(btc_klines)
                },
                'eth': {
                    'price': float(eth_ticker['lastPrice']),
                    'change_24h': float(eth_ticker['priceChangePercent']),
                    'klines': process_klines(eth_klines)
                }
            })
            
        elif current_exchange == 'LBank':
            # LBank的现有代码保持不变
            api_key = APIKey.query.filter_by(exchange='LBank', is_active=True).first()
            if not api_key:
                return jsonify({'error': 'No active LBank API key found'}), 401
            
            headers = {
                'api_key': api_key.api_key,
                'secret_key': api_key.api_secret
            }
            
            # 获取BTC/USDT和ETH/USDT的行情
            btc_response = requests.get('https://api.lbank.info/v2/ticker.do?symbol=btc_usdt', headers=headers)
            eth_response = requests.get('https://api.lbank.info/v2/ticker.do?symbol=eth_usdt', headers=headers)
            
            if btc_response.status_code == 200 and eth_response.status_code == 200:
                btc_data = btc_response.json()['data'][0]
                eth_data = eth_response.json()['data'][0]
                
                return jsonify({
                    'btc': {
                        'price': float(btc_data['ticker']['latest']),
                        'change_24h': float(btc_data['ticker']['change'])
                    },
                    'eth': {
                        'price': float(eth_data['ticker']['latest']),
                        'change_24h': float(eth_data['ticker']['change'])
                    }
                })
            else:
                return jsonify({'error': 'Failed to fetch LBank data'}), 500
                
    except Exception as e:
        app.logger.error(f"Error fetching market data: {str(e)}")
        return jsonify({'error': str(e)}), 500

# 路由：获取账户数据
@app.route('/api/account-data')
def get_account_data():
    try:
        # 获取当前交易所
        current_exchange = os.getenv('CURRENT_EXCHANGE', 'Binance')
        
        if current_exchange == 'Binance':
            # 获取Binance API密钥
            api_key = APIKey.query.filter_by(exchange='Binance', is_active=True).first()
            if not api_key:
                return jsonify({'error': 'No active Binance API key found'}), 401
            
            # 初始化Binance客户端
            client = Client(api_key.api_key, api_key.api_secret)
            
            # 获取账户信息
            account = client.get_account()
            
            # 计算总余额
            total_balance = 0
            positions = []
            
            for asset in account['balances']:
                free = float(asset['free'])
                locked = float(asset['locked'])
                if free > 0 or locked > 0:
                    # 获取USDT价格
                    if asset['asset'] != 'USDT':
                        try:
                            ticker = client.get_symbol_ticker(symbol=f"{asset['asset']}USDT")
                            price = float(ticker['price'])
                        except:
                            price = 0
                    else:
                        price = 1
                    
                    value = (free + locked) * price
                    total_balance += value
                    
                    if free > 0 or locked > 0:
                        positions.append({
                            'asset': asset['asset'],
                            'free': free,
                            'locked': locked,
                            'value': value
                        })
            
            # 获取今日盈亏（这里需要实现具体的盈亏计算逻辑）
            daily_pnl = 0  # 需要实现
            
            return jsonify({
                'total_balance': total_balance,
                'daily_pnl': daily_pnl,
                'positions': positions
            })
            
        elif current_exchange == 'LBank':
            # LBank的现有代码保持不变
            api_key = APIKey.query.filter_by(exchange='LBank', is_active=True).first()
            if not api_key:
                return jsonify({'error': 'No active LBank API key found'}), 401
            
            headers = {
                'api_key': api_key.api_key,
                'secret_key': api_key.api_secret
            }
            
            # 获取账户信息
            response = requests.get('https://api.lbank.info/v2/user_info.do', headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                if data['result']:
                    account_data = data['data']
                    return jsonify({
                        'total_balance': float(account_data['total_asset']),
                        'daily_pnl': float(account_data['today_profit']),
                        'positions': account_data['free']
                    })
                else:
                    return jsonify({'error': 'Failed to get LBank account data'}), 500
            else:
                return jsonify({'error': 'Failed to fetch LBank data'}), 500
                
    except Exception as e:
        app.logger.error(f"Error fetching account data: {str(e)}")
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

# API密钥管理路由
@app.route('/api/keys/<int:key_id>', methods=['GET'])
def get_api_key(key_id):
    try:
        key = APIKey.query.get_or_404(key_id)
        return jsonify({
            'success': True,
            'exchange': key.exchange,
            'api_key': key.api_key,
            'api_secret': key.api_secret
        })
    except Exception as e:
        logger.error(f"Error getting API key: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/keys/<int:key_id>', methods=['PUT'])
def update_api_key(key_id):
    try:
        key = APIKey.query.get_or_404(key_id)
        data = request.get_json()
        
        if not data:
            return jsonify({'success': False, 'error': '无效的请求数据'}), 400
            
        # 验证API密钥
        if not validate_api_key(data['exchange'], data['api_key'], data['api_secret']):
            return jsonify({'success': False, 'error': '无效的API凭证'}), 400
        
        key.exchange = data['exchange']
        key.api_key = data['api_key']
        key.api_secret = data['api_secret']
        
        db.session.commit()
        return jsonify({
            'success': True,
            'message': 'API密钥已更新'
        })
    except Exception as e:
        logger.error(f"Error updating API key: {str(e)}")
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/keys/<int:key_id>/toggle', methods=['POST'])
def toggle_api_key(key_id):
    try:
        key = APIKey.query.get_or_404(key_id)
        key.is_active = not key.is_active
        db.session.commit()
        return jsonify({
            'success': True,
            'message': 'API密钥状态已更新'
        })
    except Exception as e:
        logger.error(f"Error toggling API key: {str(e)}")
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/keys/<int:key_id>', methods=['DELETE'])
def delete_api_key(key_id):
    try:
        key = APIKey.query.get_or_404(key_id)
        db.session.delete(key)
        db.session.commit()
        return jsonify({
            'success': True,
            'message': 'API密钥已删除'
        })
    except Exception as e:
        logger.error(f"Error deleting API key: {str(e)}")
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/settings', methods=['GET'])
def get_settings():
    try:
        # 从.env文件加载设置
        settings = load_config()
        
        # 获取当前选择的交易所
        current_exchange = os.getenv('CURRENT_EXCHANGE', 'binance')
        
        # 获取策略启用状态
        settings['trading_settings'].update({
            'exchange': current_exchange,
            'scalpingEnabled': os.getenv('SCALPING_ENABLED', 'false'),
            'supertrendEnabled': os.getenv('SUPERTREND_ENABLED', 'false'),
            'rsiEnabled': os.getenv('RSI_ENABLED', 'false'),
            'bbEnabled': os.getenv('BB_ENABLED', 'false'),
            'ichimokuEnabled': os.getenv('ICHIMOKU_ENABLED', 'false'),
            'vwapEnabled': os.getenv('VWAP_ENABLED', 'false')
        })
        
        return jsonify(settings['trading_settings'])
    except Exception as e:
        logger.error(f"Error getting settings: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/trading-bot')
def trading_bot():
    try:
        # 获取当前策略设置
        settings = {
            'rsi_period': int(os.getenv('RSI_PERIOD', 14)),
            'rsi_overbought': int(os.getenv('RSI_OVERBOUGHT', 70)),
            'rsi_oversold': int(os.getenv('RSI_OVERSOLD', 30)),
            'bb_period': int(os.getenv('BB_PERIOD', 20)),
            'bb_std': float(os.getenv('BB_STD', 2.0)),
            'supertrend_atr_period': int(os.getenv('SUPERTREND_ATR_PERIOD', 10)),
            'supertrend_atr_multiplier': float(os.getenv('SUPERTREND_ATR_MULTIPLIER', 3.0)),
            'grid_count': int(os.getenv('GRID_COUNT', 10)),
            'grid_spacing': float(os.getenv('GRID_SPACING', 1.0))
        }
        
        # 获取最近的交易记录
        trades = TradeHistory.query.order_by(TradeHistory.timestamp.desc()).limit(50).all()
        
        return render_template('trading_bot.html', settings=settings, trades=trades)
    except Exception as e:
        logger.error(f"Error loading trading bot page: {str(e)}")
        return render_template('error.html', error="加载交易机器人页面时出错")

@app.route('/api/trading-bot/status')
def get_bot_status():
    return jsonify({
        'success': True,
        'is_running': trading_bot_running
    })

@app.route('/api/trading-bot/start', methods=['POST'])
def start_trading_bot():
    global trading_bot_running
    try:
        if trading_bot_running:
            return jsonify({
                'success': False,
                'error': '交易机器人已经在运行中'
            })
        
        # 启动交易机器人的逻辑
        trading_bot_running = True
        logger.info("交易机器人已启动")
        
        return jsonify({
            'success': True,
            'message': '交易机器人已启动'
        })
    except Exception as e:
        logger.error(f"Error starting trading bot: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/api/trading-bot/stop', methods=['POST'])
def stop_trading_bot():
    global trading_bot_running
    try:
        if not trading_bot_running:
            return jsonify({
                'success': False,
                'error': '交易机器人已经停止'
            })
        
        # 停止交易机器人的逻辑
        trading_bot_running = False
        logger.info("交易机器人已停止")
        
        return jsonify({
            'success': True,
            'message': '交易机器人已停止'
        })
    except Exception as e:
        logger.error(f"Error stopping trading bot: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/api/trading-bot/restart', methods=['POST'])
def restart_trading_bot():
    try:
        # 先停止
        stop_trading_bot()
        # 再启动
        return start_trading_bot()
    except Exception as e:
        logger.error(f"Error restarting trading bot: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/api/trading-bot/logs')
def get_bot_logs():
    try:
        # 读取最近的日志
        log_file = 'app.log'
        if not os.path.exists(log_file):
            return jsonify({
                'success': False,
                'error': '日志文件不存在'
            })
        
        # 读取最后100行日志
        with open(log_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            last_lines = lines[-100:] if len(lines) > 100 else lines
        
        # 解析日志
        logs = []
        for line in last_lines:
            try:
                # 假设日志格式为: [时间戳] 级别: 消息
                parts = line.split('] ', 1)
                if len(parts) == 2:
                    timestamp = parts[0].strip('[')
                    message = parts[1].strip()
                    logs.append({
                        'timestamp': timestamp,
                        'message': message
                    })
            except:
                continue
        
        return jsonify({
            'success': True,
            'logs': logs
        })
    except Exception as e:
        logger.error(f"Error getting bot logs: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        })

# 资金管理和风险控制
def calculate_position_size(balance, symbol, exchange='Binance'):
    try:
        # 获取当前价格
        if exchange == 'Binance':
            client = get_binance_client()
            ticker = client.get_ticker(symbol=symbol)
            current_price = float(ticker['lastPrice'])
        elif exchange == 'LBank':
            response = requests.get(f'https://api.lbank.info/v2/ticker.do?symbol={symbol.lower()}')
            data = response.json()
            if data['result']:
                current_price = float(data['data'][0]['ticker']['latest'])
            else:
                raise Exception("Failed to get LBank ticker data")
        
        # 风险控制参数
        max_risk_per_trade = 0.02  # 单笔交易最大风险（总资金的2%）
        max_total_risk = 0.1  # 总持仓最大风险（总资金的10%）
        min_position_size = 10  # 最小仓位（USDT）
        max_position_size = balance * 0.5  # 最大仓位（总资金的50%）
        
        # 获取当前持仓
        if exchange == 'Binance':
            positions = client.futures_position_information()
            current_positions = sum(abs(float(pos['positionAmt']) * float(pos['entryPrice'])) 
                                 for pos in positions if float(pos['positionAmt']) != 0)
        elif exchange == 'LBank':
            api_key = APIKey.query.filter_by(exchange='LBank', is_active=True).first()
            if not api_key:
                raise Exception("No active LBank API key found")
                
            timestamp = str(int(time.time() * 1000))
            params = {
                'api_key': api_key.api_key,
                'timestamp': timestamp
            }
            sign = generate_lbank_sign(params, api_key.api_secret)
            params['sign'] = sign
            
            response = requests.get('https://api.lbank.info/v2/user/positions', params=params)
            positions = response.json()
            
            if not positions['result']:
                raise Exception("Failed to get LBank positions")
                
            current_positions = sum(float(pos['positionValue']) for pos in positions['data'])
        
        # 计算可用风险额度
        available_risk = balance * max_total_risk - current_positions
        
        # 如果可用风险额度小于最小仓位，返回None
        if available_risk < min_position_size:
            logger.warning(f"Available risk ({available_risk} USDT) is less than minimum position size ({min_position_size} USDT)")
            return None
            
        # 计算建议仓位大小
        suggested_position = min(
            max(min_position_size, balance * max_risk_per_trade),  # 单笔交易风险限制
            max_position_size,  # 最大仓位限制
            available_risk  # 可用风险额度限制
        )
        
        # 根据价格计算数量
        quantity = suggested_position / current_price
        
        # 获取交易对精度
        if exchange == 'Binance':
            exchange_info = client.get_exchange_info()
            symbol_info = next((s for s in exchange_info['symbols'] if s['symbol'] == symbol), None)
            if symbol_info:
                quantity_precision = next((f['stepSize'] for f in symbol_info['filters'] if f['filterType'] == 'LOT_SIZE'), '0.00001')
                quantity_precision = len(str(float(quantity_precision)).rstrip('0').split('.')[-1])
                quantity = round(quantity, quantity_precision)
        elif exchange == 'LBank':
            # LBank通常使用8位小数
            quantity = round(quantity, 8)
            
        return {
            'position_size': suggested_position,
            'quantity': quantity,
            'current_price': current_price,
            'available_risk': available_risk,
            'current_positions': current_positions
        }
    except Exception as e:
        logger.error(f"Error calculating position size: {str(e)}")
        return None

# 添加K线数据缓存
@lru_cache(maxsize=100)
def get_cached_klines(symbol, timeframe, timestamp):
    try:
        current_exchange = os.getenv('CURRENT_EXCHANGE', 'Binance')
        if current_exchange == 'Binance':
            client = get_binance_client()
            klines = client.get_klines(symbol=symbol, interval=timeframe, limit=100)
            df = pd.DataFrame(klines, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'close_time', 'quote_volume', 'trades', 'taker_buy_base', 'taker_buy_quote', 'ignore'])
        elif current_exchange == 'LBank':
            response = requests.get(f'https://api.lbank.info/v2/kline.do?symbol={symbol.lower()}&size=100&type={timeframe}')
            data = response.json()
            if data['result']:
                df = pd.DataFrame(data['data'], columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            else:
                raise Exception("Failed to get LBank kline data")
        
        # 转换数据类型
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df['open'] = df['open'].astype(float)
        df['high'] = df['high'].astype(float)
        df['low'] = df['low'].astype(float)
        df['close'] = df['close'].astype(float)
        df['volume'] = df['volume'].astype(float)
        
        return df.to_dict('records')
    except Exception as e:
        logger.error(f"Error getting cached klines: {str(e)}")
        return None

# 添加K线数据API路由
@app.route('/api/kline-data')
def get_kline_data():
    try:
        symbol = request.args.get('symbol', 'BTCUSDT')
        timeframe = request.args.get('timeframe', '1m')
        
        # 获取当前时间戳（每分钟更新一次）
        current_timestamp = int(time.time() / 60)
        
        # 获取K线数据
        klines = get_cached_klines(symbol, timeframe, current_timestamp)
        
        if klines:
            return jsonify({
                'success': True,
                'data': klines
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to get kline data'
            }), 500
    except Exception as e:
        logger.error(f"Error getting kline data: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# 修改策略检查函数，使用缓存的K线数据
def check_strategy_conditions(symbol, timeframe='1m'):
    try:
        # 获取当前时间戳（每分钟更新一次）
        current_timestamp = int(time.time() / 60)
        
        # 获取K线数据
        klines = get_cached_klines(symbol, timeframe, current_timestamp)
        if not klines:
            return None
            
        df = pd.DataFrame(klines)
        
        # 获取当前启用的策略
        enabled_strategies = []
        if os.getenv('SCALPING_ENABLED', 'false').lower() == 'true':
            enabled_strategies.append('scalping')
        if os.getenv('SUPERTREND_ENABLED', 'false').lower() == 'true':
            enabled_strategies.append('supertrend')
        if os.getenv('RSI_ENABLED', 'false').lower() == 'true':
            enabled_strategies.append('rsi')
        if os.getenv('BB_ENABLED', 'false').lower() == 'true':
            enabled_strategies.append('bollinger_bands')
            
        if not enabled_strategies:
            logger.warning("No trading strategies are enabled")
            return None
            
        # 获取账户余额
        current_exchange = os.getenv('CURRENT_EXCHANGE', 'Binance')
        if current_exchange == 'Binance':
            client = get_binance_client()
            account = client.get_account()
            balance = float([asset for asset in account['balances'] if asset['asset'] == 'USDT'][0]['free'])
        elif current_exchange == 'LBank':
            api_key = APIKey.query.filter_by(exchange='LBank', is_active=True).first()
            if not api_key:
                raise Exception("No active LBank API key found")
                
            timestamp = str(int(time.time() * 1000))
            params = {
                'api_key': api_key.api_key,
                'timestamp': timestamp
            }
            sign = generate_lbank_sign(params, api_key.api_secret)
            params['sign'] = sign
            
            response = requests.get('https://api.lbank.info/v2/user/account', params=params)
            account = response.json()
            
            if not account['result']:
                raise Exception("Failed to get LBank account info")
                
            balance = float([asset for asset in account['data'] if asset['asset'] == 'usdt'][0]['free'])
        
        # 计算建议仓位
        position_info = calculate_position_size(balance, symbol, current_exchange)
        if not position_info:
            logger.warning("Cannot calculate position size, skipping trade")
            return None
            
        # 初始化信号字典
        signals = {}
        
        # 检查每个启用的策略
        for strategy in enabled_strategies:
            if strategy == 'scalping':
                signals['scalping'] = check_scalping_strategy(df)
            elif strategy == 'supertrend':
                signals['supertrend'] = check_supertrend_strategy(df)
            elif strategy == 'rsi':
                signals['rsi'] = check_rsi_strategy(df)
            elif strategy == 'bollinger_bands':
                signals['bollinger_bands'] = check_bollinger_bands_strategy(df)
                
        # 检查所有策略的信号是否一致
        if not signals:
            return None
            
        # 获取所有策略的信号
        all_signals = list(signals.values())
        
        # 如果所有策略都给出做多信号
        if all(signal == 'BUY' for signal in all_signals):
            logger.info(f"All strategies ({', '.join(enabled_strategies)}) indicate BUY signal for {symbol}")
            return {
                'signal': 'BUY',
                'quantity': position_info['quantity'],
                'position_size': position_info['position_size'],
                'current_price': position_info['current_price']
            }
            
        # 如果所有策略都给出做空信号
        elif all(signal == 'SELL' for signal in all_signals):
            logger.info(f"All strategies ({', '.join(enabled_strategies)}) indicate SELL signal for {symbol}")
            return {
                'signal': 'SELL',
                'quantity': position_info['quantity'],
                'position_size': position_info['position_size'],
                'current_price': position_info['current_price']
            }
            
        # 如果策略信号不一致
        else:
            logger.info(f"Conflicting signals from strategies for {symbol}: {signals}")
            return None
            
    except Exception as e:
        logger.error(f"Error checking strategy conditions: {str(e)}")
        return None

# 智能网格计算
def calculate_grid_parameters(balance, symbol, exchange='Binance'):
    try:
        # 获取当前价格
        if exchange == 'Binance':
            client = get_binance_client()
            ticker = client.get_ticker(symbol=symbol)
            current_price = float(ticker['lastPrice'])
        elif exchange == 'LBank':
            response = requests.get(f'https://api.lbank.info/v2/ticker.do?symbol={symbol.lower()}')
            data = response.json()
            if data['result']:
                current_price = float(data['data'][0]['ticker']['latest'])
            else:
                raise Exception("Failed to get LBank ticker data")
        
        # 计算基础参数
        min_grid_amount = 10  # 最小网格金额（USDT）
        max_grid_amount = 1000  # 最大网格金额（USDT）
        min_grids = 5  # 最小网格数量
        max_grids = 50  # 最大网格数量
        
        # 根据余额计算网格数量
        if balance <= 100:  # 小资金
            grid_count = min_grids
            grid_amount = min_grid_amount
        elif balance <= 1000:  # 中等资金
            grid_count = int(balance / 50)  # 每50USDT一个网格
            grid_amount = balance / grid_count
        elif balance <= 10000:  # 大资金
            grid_count = int(balance / 200)  # 每200USDT一个网格
            grid_amount = balance / grid_count
        else:  # 超大资金
            grid_count = max_grids
            grid_amount = balance / grid_count
            
        # 确保网格数量在合理范围内
        grid_count = max(min_grids, min(grid_count, max_grids))
        grid_amount = max(min_grid_amount, min(grid_amount, max_grid_amount))
        
        # 计算网格间距
        # 根据价格波动率动态调整网格间距
        if exchange == 'Binance':
            klines = client.get_klines(symbol=symbol, interval='1h', limit=24)
            df = pd.DataFrame(klines, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'close_time', 'quote_volume', 'trades', 'taker_buy_base', 'taker_buy_quote', 'ignore'])
        else:
            response = requests.get(f'https://api.lbank.info/v2/kline.do?symbol={symbol.lower()}&size=24&type=1h')
            data = response.json()
            if data['result']:
                df = pd.DataFrame(data['data'], columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            else:
                raise Exception("Failed to get LBank kline data")
                
        df['close'] = df['close'].astype(float)
        volatility = df['close'].pct_change().std() * 100  # 计算24小时波动率
        
        # 根据波动率调整网格间距
        if volatility <= 1:  # 低波动
            grid_spacing = 0.2  # 0.2%
        elif volatility <= 2:  # 中等波动
            grid_spacing = 0.3  # 0.3%
        elif volatility <= 3:  # 高波动
            grid_spacing = 0.4  # 0.4%
        else:  # 超高波动
            grid_spacing = 0.5  # 0.5%
            
        # 计算上下限价格
        upper_price = current_price * (1 + (grid_count * grid_spacing / 200))
        lower_price = current_price * (1 - (grid_count * grid_spacing / 200))
        
        # 计算每个网格的价格
        grid_prices = []
        for i in range(grid_count + 1):
            price = lower_price + (upper_price - lower_price) * i / grid_count
            grid_prices.append(round(price, 8))
            
        return {
            'grid_count': grid_count,
            'grid_amount': grid_amount,
            'grid_spacing': grid_spacing,
            'current_price': current_price,
            'upper_price': upper_price,
            'lower_price': lower_price,
            'grid_prices': grid_prices,
            'volatility': volatility
        }
    except Exception as e:
        logger.error(f"Error calculating grid parameters: {str(e)}")
        return None

# 修改高频交易策略，使用智能网格
def check_scalping_strategy(df):
    try:
        # 获取账户余额
        current_exchange = os.getenv('CURRENT_EXCHANGE', 'Binance')
        trading_pair = os.getenv('TRADING_PAIR', 'BTCUSDT')
        
        if current_exchange == 'Binance':
            client = get_binance_client()
            account = client.get_account()
            balance = float([asset for asset in account['balances'] if asset['asset'] == 'USDT'][0]['free'])
        elif current_exchange == 'LBank':
            api_key = APIKey.query.filter_by(exchange='LBank', is_active=True).first()
            if not api_key:
                raise Exception("No active LBank API key found")
                
            timestamp = str(int(time.time() * 1000))
            params = {
                'api_key': api_key.api_key,
                'timestamp': timestamp
            }
            sign = generate_lbank_sign(params, api_key.api_secret)
            params['sign'] = sign
            
            response = requests.get('https://api.lbank.info/v2/user/account', params=params)
            account = response.json()
            
            if not account['result']:
                raise Exception("Failed to get LBank account info")
                
            balance = float([asset for asset in account['data'] if asset['asset'] == 'usdt'][0]['free'])
            
        # 计算网格参数
        grid_params = calculate_grid_parameters(balance, trading_pair, current_exchange)
        if not grid_params:
            return None
            
        # 获取当前价格
        current_price = df['close'].iloc[-1]
        
        # 找到当前价格所在的网格区间
        for i in range(len(grid_params['grid_prices']) - 1):
            if grid_params['grid_prices'][i] <= current_price <= grid_params['grid_prices'][i + 1]:
                # 如果价格接近下边界，给出买入信号
                if (current_price - grid_params['grid_prices'][i]) / (grid_params['grid_prices'][i + 1] - grid_params['grid_prices'][i]) < 0.2:
                    return 'BUY'
                # 如果价格接近上边界，给出卖出信号
                elif (current_price - grid_params['grid_prices'][i]) / (grid_params['grid_prices'][i + 1] - grid_params['grid_prices'][i]) > 0.8:
                    return 'SELL'
                break
                
        return None
    except Exception as e:
        logger.error(f"Error in scalping strategy: {str(e)}")
        return None

# SuperTrend策略
def check_supertrend_strategy(df):
    try:
        # 计算ATR
        df['tr'] = pd.DataFrame({
            'hl': df['high'] - df['low'],
            'hc': abs(df['high'] - df['close'].shift(1)),
            'lc': abs(df['low'] - df['close'].shift(1))
        }).max(axis=1)
        df['atr'] = df['tr'].rolling(window=10).mean()
        
        # 计算SuperTrend
        df['upperband'] = ((df['high'] + df['low']) / 2) + (2 * df['atr'])
        df['lowerband'] = ((df['high'] + df['low']) / 2) - (2 * df['atr'])
        
        # 初始化SuperTrend
        df['in_uptrend'] = True
        for i in range(1, len(df)):
            current_close = df['close'].iloc[i]
            prev_close = df['close'].iloc[i-1]
            
            if current_close > df['upperband'].iloc[i-1]:
                df.loc[df.index[i], 'in_uptrend'] = True
            elif current_close < df['lowerband'].iloc[i-1]:
                df.loc[df.index[i], 'in_uptrend'] = False
            else:
                df.loc[df.index[i], 'in_uptrend'] = df['in_uptrend'].iloc[i-1]
                
                if df['in_uptrend'].iloc[i] and df['lowerband'].iloc[i] < df['lowerband'].iloc[i-1]:
                    df.loc[df.index[i], 'lowerband'] = df['lowerband'].iloc[i-1]
                    
                if not df['in_uptrend'].iloc[i] and df['upperband'].iloc[i] > df['upperband'].iloc[i-1]:
                    df.loc[df.index[i], 'upperband'] = df['upperband'].iloc[i-1]
        
        # 获取最新趋势
        current_trend = df['in_uptrend'].iloc[-1]
        prev_trend = df['in_uptrend'].iloc[-2]
        
        # 判断交易信号
        if current_trend and not prev_trend:
            return 'BUY'
        elif not current_trend and prev_trend:
            return 'SELL'
        return None
    except Exception as e:
        logger.error(f"Error in supertrend strategy: {str(e)}")
        return None

# RSI策略
def check_rsi_strategy(df):
    try:
        # 计算RSI
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))
        
        # 获取最新RSI值
        current_rsi = df['rsi'].iloc[-1]
        
        # 判断交易信号
        if current_rsi < 30:
            return 'BUY'
        elif current_rsi > 70:
            return 'SELL'
        return None
    except Exception as e:
        logger.error(f"Error in RSI strategy: {str(e)}")
        return None

# 布林带策略
def check_bollinger_bands_strategy(df):
    try:
        # 计算布林带
        df['sma'] = df['close'].rolling(window=20).mean()
        df['std'] = df['close'].rolling(window=20).std()
        df['upper_band'] = df['sma'] + (df['std'] * 2)
        df['lower_band'] = df['sma'] - (df['std'] * 2)
        
        # 获取最新数据
        current_price = df['close'].iloc[-1]
        upper_band = df['upper_band'].iloc[-1]
        lower_band = df['lower_band'].iloc[-1]
        
        # 判断交易信号
        if current_price < lower_band:
            return 'BUY'
        elif current_price > upper_band:
            return 'SELL'
        return None
    except Exception as e:
        logger.error(f"Error in Bollinger Bands strategy: {str(e)}")
        return None

# 添加保存策略设置的API路由
@app.route('/api/save-strategy-settings', methods=['POST'])
def save_strategy_settings():
    try:
        settings = request.json
        
        # 验证设置参数
        required_params = {
            'rsi_period': int,
            'rsi_overbought': int,
            'rsi_oversold': int,
            'bb_period': int,
            'bb_std': float,
            'supertrend_atr_period': int,
            'supertrend_atr_multiplier': float,
            'grid_count': int,
            'grid_spacing': float
        }
        
        for param, param_type in required_params.items():
            if param not in settings:
                raise ValueError(f"Missing required parameter: {param}")
            try:
                settings[param] = param_type(settings[param])
            except ValueError:
                raise ValueError(f"Invalid value for parameter: {param}")
        
        # 保存设置到环境变量
        os.environ['RSI_PERIOD'] = str(settings['rsi_period'])
        os.environ['RSI_OVERBOUGHT'] = str(settings['rsi_overbought'])
        os.environ['RSI_OVERSOLD'] = str(settings['rsi_oversold'])
        os.environ['BB_PERIOD'] = str(settings['bb_period'])
        os.environ['BB_STD'] = str(settings['bb_std'])
        os.environ['SUPERTREND_ATR_PERIOD'] = str(settings['supertrend_atr_period'])
        os.environ['SUPERTREND_ATR_MULTIPLIER'] = str(settings['supertrend_atr_multiplier'])
        os.environ['GRID_COUNT'] = str(settings['grid_count'])
        os.environ['GRID_SPACING'] = str(settings['grid_spacing'])
        
        # 保存设置到配置文件
        config = {
            'RSI_PERIOD': settings['rsi_period'],
            'RSI_OVERBOUGHT': settings['rsi_overbought'],
            'RSI_OVERSOLD': settings['rsi_oversold'],
            'BB_PERIOD': settings['bb_period'],
            'BB_STD': settings['bb_std'],
            'SUPERTREND_ATR_PERIOD': settings['supertrend_atr_period'],
            'SUPERTREND_ATR_MULTIPLIER': settings['supertrend_atr_multiplier'],
            'GRID_COUNT': settings['grid_count'],
            'GRID_SPACING': settings['grid_spacing']
        }
        
        with open('.env', 'a') as f:
            for key, value in config.items():
                f.write(f"{key}={value}\n")
        
        return jsonify({
            'success': True,
            'message': 'Strategy settings saved successfully'
        })
    except Exception as e:
        logger.error(f"Error saving strategy settings: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# 添加错误处理装饰器
@app.errorhandler(500)
def internal_error(error):
    logger.error(f"Internal Server Error: {str(error)}")
    return jsonify({
        'success': False,
        'error': 'Internal Server Error',
        'message': str(error)
    }), 500

@app.errorhandler(404)
def not_found_error(error):
    logger.error(f"Not Found Error: {str(error)}")
    return jsonify({
        'success': False,
        'error': 'Not Found',
        'message': str(error)
    }), 404

# 添加获取交易历史的API
@app.route('/api/trades')
def get_trades():
    try:
        trades = TradeHistory.query.order_by(TradeHistory.timestamp.desc()).limit(50).all()
        return jsonify({
            'success': True,
            'trades': [{
                'exchange': trade.exchange,
                'symbol': trade.symbol,
                'side': trade.side,
                'price': trade.price,
                'quantity': trade.quantity,
                'timestamp': trade.timestamp.isoformat(),
                'status': trade.status
            } for trade in trades]
        })
    except Exception as e:
        logger.error(f"Error getting trades: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

def check_api_keys():
    try:
        # 检查是否有活跃的API密钥
        active_keys = APIKey.query.filter_by(is_active=True).all()
        if not active_keys:
            logger.warning("No active API keys found")
            return False
            
        # 检查每个API密钥是否有效
        for key in active_keys:
            try:
                if key.exchange == 'Binance':
                    client = Client(key.api_key, key.api_secret)
                    client.get_account()
                elif key.exchange == 'LBank':
                    timestamp = str(int(time.time() * 1000))
                    params = {
                        'api_key': key.api_key,
                        'timestamp': timestamp
                    }
                    sign = generate_lbank_sign(params, key.api_secret)
                    params['sign'] = sign
                    response = requests.get('https://api.lbank.info/v2/user/account', params=params)
                    if not response.json()['result']:
                        raise Exception("Invalid LBank API key")
            except Exception as e:
                logger.error(f"Invalid API key for {key.exchange}: {str(e)}")
                key.is_active = False
                db.session.commit()
                continue
                
        return True
    except Exception as e:
        logger.error(f"Error checking API keys: {str(e)}")
        return False

# 在应用启动时检查API密钥
@app.before_first_request
def before_first_request():
    check_api_keys()

if __name__ == '__main__':
    # 修改为监听本地地址，让 Nginx 处理外部请求
    app.run(host='127.0.0.1', port=5000, debug=False) 