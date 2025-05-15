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
import ccxt
import json
from flask_sqlalchemy import SQLAlchemy
from app import db, TradeHistory

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('trading_bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

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
        # 获取当前选择的交易所
        self.exchange_name = os.getenv('CURRENT_EXCHANGE', 'binance')
        
        # 初始化交易所
        if self.exchange_name == 'binance':
            self.exchange = ccxt.binance({
                'apiKey': os.getenv('BINANCE_API_KEY'),
                'secret': os.getenv('BINANCE_API_SECRET'),
                'enableRateLimit': True,
                'options': {
                    'defaultType': 'future'
                }
            })
        elif self.exchange_name == 'lbank':
            self.exchange = ccxt.lbank({
                'apiKey': os.getenv('LBANK_API_KEY'),
                'secret': os.getenv('LBANK_API_SECRET'),
                'enableRateLimit': True
            })
        else:
            raise ValueError(f"不支持的交易所: {self.exchange_name}")
        
        # 加载交易设置
        self.trading_pair = os.getenv('TRADING_PAIR', 'ETHUSDT')
        self.leverage = int(os.getenv('LEVERAGE', '50'))
        self.quantity = float(os.getenv('QUANTITY', '0.001'))
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
        
        logger.info(f"交易机器人初始化完成 - 交易所: {self.exchange_name}, 交易对: {self.trading_pair}, 杠杆: {self.leverage}x")

    def get_account_balance(self):
        """获取账户余额"""
        try:
            balance = self.exchange.fetch_balance()
            for asset, info in balance.items():
                if asset == 'USDT':
                    return float(info['free'])
            return 0
        except Exception as e:
            logger.error(f"获取账户余额失败: {str(e)}")
            return 0

    def set_leverage(self):
        """设置合约杠杆"""
        try:
            if self.exchange_name == 'binance':
                self.exchange.fapiPrivate_post_leverage({
                    'symbol': self.trading_pair,
                    'leverage': self.leverage
                })
            elif self.exchange_name == 'lbank':
                # LBank的杠杆设置API
                self.exchange.private_post_leverage({
                    'symbol': self.trading_pair,
                    'leverage': self.leverage
                })
            logger.info(f"杠杆设置成功: {self.leverage}x")
        except Exception as e:
            logger.error(f"设置杠杆失败: {str(e)}")
            raise

    def get_historical_data(self, interval='1m', limit=100):
        """获取历史K线数据"""
        try:
            klines = self.exchange.fetch_ohlcv(self.trading_pair, interval, limit)
            
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
            logger.error(f"获取历史数据失败: {str(e)}")
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
            logger.error(f"计算指标失败: {str(e)}")
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
            logger.error(f"检查趋势失败: {str(e)}")
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
            logger.error(f"设置网格失败: {str(e)}")

    def place_grid_orders(self):
        """放置网格订单"""
        try:
            for level in self.grid_levels:
                if not level.filled:
                    order = self.exchange.create_order(
                        symbol=self.trading_pair,
                        type='limit',
                        side=level.side,
                        amount=level.quantity,
                        price=level.price
                    )
                    level.order_id = order['id']
                    self.active_orders[str(order['id'])] = {
                        'price': level.price,
                        'side': level.side,
                        'quantity': level.quantity
                    }
                    logger.info(f"网格订单放置成功: {level.side} @ {level.price}")
        except Exception as e:
            logger.error(f"放置网格订单失败: {str(e)}")

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
            logger.error(f"检查剥头皮机会失败: {str(e)}")
            return False, None

    def execute_scalping_trade(self, side: str):
        """执行剥头皮交易"""
        try:
            # 获取当前价格
            ticker = self.exchange.fetch_ticker(self.trading_pair)
            current_price = float(ticker['last'])
            
            # 计算止盈止损价格
            if side == 'BUY':
                take_profit = current_price * (1 + self.scalping_profit_target / 100)
                stop_loss = current_price * (1 - self.scalping_stop_loss / 100)
            else:
                take_profit = current_price * (1 - self.scalping_profit_target / 100)
                stop_loss = current_price * (1 + self.scalping_stop_loss / 100)
            
            # 执行交易
            order = self.exchange.create_order(
                symbol=self.trading_pair,
                type='market',
                side=side,
                amount=self.quantity
            )
            
            # 设置止盈止损
            self.exchange.create_order(
                symbol=self.trading_pair,
                type='TAKE_PROFIT_MARKET',
                side='SELL' if side == 'BUY' else 'BUY',
                amount=self.quantity,
                price=take_profit
            )
            
            self.exchange.create_order(
                symbol=self.trading_pair,
                type='STOP_MARKET',
                side='SELL' if side == 'BUY' else 'BUY',
                amount=self.quantity,
                price=stop_loss
            )
            
            logger.info(f"剥头皮交易执行成功: {side} @ {current_price}")
            
        except Exception as e:
            logger.error(f"执行剥头皮交易失败: {str(e)}")

    def run(self):
        """运行交易机器人"""
        logger.info("交易机器人启动...")
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
                logger.error(f"运行错误: {str(e)}")
                time.sleep(60)

    def check_grid_orders(self):
        """检查网格订单状态"""
        try:
            for order_id, order_info in list(self.active_orders.items()):
                order = self.exchange.fetch_order(self.trading_pair, order_id)
                
                if order['status'] == 'FILLED':
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
            logger.error(f"检查网格订单状态失败: {str(e)}")

    def execute_hedge_order(self, order_info: Dict):
        """执行对冲订单"""
        try:
            hedge_side = 'SELL' if order_info['side'] == 'BUY' else 'BUY'
            self.exchange.create_order(
                symbol=self.trading_pair,
                type='market',
                side=hedge_side,
                amount=order_info['quantity']
            )
            logger.info(f"对冲订单执行成功: {hedge_side} @ {order_info['price']}")
        except Exception as e:
            logger.error(f"执行对冲订单失败: {str(e)}")

    def reset_daily_stats(self):
        """重置每日统计数据"""
        self.daily_trades = 0
        self.daily_pnl = 0
        self.initial_balance = self.get_account_balance()
        logger.info("每日统计数据已重置")

    async def check_trading_opportunity(self, best_bid: float, best_ask: float):
        """检查交易机会"""
        try:
            # 计算市场深度
            bid_depth = sum(float(bid[1]) for bid in self.order_book['bids'][:self.order_book_depth])
            ask_depth = sum(float(ask[1]) for ask in self.order_book['asks'][:self.order_book_depth])
            
            # 计算价格压力
            price_pressure = (bid_depth - ask_depth) / (bid_depth + ask_depth)
            
            # 计算订单流
            order_flow = self.calculate_order_flow()
            
            # 计算波动率
            volatility = self.calculate_volatility()
            
            # 计算动量
            momentum = self.calculate_momentum()
            
            # 综合信号
            signal = self.generate_signal(price_pressure, order_flow, volatility, momentum)
            
            # 检查交易信号
            if abs(signal) > 0.5:  # 信号阈值
                side = 'BUY' if signal > 0 else 'SELL'
                await self.execute_trade(side, best_bid, best_ask)
                
        except Exception as e:
            logger.error(f"检查交易机会错误: {str(e)}")
            
    def calculate_order_flow(self) -> float:
        """计算订单流"""
        try:
            if len(self.trades_buffer) < 2:
                return 0.0
                
            # 计算最近交易的买卖压力
            buy_volume = sum(trade['quantity'] for trade in self.trades_buffer if trade['side'] == 'BUY')
            sell_volume = sum(trade['quantity'] for trade in self.trades_buffer if trade['side'] == 'SELL')
            
            # 计算订单流指标
            order_flow = (buy_volume - sell_volume) / (buy_volume + sell_volume)
            
            return order_flow
            
        except Exception as e:
            logger.error(f"计算订单流错误: {str(e)}")
            return 0.0
            
    def calculate_volatility(self) -> float:
        """计算波动率"""
        try:
            if len(self.klines_buffer) < 20:
                return 0.0
                
            # 计算价格变化
            prices = [float(kline[4]) for kline in self.klines_buffer]
            returns = np.diff(prices) / prices[:-1]
            
            # 计算波动率
            volatility = np.std(returns) * np.sqrt(252)  # 年化波动率
            
            return volatility
            
        except Exception as e:
            logger.error(f"计算波动率错误: {str(e)}")
            return 0.0
            
    def calculate_momentum(self) -> float:
        """计算动量"""
        try:
            if len(self.klines_buffer) < 10:
                return 0.0
                
            # 计算价格动量
            prices = [float(kline[4]) for kline in self.klines_buffer]
            momentum = (prices[-1] - prices[0]) / prices[0]
            
            return momentum
            
        except Exception as e:
            logger.error(f"计算动量错误: {str(e)}")
            return 0.0
            
    def generate_signal(self, price_pressure: float, order_flow: float, 
                       volatility: float, momentum: float) -> float:
        """生成交易信号"""
        try:
            # 信号权重
            weights = {
                'price_pressure': 0.3,
                'order_flow': 0.3,
                'volatility': 0.2,
                'momentum': 0.2
            }
            
            # 计算综合信号
            signal = (
                price_pressure * weights['price_pressure'] +
                order_flow * weights['order_flow'] +
                (1 - volatility) * weights['volatility'] +  # 低波动率更有利
                momentum * weights['momentum']
            )
            
            # 应用信号平滑
            signal = np.tanh(signal)  # 使用tanh函数将信号限制在[-1, 1]范围内
            
            return signal
            
        except Exception as e:
            logger.error(f"生成信号错误: {str(e)}")
            return 0.0
            
    async def execute_trade(self, side: str, bid: float, ask: float):
        """执行交易"""
        try:
            # 检查风险限制
            if not self.check_risk_limits():
                return
                
            # 计算交易价格和数量
            price = bid if side == 'BUY' else ask
            quantity = self.calculate_position_size(price)
            
            # 确定交易方向（做多/做空）
            position_type = 'LONG' if side == 'BUY' else 'SHORT'
            
            # 构建订单
            order = {
                'symbol': self.trading_pair,
                'type': 'limit',
                'side': side,
                'amount': quantity,
                'price': price
            }
            
            # 发送订单
            response = await self.send_order(order)
            
            if response and response['status'] == 'FILLED':
                # 更新持仓
                self.update_position(side, price, quantity)
                
                # 记录交易
                self.record_trade(side, price, quantity, position_type)
                
                # 设置动态止盈止损
                self.set_dynamic_take_profit_stop_loss(side, price)
                
        except Exception as e:
            logger.error(f"执行交易错误: {str(e)}")
            
    def calculate_position_size(self, price: float) -> float:
        """计算仓位大小"""
        try:
            # 获取账户余额
            balance = self.get_account_balance()
            
            # 计算风险金额
            risk_amount = balance * 0.01  # 风险1%的资金
            
            # 计算波动率
            volatility = self.calculate_volatility()
            
            # 根据波动率调整仓位
            position_size = risk_amount / (price * volatility)
            
            # 确保不超过最大仓位
            position_size = min(position_size, self.quantity)
            
            return position_size
            
        except Exception as e:
            logger.error(f"计算仓位大小错误: {str(e)}")
            return self.quantity
            
    def set_dynamic_take_profit_stop_loss(self, side: str, entry_price: float):
        """设置动态止盈止损"""
        try:
            # 计算波动率
            volatility = self.calculate_volatility()
            
            # 根据波动率调整止盈止损比例
            take_profit_ratio = max(self.min_profit_threshold, volatility * 2)
            stop_loss_ratio = max(self.min_profit_threshold, volatility)
            
            # 计算止盈止损价格
            if side == 'BUY':
                take_profit = entry_price * (1 + take_profit_ratio)
                stop_loss = entry_price * (1 - stop_loss_ratio)
            else:
                take_profit = entry_price * (1 - take_profit_ratio)
                stop_loss = entry_price * (1 + stop_loss_ratio)
                
            # 发送止盈止损订单
            self.executor.submit(
                self.exchange.create_order,
                symbol=self.trading_pair,
                type='TAKE_PROFIT_MARKET',
                side='SELL' if side == 'BUY' else 'BUY',
                amount=self.quantity,
                price=take_profit
            )
            
            self.executor.submit(
                self.exchange.create_order,
                symbol=self.trading_pair,
                type='STOP_MARKET',
                side='SELL' if side == 'BUY' else 'BUY',
                amount=self.quantity,
                price=stop_loss
            )
            
        except Exception as e:
            logger.error(f"设置动态止盈止损错误: {str(e)}")

    def record_trade(self, side: str, price: float, quantity: float, position_type: str):
        """记录交易"""
        try:
            trade = TradeHistory(
                exchange='Binance',
                symbol=self.trading_pair,
                side=side,
                position_type=position_type,
                price=price,
                quantity=quantity,
                status='OPEN',
                strategy=self.strategy,
                strategy_params=json.dumps({
                    'leverage': self.leverage,
                    'stop_loss': self.stop_loss,
                    'take_profit': self.take_profit
                })
            )
            db.session.add(trade)
            db.session.commit()
            logger.info(f"交易记录已保存: {side} {quantity} {self.trading_pair} @ {price}")
        except Exception as e:
            logger.error(f"保存交易记录失败: {str(e)}")
            db.session.rollback()

if __name__ == "__main__":
    bot = BinanceTradingBot()
    bot.run() 