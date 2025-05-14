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

@app.route('/api/trading-bot/status')
def get_trading_bot_status():
    try:
        global trading_bot_process
        is_running = trading_bot_process is not None and trading_bot_process.poll() is None
        return jsonify({
            'success': True,
            'is_running': is_running
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/trading-bot/start', methods=['POST'])
def start_trading_bot():
    try:
        global trading_bot_process
        
        # 如果已经有进程在运行，先停止它
        if trading_bot_process is not None and trading_bot_process.poll() is None:
            trading_bot_process.terminate()
            trading_bot_process.wait()
        
        # 启动新的进程
        if os.name == 'nt':  # Windows
            trading_bot_process = subprocess.Popen(['python', 'run_trading_bot.py'],
                                                 creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
        else:  # Linux/Unix
            trading_bot_process = subprocess.Popen(['python3', 'run_trading_bot.py'],
                                                 preexec_fn=os.setpgrp)
            
        return jsonify({
            'success': True,
            'message': '交易机器人已启动'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/trading-bot/stop', methods=['POST'])
def stop_trading_bot():
    try:
        global trading_bot_process
        
        if trading_bot_process is not None:
            if os.name == 'nt':  # Windows
                trading_bot_process.terminate()
            else:  # Linux/Unix
                os.killpg(os.getpgid(trading_bot_process.pid), signal.SIGTERM)
            trading_bot_process.wait()
            trading_bot_process = None
            
        return jsonify({
            'success': True,
            'message': '交易机器人已停止'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/trading-bot/restart', methods=['POST'])
def restart_trading_bot():
    try:
        # 先停止
        stop_response = stop_trading_bot()
        if not stop_response.json['success']:
            return stop_response
            
        # 再启动
        return start_trading_bot()
    except Exception as e:
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

if __name__ == '__main__':
    # 修改为监听本地地址，让 Nginx 处理外部请求
    app.run(host='127.0.0.1', port=5000, debug=False) 