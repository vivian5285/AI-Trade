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
from functools import lru_cache, wraps
from trading_bot_manager import trading_bot_manager

# 加载环境变量
load_dotenv()

# 确保必要的目录存在
for directory in ['/root/AI-Trade/instance', '/root/AI-Trade/logs']:
    if not os.path.exists(directory):
        os.makedirs(directory)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/root/AI-Trade/logs/app.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def api_response(data=None, success=True, error=None, message=None, status_code=200):
    """统一的API响应格式"""
    response = {
        'success': success,
        'data': data,
        'error': error,
        'message': message
    }
    return jsonify(response), status_code

def load_config():
    """加载配置文件"""
    try:
        config = {
            'trading_settings': {
                'exchange': os.getenv('CURRENT_EXCHANGE', 'binance'),
                'trading_pair': os.getenv('TRADING_PAIR', 'BTCUSDT'),
                'leverage': os.getenv('LEVERAGE', '10'),
                'stop_loss': os.getenv('STOP_LOSS_PERCENTAGE', '0.3'),
                'take_profit': os.getenv('TAKE_PROFIT_PERCENTAGE', '0.6'),
                'max_daily_trades': os.getenv('MAX_DAILY_TRADES', '100')
            },
            'strategy_settings': {
                'rsi_period': os.getenv('RSI_PERIOD', '14'),
                'rsi_overbought': os.getenv('RSI_OVERBOUGHT', '70'),
                'rsi_oversold': os.getenv('RSI_OVERSOLD', '30'),
                'bb_period': os.getenv('BB_PERIOD', '20'),
                'bb_std': os.getenv('BB_STD', '2.0'),
                'supertrend_atr_period': os.getenv('SUPERTREND_ATR_PERIOD', '10'),
                'supertrend_atr_multiplier': os.getenv('SUPERTREND_ATR_MULTIPLIER', '3.0'),
                'grid_count': os.getenv('GRID_COUNT', '10'),
                'grid_spacing': os.getenv('GRID_SPACING', '0.5')
            }
        }
        return config
    except Exception as e:
        logger.error(f"Error loading config: {str(e)}")
        return None

def get_high_frequency_trading_status():
    """获取高频交易状态"""
    try:
        # 获取最近的交易记录
        trades = TradeHistory.query.filter_by(strategy='high_frequency').order_by(TradeHistory.timestamp.desc()).limit(10).all()
        
        # 计算统计数据
        total_trades = len(trades)
        winning_trades = sum(1 for trade in trades if trade.pnl > 0)
        total_profit = sum(trade.pnl for trade in trades)
        
        return {
            'is_running': True,  # 这里需要根据实际情况判断
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'win_rate': (winning_trades / total_trades * 100) if total_trades > 0 else 0,
            'total_profit': total_profit,
            'recent_trades': [
                {
                    'id': trade.id,
                    'timestamp': trade.timestamp.isoformat(),
                    'side': trade.side,
                    'price': trade.price,
                    'quantity': trade.quantity,
                    'pnl': trade.pnl
                }
                for trade in trades
            ]
        }
    except Exception as e:
        logger.error(f"Error getting high frequency trading status: {str(e)}")
        return None

