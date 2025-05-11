import os
import time
import json
import hmac
import hashlib
import requests
import websocket
import pandas as pd
import numpy as np
from datetime import datetime
from dotenv import load_dotenv
import talib
import logging
from typing import Dict, List, Optional

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('trading_bot.log'),
        logging.StreamHandler()
    ]
)

class LBankTradingBot:
    def __init__(self):
        # 加载环境变量
        load_dotenv()
        
        # API配置
        self.api_key = os.getenv('LBANK_API_KEY')
        self.secret_key = os.getenv('LBANK_SECRET_KEY')
        self.base_url = 'https://api.lbank.info/v2'
        self.ws_url = 'wss://www.lbank.info/ws/V2/'
        
        # 交易配置
        self.trading_pair = os.getenv('TRADING_PAIR')
        self.leverage = int(os.getenv('LEVERAGE'))
        self.position_size = float(os.getenv('POSITION_SIZE'))
        self.max_positions = int(os.getenv('MAX_POSITIONS'))
        
        # 风险控制参数
        self.max_drawdown = float(os.getenv('MAX_DRAWDOWN'))
        self.daily_loss_limit = float(os.getenv('DAILY_LOSS_LIMIT'))
        self.max_leverage = int(os.getenv('MAX_LEVERAGE'))
        
        # 策略参数
        self.fast_ema = int(os.getenv('FAST_EMA'))
        self.slow_ema = int(os.getenv('SLOW_EMA'))
        self.rsi_period = int(os.getenv('RSI_PERIOD'))
        self.rsi_overbought = int(os.getenv('RSI_OVERBOUGHT'))
        self.rsi_oversold = int(os.getenv('RSI_OVERSOLD'))
        self.bb_period = int(os.getenv('BB_PERIOD'))
        self.bb_std = float(os.getenv('BB_STD'))
        
        # 高频交易参数
        self.min_volume = float(os.getenv('MIN_VOLUME'))
        self.price_change_threshold = float(os.getenv('PRICE_CHANGE_THRESHOLD'))
        self.execution_interval = float(os.getenv('EXECUTION_INTERVAL'))
        
        # 初始化数据存储
        self.klines = []
        self.positions = []
        self.trades_history = []
        self.daily_pnl = 0.0
        
        # 初始化WebSocket连接
        self.ws = None
        self.connect_websocket()
        
    def connect_websocket(self):
        """建立WebSocket连接"""
        def on_message(ws, message):
            try:
                data = json.loads(message)
                self.handle_websocket_message(data)
            except Exception as e:
                logging.error(f"WebSocket message error: {e}")
                
        def on_error(ws, error):
            logging.error(f"WebSocket error: {error}")
            
        def on_close(ws, close_status_code, close_msg):
            logging.info("WebSocket connection closed")
            
        def on_open(ws):
            logging.info("WebSocket connection established")
            # 订阅K线数据
            subscribe_msg = {
                "action": "subscribe",
                "pair": self.trading_pair,
                "type": "kbar",
                "size": 100
            }
            ws.send(json.dumps(subscribe_msg))
            
        self.ws = websocket.WebSocketApp(
            self.ws_url,
            on_message=on_message,
            on_error=on_error,
            on_close=on_close,
            on_open=on_open
        )
        
    def handle_websocket_message(self, data: Dict):
        """处理WebSocket消息"""
        if 'data' in data:
            self.update_klines(data['data'])
            self.analyze_market()
            
    def update_klines(self, kline_data: List):
        """更新K线数据"""
        self.klines = kline_data
        if len(self.klines) > 100:
            self.klines = self.klines[-100:]
            
    def analyze_market(self):
        """分析市场并生成交易信号"""
        if len(self.klines) < 100:
            return
            
        # 计算技术指标
        df = pd.DataFrame(self.klines)
        close_prices = df['close'].astype(float)
        
        # 计算EMA
        fast_ema = talib.EMA(close_prices, timeperiod=self.fast_ema)
        slow_ema = talib.EMA(close_prices, timeperiod=self.slow_ema)
        
        # 计算RSI
        rsi = talib.RSI(close_prices, timeperiod=self.rsi_period)
        
        # 计算布林带
        upper, middle, lower = talib.BBANDS(
            close_prices,
            timeperiod=self.bb_period,
            nbdevup=self.bb_std,
            nbdevdn=self.bb_std
        )
        
        # 生成交易信号
        current_price = float(close_prices.iloc[-1])
        current_rsi = float(rsi.iloc[-1])
        
        # 趋势信号
        trend_signal = 0
        if fast_ema.iloc[-1] > slow_ema.iloc[-1]:
            trend_signal = 1
        elif fast_ema.iloc[-1] < slow_ema.iloc[-1]:
            trend_signal = -1
            
        # 超买超卖信号
        rsi_signal = 0
        if current_rsi < self.rsi_oversold:
            rsi_signal = 1
        elif current_rsi > self.rsi_overbought:
            rsi_signal = -1
            
        # 布林带信号
        bb_signal = 0
        if current_price < lower.iloc[-1]:
            bb_signal = 1
        elif current_price > upper.iloc[-1]:
            bb_signal = -1
            
        # 综合信号
        if trend_signal == 1 and rsi_signal == 1 and bb_signal == 1:
            self.execute_trade('buy')
        elif trend_signal == -1 and rsi_signal == -1 and bb_signal == -1:
            self.execute_trade('sell')
            
    def execute_trade(self, side: str):
        """执行交易"""
        if len(self.positions) >= self.max_positions:
            return
            
        # 检查风险限制
        if not self.check_risk_limits():
            return
            
        # 构建订单参数
        order_params = {
            'api_key': self.api_key,
            'symbol': self.trading_pair,
            'type': side,
            'amount': self.position_size,
            'leverage': self.leverage
        }
        
        # 添加签名
        order_params['sign'] = self.generate_signature(order_params)
        
        try:
            # 发送订单
            response = requests.post(
                f"{self.base_url}/order/create",
                json=order_params
            )
            
            if response.status_code == 200:
                order_data = response.json()
                if order_data['result']:
                    self.positions.append({
                        'order_id': order_data['order_id'],
                        'side': side,
                        'price': float(order_data['price']),
                        'amount': self.position_size,
                        'timestamp': datetime.now().timestamp()
                    })
                    logging.info(f"Order executed: {side} {self.position_size} {self.trading_pair}")
                else:
                    logging.error(f"Order failed: {order_data['error']}")
            else:
                logging.error(f"API request failed: {response.status_code}")
                
        except Exception as e:
            logging.error(f"Trade execution error: {e}")
            
    def check_risk_limits(self) -> bool:
        """检查风险限制"""
        # 检查日亏损限制
        if self.daily_pnl < -self.daily_loss_limit:
            logging.warning("Daily loss limit reached")
            return False
            
        # 检查最大回撤
        if self.calculate_drawdown() > self.max_drawdown:
            logging.warning("Maximum drawdown reached")
            return False
            
        return True
        
    def calculate_drawdown(self) -> float:
        """计算当前回撤"""
        if not self.trades_history:
            return 0.0
            
        peak = max(trade['pnl'] for trade in self.trades_history)
        current = self.trades_history[-1]['pnl']
        return (peak - current) / peak if peak > 0 else 0.0
        
    def generate_signature(self, params: Dict) -> str:
        """生成API签名"""
        sorted_params = sorted(params.items(), key=lambda x: x[0])
        sign_str = '&'.join([f"{k}={v}" for k, v in sorted_params])
        return hmac.new(
            self.secret_key.encode(),
            sign_str.encode(),
            hashlib.sha256
        ).hexdigest()
        
    def run(self):
        """运行交易机器人"""
        try:
            # 启动WebSocket连接
            self.ws.run_forever()
        except KeyboardInterrupt:
            logging.info("Trading bot stopped by user")
        except Exception as e:
            logging.error(f"Trading bot error: {e}")
        finally:
            if self.ws:
                self.ws.close()
                
if __name__ == "__main__":
    bot = LBankTradingBot()
    bot.run() 