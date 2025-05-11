import os
import time
from datetime import datetime
import pandas as pd
import numpy as np
from binance.client import Client
from binance.enums import *
from dotenv import load_dotenv
import ta
import logging
from typing import List, Dict, Tuple

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('trading.log'),
        logging.StreamHandler()
    ]
)

# 加载环境变量
load_dotenv()

class GridLevel:
    def __init__(self, price: float, side: str, quantity: float):
        self.price = price
        self.side = side
        self.quantity = quantity
        self.order_id = None
        self.filled = False

class BinanceTradingBot:
    def __init__(self):
        self.api_key = os.getenv('BINANCE_API_KEY')
        self.api_secret = os.getenv('BINANCE_API_SECRET')
        self.trading_pair = os.getenv('TRADING_PAIR')
        self.leverage = int(os.getenv('LEVERAGE'))
        self.quantity = float(os.getenv('QUANTITY'))
        self.stop_loss_percentage = float(os.getenv('STOP_LOSS_PERCENTAGE'))
        self.take_profit_percentage = float(os.getenv('TAKE_PROFIT_PERCENTAGE'))
        self.max_daily_trades = int(os.getenv('MAX_DAILY_TRADES'))
        self.max_daily_loss_percentage = float(os.getenv('MAX_DAILY_LOSS_PERCENTAGE'))
        self.min_volume_threshold = float(os.getenv('MIN_VOLUME_THRESHOLD'))
        self.grid_size = int(os.getenv('GRID_SIZE'))
        self.grid_spacing = float(os.getenv('GRID_SPACING'))
        self.trend_ema_fast = int(os.getenv('TREND_EMA_FAST'))
        self.trend_ema_slow = int(os.getenv('TREND_EMA_SLOW'))
        self.scalping_profit_target = float(os.getenv('SCALPING_PROFIT_TARGET'))
        self.scalping_stop_loss = float(os.getenv('SCALPING_STOP_LOSS'))
        
        # 初始化币安客户端
        self.client = Client(self.api_key, self.api_secret)
        
        # 设置杠杆
        self.set_leverage()
        
        # 初始化交易状态
        self.position = None
        self.entry_price = None
        self.daily_trades = 0
        self.daily_pnl = 0
        self.last_trade_time = None
        self.initial_balance = self.get_account_balance()
        self.grid_levels: List[GridLevel] = []
        self.active_orders: Dict[str, Dict] = {}
        
        logging.info(f"交易机器人初始化完成 - 初始余额: {self.initial_balance} USDT")

    def get_account_balance(self):
        """获取账户余额"""
        try:
            account = self.client.futures_account_balance()
            for balance in account:
                if balance['asset'] == 'USDT':
                    return float(balance['balance'])
            return 0
        except Exception as e:
            logging.error(f"获取账户余额失败: {e}")
            return 0

    def set_leverage(self):
        """设置合约杠杆"""
        try:
            self.client.futures_change_leverage(
                symbol=self.trading_pair,
                leverage=self.leverage
            )
            logging.info(f"杠杆设置成功: {self.leverage}x")
        except Exception as e:
            logging.error(f"设置杠杆失败: {e}")

    def get_historical_data(self, interval='1m', limit=100):
        """获取历史K线数据"""
        try:
            klines = self.client.futures_klines(
                symbol=self.trading_pair,
                interval=interval,
                limit=limit
            )
            
            df = pd.DataFrame(klines, columns=[
                'timestamp', 'open', 'high', 'low', 'close', 'volume',
                'close_time', 'quote_volume', 'trades', 'taker_buy_base',
                'taker_buy_quote', 'ignore'
            ])
            
            df['close'] = df['close'].astype(float)
            df['high'] = df['high'].astype(float)
            df['low'] = df['low'].astype(float)
            df['volume'] = df['volume'].astype(float)
            
            return df
        except Exception as e:
            logging.error(f"获取历史数据失败: {e}")
            return None

    def calculate_indicators(self, df):
        """计算技术指标"""
        try:
            # 趋势指标
            df['ema_fast'] = ta.trend.EMAIndicator(df['close'], window=self.trend_ema_fast).ema_indicator()
            df['ema_slow'] = ta.trend.EMAIndicator(df['close'], window=self.trend_ema_slow).ema_indicator()
            
            # RSI
            df['rsi'] = ta.momentum.RSIIndicator(df['close']).rsi()
            
            # MACD
            macd = ta.trend.MACD(df['close'])
            df['macd'] = macd.macd()
            df['macd_signal'] = macd.macd_signal()
            
            # 布林带
            bollinger = ta.volatility.BollingerBands(df['close'])
            df['bb_high'] = bollinger.bollinger_hband()
            df['bb_low'] = bollinger.bollinger_lband()
            df['bb_mid'] = bollinger.bollinger_mavg()
            
            # 成交量指标
            df['volume_ma'] = df['volume'].rolling(window=20).mean()
            
            # 价格动量
            df['momentum'] = df['close'].pct_change(periods=10)
            
            # 波动率
            df['volatility'] = df['close'].rolling(window=20).std()
            
            # ATR (Average True Range)
            df['atr'] = ta.volatility.AverageTrueRange(df['high'], df['low'], df['close']).average_true_range()
            
            return df
        except Exception as e:
            logging.error(f"计算指标失败: {e}")
            return None

    def check_trend(self, df) -> str:
        """检查趋势方向"""
        try:
            current_price = df['close'].iloc[-1]
            ema_fast = df['ema_fast'].iloc[-1]
            ema_slow = df['ema_slow'].iloc[-1]
            
            if current_price > ema_fast > ema_slow:
                return 'UPTREND'
            elif current_price < ema_fast < ema_slow:
                return 'DOWNTREND'
            else:
                return 'SIDEWAYS'
        except Exception as e:
            logging.error(f"检查趋势失败: {e}")
            return 'UNKNOWN'

    def setup_grid(self, current_price: float):
        """设置网格交易水平"""
        try:
            self.grid_levels.clear()
            grid_range = self.grid_size * self.grid_spacing / 100
            
            for i in range(self.grid_size):
                # 买入网格
                buy_price = current_price * (1 - (i + 1) * self.grid_spacing / 100)
                self.grid_levels.append(GridLevel(buy_price, 'BUY', self.quantity))
                
                # 卖出网格
                sell_price = current_price * (1 + (i + 1) * self.grid_spacing / 100)
                self.grid_levels.append(GridLevel(sell_price, 'SELL', self.quantity))
            
            # 放置网格订单
            self.place_grid_orders()
            
        except Exception as e:
            logging.error(f"设置网格失败: {e}")

    def place_grid_orders(self):
        """放置网格订单"""
        try:
            for level in self.grid_levels:
                if not level.filled:
                    order = self.client.futures_create_order(
                        symbol=self.trading_pair,
                        side=level.side,
                        type='LIMIT',
                        timeInForce='GTC',
                        quantity=level.quantity,
                        price=level.price
                    )
                    level.order_id = order['orderId']
                    self.active_orders[order['orderId']] = {
                        'price': level.price,
                        'side': level.side,
                        'quantity': level.quantity
                    }
                    logging.info(f"网格订单放置成功: {level.side} @ {level.price}")
        except Exception as e:
            logging.error(f"放置网格订单失败: {e}")

    def check_scalping_opportunity(self, df) -> Tuple[bool, str]:
        """检查剥头皮交易机会"""
        try:
            current_price = df['close'].iloc[-1]
            rsi = df['rsi'].iloc[-1]
            bb_low = df['bb_low'].iloc[-1]
            bb_high = df['bb_high'].iloc[-1]
            
            # 超卖条件
            if rsi < 30 and current_price < bb_low:
                return True, 'BUY'
            
            # 超买条件
            if rsi > 70 and current_price > bb_high:
                return True, 'SELL'
            
            return False, None
        except Exception as e:
            logging.error(f"检查剥头皮机会失败: {e}")
            return False, None

    def execute_scalping_trade(self, side: str):
        """执行剥头皮交易"""
        try:
            # 获取当前价格
            ticker = self.client.futures_symbol_ticker(symbol=self.trading_pair)
            current_price = float(ticker['price'])
            
            # 计算止盈止损价格
            if side == 'BUY':
                take_profit = current_price * (1 + self.scalping_profit_target / 100)
                stop_loss = current_price * (1 - self.scalping_stop_loss / 100)
            else:
                take_profit = current_price * (1 - self.scalping_profit_target / 100)
                stop_loss = current_price * (1 + self.scalping_stop_loss / 100)
            
            # 执行交易
            order = self.client.futures_create_order(
                symbol=self.trading_pair,
                side=side,
                type='MARKET',
                quantity=self.quantity
            )
            
            # 设置止盈止损
            self.client.futures_create_order(
                symbol=self.trading_pair,
                side='SELL' if side == 'BUY' else 'BUY',
                type='TAKE_PROFIT_MARKET',
                stopPrice=take_profit,
                closePosition=True
            )
            
            self.client.futures_create_order(
                symbol=self.trading_pair,
                side='SELL' if side == 'BUY' else 'BUY',
                type='STOP_MARKET',
                stopPrice=stop_loss,
                closePosition=True
            )
            
            logging.info(f"剥头皮交易执行成功: {side} @ {current_price}")
            
        except Exception as e:
            logging.error(f"执行剥头皮交易失败: {e}")

    def run(self):
        """运行交易机器人"""
        logging.info("交易机器人启动...")
        last_reset_time = datetime.now().date()
        
        while True:
            try:
                current_time = datetime.now()
                
                # 检查是否需要重置每日统计
                if current_time.date() != last_reset_time:
                    self.reset_daily_stats()
                    last_reset_time = current_time.date()
                
                # 获取市场数据
                df = self.get_historical_data()
                if df is None:
                    time.sleep(60)
                    continue
                
                df = self.calculate_indicators(df)
                if df is None:
                    time.sleep(60)
                    continue
                
                # 检查趋势
                trend = self.check_trend(df)
                
                # 检查剥头皮机会
                scalping_opportunity, scalping_side = self.check_scalping_opportunity(df)
                
                if scalping_opportunity and trend != 'SIDEWAYS':
                    self.execute_scalping_trade(scalping_side)
                
                # 更新网格
                if not self.grid_levels:
                    current_price = df['close'].iloc[-1]
                    self.setup_grid(current_price)
                
                # 检查网格订单状态
                self.check_grid_orders()
                
                # 等待15秒
                time.sleep(15)
                
            except Exception as e:
                logging.error(f"运行错误: {e}")
                time.sleep(60)

    def check_grid_orders(self):
        """检查网格订单状态"""
        try:
            for order_id, order_info in list(self.active_orders.items()):
                order_status = self.client.futures_get_order(
                    symbol=self.trading_pair,
                    orderId=order_id
                )
                
                if order_status['status'] == 'FILLED':
                    # 订单已成交，执行对冲订单
                    self.execute_hedge_order(order_info)
                    del self.active_orders[order_id]
                    
                    # 更新网格水平
                    for level in self.grid_levels:
                        if level.order_id == order_id:
                            level.filled = True
                            break
                    
                    # 放置新的网格订单
                    self.place_grid_orders()
                    
        except Exception as e:
            logging.error(f"检查网格订单状态失败: {e}")

    def execute_hedge_order(self, order_info: Dict):
        """执行对冲订单"""
        try:
            hedge_side = 'SELL' if order_info['side'] == 'BUY' else 'BUY'
            self.client.futures_create_order(
                symbol=self.trading_pair,
                side=hedge_side,
                type='MARKET',
                quantity=order_info['quantity']
            )
            logging.info(f"对冲订单执行成功: {hedge_side} @ {order_info['price']}")
        except Exception as e:
            logging.error(f"执行对冲订单失败: {e}")

    def reset_daily_stats(self):
        """重置每日统计数据"""
        self.daily_trades = 0
        self.daily_pnl = 0
        self.initial_balance = self.get_account_balance()
        logging.info("每日统计数据已重置")

if __name__ == "__main__":
    bot = BinanceTradingBot()
    bot.run() 