# 错误处理装饰器
def handle_errors(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except Exception as e:
            logger.error(f"Error in {f.__name__}: {str(e)}")
            return api_response(success=False, error=str(e), status_code=500)
    return decorated_function

# 请求日志装饰器
def log_request(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        logger.info(f"Request to {f.__name__} from {request.remote_addr}")
        return f(*args, **kwargs)
    return decorated_function

# 参数验证装饰器
def validate_params(*required_params):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            data = request.get_json()
            if not data:
                return api_response(success=False, error="No data provided", status_code=400)
            
            missing_params = [param for param in required_params if param not in data]
            if missing_params:
                return api_response(
                    success=False,
                    error=f"Missing required parameters: {', '.join(missing_params)}",
                    status_code=400
                )
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# Binance客户端获取函数
def get_binance_client():
    try:
        api_key = os.getenv('BINANCE_API_KEY')
        api_secret = os.getenv('BINANCE_API_SECRET')
        
        if not api_key or not api_secret:
            raise ValueError("Binance API credentials not found in environment variables")
        
        return Client(api_key, api_secret)
    except Exception as e:
        logger.error(f"Error creating Binance client: {str(e)}")
        raise

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///trading.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Add custom Jinja2 filter for parsing JSON strings
@app.template_filter('from_json')
def from_json_filter(value):
    if isinstance(value, str):
        try:
            return json.loads(value)
        except:
            return []
    return value

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
    bot_id = db.Column(db.Integer, db.ForeignKey('trading_bot_config.id'))  # 关联到交易机器人
    exchange = db.Column(db.String(20), nullable=False)
    symbol = db.Column(db.String(20), nullable=False)
    side = db.Column(db.String(10), nullable=False)  # BUY, SELL
    position_type = db.Column(db.String(10), nullable=False)  # LONG, SHORT
    price = db.Column(db.Float, nullable=False)
    quantity = db.Column(db.Float, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), nullable=False)  # OPEN, CLOSED, CANCELLED
    strategy = db.Column(db.String(20))
    strategy_params = db.Column(db.String(255))
    pnl = db.Column(db.Float)  # 盈亏金额
    pnl_percentage = db.Column(db.Float)  # 盈亏百分比

# 交易机器人配置模型
class TradingBotConfig(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)  # 机器人名称
    exchange = db.Column(db.String(20), nullable=False)  # 交易所
    trading_pair = db.Column(db.String(20), nullable=False)  # 交易对
    funds = db.Column(db.Float, nullable=False)  # 分配资金
    strategies = db.Column(db.String(255), nullable=False)  # 策略列表（JSON格式）
    kline_period = db.Column(db.String(10), nullable=False)  # K线周期
    leverage = db.Column(db.Integer, nullable=False)  # 杠杆倍数
    stop_loss = db.Column(db.Float, nullable=False)  # 止损比例
    take_profit = db.Column(db.Float, nullable=False)  # 止盈比例
    max_daily_trades = db.Column(db.Integer, nullable=False)  # 每日最大交易次数
    status = db.Column(db.String(20), default='STOPPED')  # 运行状态：RUNNING/STOPPED
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

# 交易机器人运行记录模型
class TradingBotLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    bot_id = db.Column(db.Integer, db.ForeignKey('trading_bot_config.id'), nullable=False)
    action = db.Column(db.String(50), nullable=False)  # 操作类型
    details = db.Column(db.Text)  # 详细信息
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# 创建数据库表
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

# 添加全局变量来跟踪交易机器人进程
trading_bot_process = None

# 交易机器人状态管理
trading_bot_running = False

# 在文件开头添加策略名称常量
STRATEGY_NAMES = {
    'scalping': '网格交易',
    'supertrend': '超级趋势',
    'rsi': 'RSI策略',
    'bollinger_bands': '布林带策略'
}

# 路由：首页
@app.route('/')
def index():
    try:
        return render_template('index.html')
    except Exception as e:
        logger.error(f"Error loading index page: {str(e)}")
        return render_template('error.html', error=str(e)), 500

# 路由：仪表盘
@app.route('/dashboard')
def dashboard():
    try:
        api_keys = APIKey.query.all()
        trades = TradeHistory.query.order_by(TradeHistory.timestamp.desc()).limit(10).all()
        return render_template('dashboard.html', api_keys=api_keys, trades=trades)
    except Exception as e:
        logger.error(f"Error in dashboard route: {str(e)}")
        return render_template('error.html', error=str(e)), 500

# 路由：交易记录
@app.route('/trades')
def trades():
    try:
        # 获取所有交易记录，按时间倒序排列
        trades = TradeHistory.query.order_by(TradeHistory.timestamp.desc()).all()
        
        # 处理策略参数显示
        for trade in trades:
            if trade.strategy_params:
                try:
                    # 将JSON字符串转换为Python对象
                    params = json.loads(trade.strategy_params)
                    # 格式化显示
                    trade.strategy_params = json.dumps(params, indent=2, ensure_ascii=False)
                except:
                    trade.strategy_params = None
        
        return render_template('trades.html', trades=trades)
    except Exception as e:
        logger.error(f"获取交易记录失败: {str(e)}")
        flash('获取交易记录失败', 'error')
        return redirect(url_for('index'))

# 路由：系统配置
@app.route('/config')
def config():
    try:
        # 获取当前配置
        config = {
            'trading_settings': {
                'exchange': os.getenv('CURRENT_EXCHANGE', 'binance'),
                'trading_pair': os.getenv('TRADING_PAIR', 'BTCUSDT'),
                'leverage': os.getenv('LEVERAGE', '10'),
                'stop_loss': os.getenv('STOP_LOSS_PERCENTAGE', '0.3'),
                'take_profit': os.getenv('TAKE_PROFIT_PERCENTAGE', '0.6'),
                'max_daily_trades': os.getenv('MAX_DAILY_TRADES', '100')
            },
            'strategy_settings': {
                'rsi_period': os.getenv('RSI_PERIOD', '14'),
                'rsi_overbought': os.getenv('RSI_OVERBOUGHT', '70'),
                'rsi_oversold': os.getenv('RSI_OVERSOLD', '30'),
                'bb_period': os.getenv('BB_PERIOD', '20'),
                'bb_std': os.getenv('BB_STD', '2.0'),
                'supertrend_atr_period': os.getenv('SUPERTREND_ATR_PERIOD', '10'),
                'supertrend_atr_multiplier': os.getenv('SUPERTREND_ATR_MULTIPLIER', '3.0'),
                'grid_count': os.getenv('GRID_COUNT', '10'),
                'grid_spacing': os.getenv('GRID_SPACING', '0.5')
            }
        }
        
        return render_template('config.html', config=config)
    except Exception as e:
        logger.error(f"Error loading config page: {str(e)}")
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
@app.route('/trade_history')
def trade_history():
    try:
        # 获取所有交易记录，按时间倒序排列
        trades = TradeHistory.query.order_by(TradeHistory.timestamp.desc()).all()
        
        # 处理策略参数显示
        for trade in trades:
            if trade.strategy_params:
                try:
                    # 将JSON字符串转换为Python对象
                    params = json.loads(trade.strategy_params)
                    # 格式化显示
                    trade.strategy_params = json.dumps(params, indent=2, ensure_ascii=False)
                except:
                    trade.strategy_params = None
        
        return render_template('trade_history.html', trades=trades)
    except Exception as e:
        logger.error(f"获取交易历史失败: {str(e)}")
        flash('获取交易历史失败', 'error')
        return redirect(url_for('index'))

# 添加获取单个交易详情的路由
@app.route('/trade_history/<int:trade_id>')
def view_trade_details(trade_id):
    try:
        trade = TradeHistory.query.get_or_404(trade_id)
        return jsonify({
            'success': True,
            'trade': {
                'id': trade.id,
                'exchange': trade.exchange,
                'symbol': trade.symbol,
                'side': trade.side,
                'price': trade.price,
                'quantity': trade.quantity,
                'timestamp': trade.timestamp.isoformat(),
                'status': trade.status,
                'strategy': trade.strategy,
                'strategy_params': trade.strategy_params
            }
        })
    except Exception as e:
        logger.error(f"获取交易详情失败: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# 添加获取单个交易详情的API
@app.route('/api/trades/<int:trade_id>')
def get_trade_detail(trade_id):
    try:
        trade = TradeHistory.query.get_or_404(trade_id)
        return jsonify({
            'success': True,
            'trade': {
                'id': trade.id,
                'exchange': trade.exchange,
                'symbol': trade.symbol,
                'side': trade.side,
                'price': trade.price,
                'quantity': trade.quantity,
                'timestamp': trade.timestamp.isoformat(),
                'status': trade.status,
                'strategy': trade.strategy,
                'strategy_params': trade.strategy_params
            }
        })
    except Exception as e:
        logger.error(f"获取交易详情失败: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

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

@app.route('/api/settings', methods=['GET'])
@handle_errors
@log_request
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
        
        return api_response(
            data=settings['trading_settings']
        )
    except Exception as e:
        logger.error(f"Error getting settings: {str(e)}")
        return api_response(
            success=False,
            error=str(e),
            message="获取设置失败",
            status_code=500
        )

@app.route('/api/settings', methods=['POST'])
@handle_errors
@log_request
@validate_params('exchange', 'trading_pair', 'leverage', 'stop_loss', 'take_profit', 'max_daily_trades')
def update_settings():
    try:
        settings = request.json
        
        # 验证设置
        if not all(key in settings for key in ['exchange', 'trading_pair', 'leverage', 'stop_loss', 'take_profit', 'max_daily_trades']):
            return api_response(
                success=False,
                error="缺少必要的设置项",
                message="请提供所有必要的设置参数",
                status_code=400
            )
        
        # 更新设置
        with open('config.json', 'w') as f:
            json.dump(settings, f, indent=4)
        
        # 更新环境变量
        os.environ['CURRENT_EXCHANGE'] = settings['exchange']
        
        return api_response(
            message="设置已更新"
        )
    except Exception as e:
        logger.error(f"Error updating settings: {str(e)}")
        return api_response(
            success=False,
            error=str(e),
            message="更新设置失败",
            status_code=500
        )

@app.route('/api/trades')
@handle_errors
@log_request
def get_trades():
    try:
        # 获取所有交易记录，按时间倒序排列，并关联机器人信息
        trades = db.session.query(
            TradeHistory,
            TradingBotConfig.name.label('bot_name')
        ).outerjoin(
            TradingBotConfig,
            TradeHistory.bot_id == TradingBotConfig.id
        ).order_by(TradeHistory.timestamp.desc()).limit(50).all()
        
        return api_response(
            data={
                'trades': [{
                    'id': trade.TradeHistory.id,
                    'bot_id': trade.TradeHistory.bot_id,
                    'bot_name': trade.bot_name,
                    'exchange': trade.TradeHistory.exchange,
                    'symbol': trade.TradeHistory.symbol,
                    'side': trade.TradeHistory.side,
                    'position_type': trade.TradeHistory.position_type,
                    'price': trade.TradeHistory.price,
                    'quantity': trade.TradeHistory.quantity,
                    'timestamp': trade.TradeHistory.timestamp.isoformat(),
                    'status': trade.TradeHistory.status,
                    'strategy': trade.TradeHistory.strategy,
                    'strategy_params': trade.TradeHistory.strategy_params,
                    'pnl': trade.TradeHistory.pnl,
                    'pnl_percentage': trade.TradeHistory.pnl_percentage
                } for trade in trades]
            }
        )
    except Exception as e:
        logger.error(f"Error getting trades: {str(e)}")
        return api_response(
            success=False,
            error=str(e),
            message="获取交易历史失败",
            status_code=500
        )

@app.route('/api/chart-data')
@handle_errors
@log_request
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
        
        return api_response(
            data={
                'equity_data': equity_data,
                'trade_stats': trade_stats
            }
        )
    except Exception as e:
        logger.error(f"Error getting chart data: {str(e)}")
        return api_response(
            success=False,
            error=str(e),
            message="获取图表数据失败",
            status_code=500
        )

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

# 修改交易执行函数
def execute_trade(exchange, symbol, side, quantity, price, strategy=None, strategy_params=None, bot_id=None):
    """执行交易"""
    try:
        # 获取账户信息
        account_info = get_account_balance(exchange)
        if not account_info:
            raise Exception("Failed to get account information")
            
        # 分析市场状态
        market_state = analyze_market_conditions(symbol)
        if not market_state:
            raise Exception("Failed to analyze market conditions")
            
        # 选择最优策略
        if not strategy:
            strategy = select_optimal_strategy(market_state, account_info)
            if not strategy:
                raise Exception("Failed to select optimal strategy")
                
        # 计算最优仓位
        position_info = calculate_optimal_position_size(account_info, market_state, strategy)
        if not position_info:
            raise Exception("Failed to calculate optimal position size")
            
        # 更新交易参数
        quantity = position_info['position_size'] / price
        strategy_params = {
            'leverage': position_info['leverage'],
            'stop_loss': position_info['stop_loss'],
            'take_profit': position_info['take_profit'],
            'market_state': market_state,
            'strategy': strategy
        }
        
        # 确定交易方向（做多/做空）
        position_type = 'LONG' if side == 'BUY' else 'SHORT'
        
        # 创建交易记录
        trade = TradeHistory(
            bot_id=bot_id,
            exchange=exchange,
            symbol=symbol,
            side=side,
            position_type=position_type,
            price=price,
            quantity=quantity,
            status='OPEN',
            strategy=strategy,
            strategy_params=json.dumps(strategy_params)
        )
        db.session.add(trade)
        db.session.commit()
        
        # 记录日志
        strategy_name = STRATEGY_NAMES.get(strategy, '手动')
        bot_name = TradingBotConfig.query.get(bot_id).name if bot_id else '手动'
        logger.info(f"执行{bot_name}的{strategy_name}交易: {exchange} {symbol} {position_type} {quantity}@{price}")
        logger.info(f"交易参数: {strategy_params}")
        
        return trade
        
    except Exception as e:
        logger.error(f"执行交易失败: {str(e)}")
        db.session.rollback()
        return None

# 路由：策略日志页面
@app.route('/strategy-logs')
def strategy_logs():
    try:
        return render_template('strategy_logs.html')
    except Exception as e:
        logger.error(f"Error loading strategy logs page: {str(e)}")
        return render_template('error.html', error=str(e)), 500

# API路由：获取策略日志
@app.route('/api/strategy-logs')
def get_strategy_logs():
    try:
        # 从交易历史中获取策略相关的交易记录
        trades = TradeHistory.query.filter(
            TradeHistory.strategy.isnot(None)
        ).order_by(TradeHistory.timestamp.desc()).limit(100).all()
        
        logs = []
        for trade in trades:
            logs.append({
                'timestamp': trade.timestamp.isoformat(),
                'strategy': trade.strategy,
                'symbol': trade.symbol,
                'signal': trade.side,  # BUY 或 SELL
                'price': trade.price,
                'quantity': trade.quantity,
                'status': trade.status,
                'strategy_params': trade.strategy_params
            })
        
        return jsonify({
            'success': True,
            'logs': logs
        })
    except Exception as e:
        logger.error(f"Error getting strategy logs: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

def get_account_balance(exchange='Binance'):
    """获取账户余额和持仓信息"""
    try:
        if exchange == 'Binance':
            client = get_binance_client()
            # 获取合约账户信息
            futures_account = client.futures_account()
            
            # 计算总权益和未实现盈亏
            total_balance = float(futures_account['totalWalletBalance'])
            unrealized_pnl = float(futures_account['totalUnrealizedProfit'])
            
            # 获取持仓信息
            positions = []
            for position in futures_account['positions']:
                if float(position['positionAmt']) != 0:  # 只显示有持仓的
                    positions.append({
                        'symbol': position['symbol'],
                        'amount': float(position['positionAmt']),
                        'entry_price': float(position['entryPrice']),
                        'mark_price': float(position['markPrice']),
                        'unrealized_pnl': float(position['unRealizedProfit']),
                        'leverage': float(position['leverage']),
                        'side': 'LONG' if float(position['positionAmt']) > 0 else 'SHORT'
                    })
            
            return {
                'total_balance': total_balance,
                'unrealized_pnl': unrealized_pnl,
                'positions': positions
            }
            
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
            
            # 获取合约账户信息
            response = requests.get('https://api.lbank.info/v2/user/contract_account', params=params)
            if response.status_code != 200:
                raise Exception("Failed to fetch LBank data")
                
            data = response.json()
            if not data['result']:
                raise Exception("Failed to get LBank account data")
                
            account_data = data['data']
            
            # 获取持仓信息
            positions_response = requests.get('https://api.lbank.info/v2/user/contract_position', params=params)
            positions_data = positions_response.json()
            
            positions = []
            if positions_data['result']:
                for position in positions_data['data']:
                    if float(position['amount']) != 0:  # 只显示有持仓的
                        positions.append({
                            'symbol': position['symbol'],
                            'amount': float(position['amount']),
                            'entry_price': float(position['entry_price']),
                            'mark_price': float(position['mark_price']),
                            'unrealized_pnl': float(position['unrealized_pnl']),
                            'leverage': float(position['leverage']),
                            'side': 'LONG' if position['side'] == 'buy' else 'SHORT'
                        })
            
            return jsonify({
                'total_balance': float(account_data['total_balance']),
                'unrealized_pnl': float(account_data['unrealized_pnl']),
                'positions': positions
            })
                
    except Exception as e:
        logger.error(f"Error getting account balance: {str(e)}")
        return None

def analyze_market_conditions(symbol, timeframe='1m'):
    """分析市场条件，返回市场状态和波动性"""
    try:
        # 获取K线数据
        klines = get_cached_klines(symbol, timeframe, int(time.time() / 60))
        if not klines:
            return None
            
        df = pd.DataFrame(klines)
        
        # 计算技术指标
        # 1. 计算波动率
        df['returns'] = df['close'].pct_change()
        volatility = df['returns'].std() * 100  # 转换为百分比
        
        # 2. 计算趋势强度
        df['sma20'] = df['close'].rolling(window=20).mean()
        df['sma50'] = df['close'].rolling(window=50).mean()
        trend_strength = abs((df['sma20'].iloc[-1] - df['sma50'].iloc[-1]) / df['sma50'].iloc[-1] * 100)
        
        # 3. 计算成交量趋势
        df['volume_sma'] = df['volume'].rolling(window=20).mean()
        volume_trend = df['volume'].iloc[-1] / df['volume_sma'].iloc[-1]
        
        # 4. 计算市场状态
        market_state = {
            'volatility': volatility,
            'trend_strength': trend_strength,
            'volume_trend': volume_trend,
            'is_trending': trend_strength > 1.0,  # 趋势强度大于1%认为是趋势市场
            'is_volatile': volatility > 1.0,  # 波动率大于1%认为是高波动市场
            'is_high_volume': volume_trend > 1.2  # 成交量大于20日均量认为是高成交量
        }
        
        return market_state
        
    except Exception as e:
        logger.error(f"Error analyzing market conditions: {str(e)}")
        return None

def select_optimal_strategy(market_state, account_info):
    """根据市场状态和账户信息选择最优策略"""
    try:
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
            return None
            
        # 根据市场状态选择策略
        if market_state['is_trending']:
            # 趋势市场优先使用趋势策略
            if 'supertrend' in enabled_strategies:
                return 'supertrend'
            elif 'bollinger_bands' in enabled_strategies:
                return 'bollinger_bands'
        elif market_state['is_volatile']:
            # 高波动市场优先使用网格策略
            if 'scalping' in enabled_strategies:
                return 'scalping'
        elif market_state['is_high_volume']:
            # 高成交量市场可以使用RSI策略
            if 'rsi' in enabled_strategies:
                return 'rsi'
                
        # 默认返回第一个启用的策略
        return enabled_strategies[0]
        
    except Exception as e:
        logger.error(f"Error selecting optimal strategy: {str(e)}")
        return None

def calculate_optimal_position_size(account_info, market_state, strategy):
    """计算最优仓位大小"""
    try:
        total_balance = account_info['total_balance']
        unrealized_pnl = account_info['unrealized_pnl']
        current_positions = account_info['positions']
        
        # 计算当前总持仓价值
        total_position_value = sum(abs(pos['amount'] * pos['mark_price']) for pos in current_positions)
        
        # 基础风险参数
        max_risk_per_trade = 0.02  # 单笔交易最大风险（总资金的2%）
        max_total_risk = 0.1  # 总持仓最大风险（总资金的10%）
        min_position_size = 10  # 最小仓位（USDT）
        max_position_size = total_balance * 0.5  # 最大仓位（总资金的50%）
        
        # 根据市场状态调整风险参数
        if market_state['is_volatile']:
            max_risk_per_trade *= 0.8  # 高波动市场降低风险
        elif market_state['is_trending']:
            max_risk_per_trade *= 1.2  # 趋势市场可以适当提高风险
            
        # 根据策略调整风险参数
        if strategy == 'scalping':
            max_risk_per_trade *= 0.8  # 网格策略降低风险
        elif strategy == 'supertrend':
            max_risk_per_trade *= 1.2  # 趋势策略可以适当提高风险
            
        # 计算可用风险额度
        available_risk = total_balance * max_total_risk - total_position_value
        
        # 如果可用风险额度小于最小仓位，返回None
        if available_risk < min_position_size:
            logger.warning(f"Available risk ({available_risk} USDT) is less than minimum position size ({min_position_size} USDT)")
            return None
            
        # 计算建议仓位大小
        suggested_position = min(
            max(min_position_size, total_balance * max_risk_per_trade),  # 单笔交易风险限制
            max_position_size,  # 最大仓位限制
            available_risk  # 可用风险额度限制
        )
        
        return {
            'position_size': suggested_position,
            'leverage': calculate_optimal_leverage(market_state, strategy),
            'stop_loss': calculate_stop_loss(market_state, strategy),
            'take_profit': calculate_take_profit(market_state, strategy)
        }
        
    except Exception as e:
        logger.error(f"Error calculating optimal position size: {str(e)}")
        return None

def calculate_optimal_leverage(market_state, strategy):
    """计算最优杠杆倍数"""
    try:
        # 基础杠杆倍数
        base_leverage = 10
        
        # 根据市场状态调整杠杆
        if market_state['is_volatile']:
            base_leverage *= 0.8  # 高波动市场降低杠杆
        elif market_state['is_trending']:
            base_leverage *= 1.2  # 趋势市场可以适当提高杠杆
            
        # 根据策略调整杠杆
        if strategy == 'scalping':
            base_leverage *= 0.8  # 网格策略降低杠杆
        elif strategy == 'supertrend':
            base_leverage *= 1.2  # 趋势策略可以适当提高杠杆
            
        # 确保杠杆在合理范围内
        return max(1, min(20, base_leverage))
        
    except Exception as e:
        logger.error(f"Error calculating optimal leverage: {str(e)}")
        return 10  # 默认返回10倍杠杆

def calculate_stop_loss(market_state, strategy):
    """计算止损价格"""
    try:
        # 基础止损比例
        base_stop_loss = 0.02  # 2%
        
        # 根据市场状态调整止损
        if market_state['is_volatile']:
            base_stop_loss *= 1.2  # 高波动市场扩大止损
        elif market_state['is_trending']:
            base_stop_loss *= 0.8  # 趋势市场收紧止损
            
        # 根据策略调整止损
        if strategy == 'scalping':
            base_stop_loss *= 0.8  # 网格策略收紧止损
        elif strategy == 'supertrend':
            base_stop_loss *= 1.2  # 趋势策略扩大止损
            
        return base_stop_loss
        
    except Exception as e:
        logger.error(f"Error calculating stop loss: {str(e)}")
        return 0.02  # 默认返回2%止损

def calculate_take_profit(market_state, strategy):
    """计算止盈价格"""
    try:
        # 基础止盈比例
        base_take_profit = 0.04  # 4%
        
        # 根据市场状态调整止盈
        if market_state['is_volatile']:
            base_take_profit *= 1.2  # 高波动市场扩大止盈
        elif market_state['is_trending']:
            base_take_profit *= 1.5  # 趋势市场大幅提高止盈
            
        # 根据策略调整止盈
        if strategy == 'scalping':
            base_take_profit *= 0.8  # 网格策略收紧止盈
        elif strategy == 'supertrend':
            base_take_profit *= 1.5  # 趋势策略扩大止盈
            
        return base_take_profit
        
    except Exception as e:
        logger.error(f"Error calculating take profit: {str(e)}")
        return 0.04  # 默认返回4%止盈

def check_high_frequency_strategy(df, timeframe='1m'):
    """高频交易策略"""
    try:
        # 计算技术指标
        # 1. 计算EMA
        df['ema9'] = df['close'].ewm(span=9, adjust=False).mean()
        df['ema21'] = df['close'].ewm(span=21, adjust=False).mean()
        df['ema50'] = df['close'].ewm(span=50, adjust=False).mean()
        
        # 2. 计算MACD
        df['macd'] = df['ema9'] - df['ema21']
        df['signal'] = df['macd'].ewm(span=9, adjust=False).mean()
        df['hist'] = df['macd'] - df['signal']
        
        # 3. 计算RSI
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))
        
        # 4. 计算布林带
        df['sma20'] = df['close'].rolling(window=20).mean()
        df['std20'] = df['close'].rolling(window=20).std()
        df['upper_band'] = df['sma20'] + (df['std20'] * 2)
        df['lower_band'] = df['sma20'] - (df['std20'] * 2)
        
        # 5. 计算成交量指标
        df['volume_sma'] = df['volume'].rolling(window=20).mean()
        df['volume_ratio'] = df['volume'] / df['volume_sma']
        
        # 获取最新数据
        current_price = df['close'].iloc[-1]
        prev_price = df['close'].iloc[-2]
        
        # 交易信号逻辑
        signals = []
        
        # 1. EMA交叉信号
        if df['ema9'].iloc[-1] > df['ema21'].iloc[-1] and df['ema9'].iloc[-2] <= df['ema21'].iloc[-2]:
            signals.append('BUY')
        elif df['ema9'].iloc[-1] < df['ema21'].iloc[-1] and df['ema9'].iloc[-2] >= df['ema21'].iloc[-2]:
            signals.append('SELL')
            
        # 2. MACD信号
        if df['hist'].iloc[-1] > 0 and df['hist'].iloc[-2] <= 0:
            signals.append('BUY')
        elif df['hist'].iloc[-1] < 0 and df['hist'].iloc[-2] >= 0:
            signals.append('SELL')
            
        # 3. RSI超买超卖信号
        if df['rsi'].iloc[-1] < 30:
            signals.append('BUY')
        elif df['rsi'].iloc[-1] > 70:
            signals.append('SELL')
            
        # 4. 布林带突破信号
        if current_price < df['lower_band'].iloc[-1]:
            signals.append('BUY')
        elif current_price > df['upper_band'].iloc[-1]:
            signals.append('SELL')
            
        # 5. 成交量确认
        volume_confirmed = df['volume_ratio'].iloc[-1] > 1.5
        
        # 综合信号判断
        if len(signals) >= 2 and volume_confirmed:  # 至少两个指标同时确认
            # 计算信号强度
            buy_signals = signals.count('BUY')
            sell_signals = signals.count('SELL')
            
            if buy_signals > sell_signals:
                return {
                    'signal': 'BUY',
                    'strength': buy_signals / len(signals),
                    'indicators': {
                        'ema_cross': df['ema9'].iloc[-1] > df['ema21'].iloc[-1],
                        'macd_signal': df['hist'].iloc[-1] > 0,
                        'rsi_signal': df['rsi'].iloc[-1] < 30,
                        'bb_signal': current_price < df['lower_band'].iloc[-1],
                        'volume_confirmed': volume_confirmed
                    }
                }
            elif sell_signals > buy_signals:
                return {
                    'signal': 'SELL',
                    'strength': sell_signals / len(signals),
                    'indicators': {
                        'ema_cross': df['ema9'].iloc[-1] < df['ema21'].iloc[-1],
                        'macd_signal': df['hist'].iloc[-1] < 0,
                        'rsi_signal': df['rsi'].iloc[-1] > 70,
                        'bb_signal': current_price > df['upper_band'].iloc[-1],
                        'volume_confirmed': volume_confirmed
                    }
                }
                
        return None
        
    except Exception as e:
        logger.error(f"Error in high frequency strategy: {str(e)}")
        return None

def calculate_high_frequency_position_size(account_info, market_state, strategy_signal):
    """计算高频交易仓位大小"""
    try:
        total_balance = account_info['total_balance']
        unrealized_pnl = account_info['unrealized_pnl']
        current_positions = account_info['positions']
        
        # 计算当前总持仓价值
        total_position_value = sum(abs(pos['amount'] * pos['mark_price']) for pos in current_positions)
        
        # 基础风险参数
        base_risk = 0.02  # 基础风险2%
        
        # 根据信号强度调整风险
        signal_strength = strategy_signal.get('strength', 0.5)
        adjusted_risk = base_risk * signal_strength
        
        # 根据市场状态调整风险
        if market_state['is_volatile']:
            adjusted_risk *= 0.8  # 高波动市场降低风险
        elif market_state['is_trending']:
            adjusted_risk *= 1.2  # 趋势市场提高风险
            
        # 计算仓位大小
        position_size = total_balance * adjusted_risk
        
        # 设置最小和最大仓位限制
        min_position = 10  # 最小10 USDT
        max_position = total_balance * 0.5  # 最大50%资金
        
        # 确保仓位在合理范围内
        position_size = max(min_position, min(position_size, max_position))
        
        # 计算杠杆倍数
        leverage = calculate_high_frequency_leverage(market_state, strategy_signal)
        
        return {
            'position_size': position_size,
            'leverage': leverage,
            'stop_loss': calculate_high_frequency_stop_loss(market_state, strategy_signal),
            'take_profit': calculate_high_frequency_take_profit(market_state, strategy_signal)
        }
        
    except Exception as e:
        logger.error(f"Error calculating high frequency position size: {str(e)}")
        return None

def calculate_high_frequency_leverage(market_state, strategy_signal):
    """计算高频交易杠杆倍数"""
    try:
        # 基础杠杆
        base_leverage = 20  # 高频交易使用更高杠杆
        
        # 根据信号强度调整杠杆
        signal_strength = strategy_signal.get('strength', 0.5)
        adjusted_leverage = base_leverage * signal_strength
        
        # 根据市场状态调整杠杆
        if market_state['is_volatile']:
            adjusted_leverage *= 0.8
        elif market_state['is_trending']:
            adjusted_leverage *= 1.2
            
        # 确保杠杆在合理范围内
        return max(1, min(50, adjusted_leverage))
        
    except Exception as e:
        logger.error(f"Error calculating high frequency leverage: {str(e)}")
        return 20

def calculate_high_frequency_stop_loss(market_state, strategy_signal):
    """计算高频交易止损价格"""
    try:
        # 基础止损
        base_stop_loss = 0.01  # 1%
        
        # 根据信号强度调整止损
        signal_strength = strategy_signal.get('strength', 0.5)
        adjusted_stop_loss = base_stop_loss * (1 / signal_strength)
        
        # 根据市场状态调整止损
        if market_state['is_volatile']:
            adjusted_stop_loss *= 1.2
        elif market_state['is_trending']:
            adjusted_stop_loss *= 0.8
            
        return adjusted_stop_loss
        
    except Exception as e:
        logger.error(f"Error calculating high frequency stop loss: {str(e)}")
        return 0.01

def calculate_high_frequency_take_profit(market_state, strategy_signal):
    """计算高频交易止盈价格"""
    try:
        # 基础止盈
        base_take_profit = 0.02  # 2%
        
        # 根据信号强度调整止盈
        signal_strength = strategy_signal.get('strength', 0.5)
        adjusted_take_profit = base_take_profit * signal_strength
        
        # 根据市场状态调整止盈
        if market_state['is_volatile']:
            adjusted_take_profit *= 1.2
        elif market_state['is_trending']:
            adjusted_take_profit *= 1.5
            
        return adjusted_take_profit
        
    except Exception as e:
        logger.error(f"Error calculating high frequency take profit: {str(e)}")
        return 0.02

def execute_high_frequency_trade(exchange, symbol, side, quantity, price, strategy_signal=None):
    """执行高频交易"""
    try:
        # 获取账户信息
        account_info = get_account_balance(exchange)
        if not account_info:
            raise Exception("Failed to get account information")
            
        # 分析市场状态
        market_state = analyze_market_conditions(symbol)
        if not market_state:
            raise Exception("Failed to analyze market conditions")
            
        # 计算仓位大小
        position_info = calculate_high_frequency_position_size(account_info, market_state, strategy_signal)
        if not position_info:
            raise Exception("Failed to calculate position size")
            
        # 更新交易参数
        quantity = position_info['position_size'] / price
        
        # 创建交易记录
        trade = TradeHistory(
            exchange=exchange,
            symbol=symbol,
            side=side,
            price=price,
            quantity=quantity,
            status='OPEN',
            strategy='high_frequency',
            strategy_params=json.dumps({
                'leverage': position_info['leverage'],
                'stop_loss': position_info['stop_loss'],
                'take_profit': position_info['take_profit'],
                'market_state': market_state,
                'strategy_signal': strategy_signal
            })
        )
        db.session.add(trade)
        db.session.commit()
        
        # 记录日志
        logger.info(f"执行高频交易: {exchange} {symbol} {side} {quantity}@{price}")
        logger.info(f"交易参数: {position_info}")
        
        return trade
        
    except Exception as e:
        logger.error(f"执行高频交易失败: {str(e)}")
        db.session.rollback()
        return None

@app.route('/high-frequency')
def high_frequency():
    try:
        # 获取当前设置
        settings = {
            'trading_pair': os.getenv('TRADING_PAIR', 'BTCUSDT'),
            'leverage': os.getenv('LEVERAGE', '20'),
            'min_position': os.getenv('MIN_POSITION', '10'),
            'max_position': os.getenv('MAX_POSITION', '1000'),
            'stop_loss': os.getenv('STOP_LOSS_PERCENTAGE', '1'),
            'take_profit': os.getenv('TAKE_PROFIT_PERCENTAGE', '2'),
            'max_daily_trades': os.getenv('MAX_DAILY_TRADES', '1000')
        }
        
        # 获取最近的交易记录
        trades = TradeHistory.query.filter_by(strategy='high_frequency').order_by(TradeHistory.timestamp.desc()).limit(50).all()
        
        return render_template('high_frequency.html', settings=settings, trades=trades)
    except Exception as e:
        logger.error(f"Error loading high frequency page: {str(e)}")
        return render_template('error.html', error="加载高频交易页面时出错")

@app.route('/api/high-frequency/start', methods=['POST'])
@handle_errors
@log_request
@validate_params('exchange', 'trading_pair', 'leverage', 'quantity')
def start_high_frequency_trading():
    try:
        # 获取当前选择的交易所
        exchange = request.json.get('exchange', os.getenv('CURRENT_EXCHANGE', 'binance'))
        
        # 根据选择的交易所初始化API客户端
        if exchange == 'binance':
            api_key = os.getenv('BINANCE_API_KEY')
            api_secret = os.getenv('BINANCE_API_SECRET')
        else:  # lbank
            api_key = os.getenv('LBANK_API_KEY')
            api_secret = os.getenv('LBANK_API_SECRET')
            
        if not all([api_key, api_secret]):
            return api_response(
                success=False,
                error="API密钥未配置",
                message="请先配置API密钥",
                status_code=400
            )
            
        # 启动高频交易
        success = start_high_frequency_trading_process(exchange)
        if success:
            return api_response(
                message="高频交易已启动"
            )
        else:
            return api_response(
                success=False,
                error="启动失败",
                message="无法启动高频交易",
                status_code=400
            )
    except Exception as e:
        logger.error(f"Error starting high frequency trading: {str(e)}")
        return api_response(
            success=False,
            error=str(e),
            message="启动高频交易失败",
            status_code=500
        )

@app.route('/api/high-frequency/stop', methods=['POST'])
@handle_errors
@log_request
def stop_high_frequency_trading():
    try:
        success = stop_high_frequency_trading_process()
        if success:
            return api_response(
                message="高频交易已停止"
            )
        else:
            return api_response(
                success=False,
                error="停止失败",
                message="无法停止高频交易",
                status_code=400
            )
    except Exception as e:
        logger.error(f"Error stopping high frequency trading: {str(e)}")
        return api_response(
            success=False,
            error=str(e),
            message="停止高频交易失败",
            status_code=500
        )

@app.route('/api/high-frequency/status')
@handle_errors
@log_request
def get_high_frequency_status():
    try:
        status = get_high_frequency_trading_status()
        return api_response(
            data=status
        )
    except Exception as e:
        logger.error(f"Error getting high frequency status: {str(e)}")
        return api_response(
            success=False,
            error=str(e),
            message="获取高频交易状态失败",
            status_code=500
        )

@app.route('/api/high-frequency/trade', methods=['POST'])
@handle_errors
@log_request
@validate_params('exchange', 'symbol', 'side', 'quantity', 'price', 'strategy_signal')
def execute_high_frequency_trade_api():
    try:
        data = request.json
        if not data:
            return api_response(
                success=False,
                error="无效的请求数据",
                message="请提供有效的JSON数据",
                status_code=400
            )
            
        exchange = data.get('exchange', os.getenv('CURRENT_EXCHANGE', 'Binance'))
        symbol = data.get('symbol', os.getenv('TRADING_PAIR', 'BTCUSDT'))
        side = data.get('side')
        quantity = data.get('quantity')
        price = data.get('price')
        strategy_signal = data.get('strategy_signal')
        
        if not all([exchange, symbol, side, quantity, price]):
            return api_response(
                success=False,
                error="缺少必要参数",
                message="请提供所有必要的交易参数",
                status_code=400
            )
            
        # 执行高频交易
        trade = execute_high_frequency_trade(exchange, symbol, side, quantity, price, strategy_signal)
        
        if trade:
            return api_response(
                data={
                    'trade': {
                        'id': trade.id,
                        'exchange': trade.exchange,
                        'symbol': trade.symbol,
                        'side': trade.side,
                        'price': trade.price,
                        'quantity': trade.quantity,
                        'timestamp': trade.timestamp.isoformat(),
                        'status': trade.status,
                        'strategy': trade.strategy,
                        'strategy_params': trade.strategy_params
                    }
                }
            )
        else:
            return api_response(
                success=False,
                error="交易执行失败",
                message="无法执行高频交易",
                status_code=500
            )
    except Exception as e:
        logger.error(f"Error executing high frequency trade: {str(e)}")
        return api_response(
            success=False,
            error=str(e),
            message="执行高频交易失败",
            status_code=500
        )

# 添加机器人配置相关的API
@app.route('/api/trading-bots', methods=['GET'])
@handle_errors
@log_request
def get_trading_bots():
    try:
        bots = TradingBotConfig.query.all()
        
        return api_response(
            data={
                'bots': [{
                    'id': bot.id,
                    'name': bot.name,
                    'exchange': bot.exchange,
                    'trading_pair': bot.trading_pair,
                    'status': bot.status,
                    'strategies': json.loads(bot.strategies),
                    'funds': bot.funds,
                    'leverage': bot.leverage,
                    'stop_loss': bot.stop_loss,
                    'take_profit': bot.take_profit,
                    'max_daily_trades': bot.max_daily_trades,
                    'performance': json.loads(bot.performance) if bot.performance else None
                } for bot in bots]
            }
        )
    except Exception as e:
        logger.error(f"Error getting trading bots: {str(e)}")
        return api_response(
            success=False,
            error=str(e),
            message="获取交易机器人列表失败",
            status_code=500
        )

@app.route('/api/trading-bots', methods=['POST'])
@handle_errors
@log_request
@validate_params('name', 'exchange', 'trading_pair', 'strategies', 'funds', 'leverage', 'stop_loss', 'take_profit', 'max_daily_trades')
def create_trading_bot_api():
    try:
        data = request.json
        
        # 验证数据
        if not validate_bot_data(data):
            return api_response(
                success=False,
                error="无效的机器人参数",
                message="请检查机器人参数是否正确",
                status_code=400
            )
        
        # 创建新的交易机器人配置
        new_bot = TradingBotConfig(
            name=data['name'],
            exchange=data['exchange'],
            trading_pair=data['trading_pair'],
            status='STOPPED',
            strategies=json.dumps(data['strategies']),
            funds=data['funds'],
            leverage=data['leverage'],
            stop_loss=data['stop_loss'],
            take_profit=data['take_profit'],
            max_daily_trades=data['max_daily_trades']
        )
        
        db.session.add(new_bot)
        db.session.commit()
        
        return api_response(
            message="交易机器人创建成功"
        )
    except Exception as e:
        logger.error(f"Error creating trading bot: {str(e)}")
        db.session.rollback()
        return api_response(
            success=False,
            error=str(e),
            message="创建交易机器人失败",
            status_code=500
        )

@app.route('/api/trading-bots/<int:bot_id>', methods=['GET'])
def get_trading_bot(bot_id):
    try:
        bot = TradingBotConfig.query.get(bot_id)
        if not bot:
            return api_response(
                success=False,
                error="机器人不存在",
                message="找不到指定的机器人",
                status_code=404
            )
        
        return api_response(
            data={
                'id': bot.id,
                'name': bot.name,
                'exchange': bot.exchange,
                'trading_pair': bot.trading_pair,
                'status': bot.status,
                'strategies': json.loads(bot.strategies) if bot.strategies else [],
                'funds': bot.funds,
                'leverage': bot.leverage,
                'stop_loss': bot.stop_loss,
                'take_profit': bot.take_profit,
                'max_daily_trades': bot.max_daily_trades,
                'performance': json.loads(bot.performance) if bot.performance else None
            }
        )
    except Exception as e:
        logger.error(f"Error getting trading bot: {str(e)}")
        return api_response(
            success=False,
            error=str(e),
            message="获取机器人信息失败",
            status_code=500
        )

@app.route('/api/trading-bots/<int:bot_id>', methods=['PUT'])
def update_trading_bot(bot_id):
    try:
        data = request.json
        
        # 验证数据
        if not validate_bot_data(data):
            return api_response(
                success=False,
                error="无效的机器人参数",
                message="请检查机器人参数是否正确",
                status_code=400
            )
        
        # 检查机器人是否存在
        bot = TradingBotConfig.query.get(bot_id)
        if not bot:
            return api_response(
                success=False,
                error="机器人不存在",
                message="找不到指定的机器人",
                status_code=404
            )
        
        # 更新机器人配置
        bot.name = data['name']
        bot.exchange = data['exchange']
        bot.trading_pair = data['trading_pair']
        bot.strategies = json.dumps(data['strategies'])
        bot.funds = data['funds']
        bot.leverage = data['leverage']
        bot.stop_loss = data['stop_loss']
        bot.take_profit = data['take_profit']
        bot.max_daily_trades = data['max_daily_trades']
        
        db.session.commit()
        
        return api_response(
            message="机器人配置已更新"
        )
    except Exception as e:
        logger.error(f"Error updating trading bot: {str(e)}")
        db.session.rollback()
        return api_response(
            success=False,
            error=str(e),
            message="更新机器人配置失败",
            status_code=500
        )

@app.route('/api/trading-bots/<int:bot_id>', methods=['DELETE'])
def delete_trading_bot(bot_id):
    try:
        # 检查机器人是否存在
        bot = TradingBotConfig.query.get(bot_id)
        if not bot:
            return api_response(
                success=False,
                error="机器人不存在",
                message="找不到指定的机器人",
                status_code=404
            )
        
        # 检查机器人是否在运行
        if bot.status == 'RUNNING':
            return api_response(
                success=False,
                error="请先停止机器人",
                message="无法删除正在运行的机器人",
                status_code=400
            )
        
        # 删除机器人
        db.session.delete(bot)
        db.session.commit()
        
        return api_response(
            message="机器人已删除"
        )
    except Exception as e:
        logger.error(f"Error deleting trading bot: {str(e)}")
        db.session.rollback()
        return api_response(
            success=False,
            error=str(e),
            message="删除机器人失败",
            status_code=500
        )

def validate_bot_data(data):
    """验证机器人参数是否有效"""
    required_fields = [
        'name', 'exchange', 'trading_pair', 'funds', 'leverage',
        'stop_loss', 'take_profit', 'max_daily_trades', 'strategies'
    ]
    
    # 检查必需字段
    if not all(field in data for field in required_fields):
        return False
    
    # 检查数值范围
    if not (100 <= data['funds'] <= 1000000):
        return False
    if not (1 <= data['leverage'] <= 50):
        return False
    if not (0.1 <= data['stop_loss'] <= 5):
        return False
    if not (0.1 <= data['take_profit'] <= 10):
        return False
    if not (10 <= data['max_daily_trades'] <= 1000):
        return False
    
    # 检查策略设置
    if not isinstance(data['strategies'], dict):
        return False
    
    # 检查是否至少启用了一个策略
    enabled_strategies = [s for s in data['strategies'].values() if s.get('enabled')]
    if not enabled_strategies:
        return False
    
    return True

# 初始化机器人管理器
bot_manager = trading_bot_manager

@app.route('/api/bot/start/<int:bot_id>', methods=['POST'])
@handle_errors
@log_request
def start_bot(bot_id):
    """启动交易机器人"""
    try:
        success = bot_manager.start_bot(bot_id)
        if success:
            return api_response(
                message="机器人启动成功"
            )
        else:
            return api_response(
                success=False,
                error="启动失败",
                message="无法启动机器人",
                status_code=400
            )
    except Exception as e:
        logger.error(f"Error starting bot {bot_id}: {str(e)}")
        return api_response(
            success=False,
            error=str(e),
            message="启动机器人失败",
            status_code=500
        )

@app.route('/api/bot/stop/<int:bot_id>', methods=['POST'])
@handle_errors
@log_request
def stop_bot(bot_id):
    """停止交易机器人"""
    try:
        success = bot_manager.stop_bot(bot_id)
        if success:
            return api_response(
                message="机器人停止成功"
            )
        else:
            return api_response(
                success=False,
                error="停止失败",
                message="无法停止机器人",
                status_code=400
            )
    except Exception as e:
        logger.error(f"Error stopping bot {bot_id}: {str(e)}")
        return api_response(
            success=False,
            error=str(e),
            message="停止机器人失败",
            status_code=500
        )

@app.route('/api/bot/performance/<int:bot_id>')
@handle_errors
@log_request
def get_bot_performance(bot_id):
    """获取机器人性能统计"""
    try:
        performance = bot_manager.get_bot_performance(bot_id)
        if performance:
            return api_response(
                data=performance
            )
        else:
            return api_response(
                success=False,
                error="获取性能数据失败",
                message="无法获取机器人性能数据",
                status_code=400
            )
    except Exception as e:
        logger.error(f"Error getting performance for bot {bot_id}: {str(e)}")
        return api_response(
            success=False,
            error=str(e),
            message="获取性能数据失败",
            status_code=500
        )

@app.route('/api/bot/status/<int:bot_id>')
def get_bot_status(bot_id):
    """获取机器人状态"""
    try:
        bot = TradingBotConfig.query.get(bot_id)
        if not bot:
            return api_response(
                success=False,
                error="机器人不存在",
                message="找不到指定的机器人",
                status_code=404
            )
            
        performance = bot_manager.get_bot_performance(bot_id)
        
        return api_response(
            data={
                'id': bot.id,
                'name': bot.name,
                'exchange': bot.exchange,
                'trading_pair': bot.trading_pair,
                'status': bot.status,
                'strategies': bot.strategies,
                'funds': bot.funds,
                'performance': performance
            }
        )
    except Exception as e:
        logger.error(f"Error getting bot status: {str(e)}")
        return api_response(
            success=False,
            error=str(e),
            message="获取机器人状态失败",
            status_code=500
        )

@app.route('/api/high-frequency/settings', methods=['POST'])
def update_high_frequency_settings():
    try:
        settings = request.json
        
        # 验证设置
        if not validate_settings(settings):
            return jsonify({'success': False, 'error': '无效的设置参数'})
        
        # 保存设置到数据库
        db = get_db()
        db.execute('''
            INSERT OR REPLACE INTO high_frequency_settings (
                exchange, trading_pair, leverage, stop_loss, take_profit,
                max_daily_trades, total_funds, strategies
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            settings['exchange'],
            settings['trading_pair'],
            settings['leverage'],
            settings['stop_loss'],
            settings['take_profit'],
            settings['max_daily_trades'],
            settings['total_funds'],
            json.dumps(settings['strategies'])
        ))
        db.commit()
        
        # 保存设置到配置文件
        with open('strategy_config.json', 'w') as f:
            json.dump(settings, f, indent=4)
        
        # 更新环境变量
        os.environ['CURRENT_EXCHANGE'] = settings['exchange']
        
        return jsonify({'success': True, 'message': '设置已更新'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# 路由：交易机器人页面
@app.route('/trading-bots')
def trading_bots():
    try:
        # 获取所有交易机器人
        bots = TradingBotConfig.query.all()
        return render_template('trading_bots.html', bots=bots)
    except Exception as e:
        logger.error(f"Error loading trading bots page: {str(e)}")
        return render_template('error.html', error=str(e)), 500

# 路由：创建交易机器人页面
@app.route('/trading-bots/create')
def create_trading_bot_page_view():
    try:
        return render_template('create_trading_bot.html')
    except Exception as e:
        logger.error(f"Error loading create trading bot page: {str(e)}")
        return render_template('error.html', error=str(e)), 500

# 路由：单个交易机器人页面
@app.route('/trading-bots/<int:bot_id>')
def trading_bot_detail(bot_id):
    try:
        bot = TradingBotConfig.query.get_or_404(bot_id)
        # 获取机器人的交易历史
        trades = TradeHistory.query.filter_by(bot_id=bot_id).order_by(TradeHistory.timestamp.desc()).limit(50).all()
        # 获取策略设置
        settings = {
            'rsi_period': 14,
            'rsi_overbought': 70,
            'rsi_oversold': 30,
            'bb_period': 20,
            'bb_std': 2.0,
            'supertrend_atr_period': 10,
            'supertrend_atr_multiplier': 3.0,
            'grid_count': 10,
            'grid_spacing': 0.5
        }
        return render_template('trading_bot.html', bot=bot, trades=trades, settings=settings)
    except Exception as e:
        logger.error(f"Error loading trading bot detail page: {str(e)}")
        return render_template('error.html', error=str(e)), 500

@app.route('/api/bot/logs/<int:bot_id>')
@handle_errors
@log_request
def get_bot_logs(bot_id):
    try:
        logs = TradingBotLog.query.filter_by(bot_id=bot_id).order_by(TradingBotLog.created_at.desc()).limit(100).all()
        
        return api_response(
            data={
                'logs': [{
                    'action': log.action,
                    'details': log.details,
                    'timestamp': log.created_at.isoformat()
                } for log in logs]
            }
        )
    except Exception as e:
        logger.error(f"Error getting bot logs: {str(e)}")
        return api_response(
            success=False,
            error=str(e),
            message="获取机器人日志失败",
            status_code=500
        )

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True) 