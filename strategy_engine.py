import logging
import time
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Union
from exchange_api import ExchangeAPI
import json
from datetime import datetime

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('strategy_engine.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class StrategyEngine:
    def __init__(self, exchange_api: ExchangeAPI, config: Dict):
        self.exchange_api = exchange_api
        self.config = config
        self.active_positions = {}
        self.pending_orders = {}
        self.strategy_state = {}
        self.initialize_strategy()

    def initialize_strategy(self):
        """初始化策略状态"""
        self.strategy_state = {
            'last_signal_time': 0,
            'current_position': None,
            'signal_count': 0,
            'win_count': 0,
            'loss_count': 0,
            'total_pnl': 0.0
        }
        logger.info("Strategy initialized with config: %s", json.dumps(self.config))

    def calculate_indicators(self, market_data: List[Dict]) -> Dict:
        """计算技术指标"""
        try:
            df = pd.DataFrame(market_data)
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)

            # 计算移动平均线
            df['MA20'] = df['close'].rolling(window=20).mean()
            df['MA50'] = df['close'].rolling(window=50).mean()
            df['MA200'] = df['close'].rolling(window=200).mean()

            # 计算RSI
            delta = df['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            df['RSI'] = 100 - (100 / (1 + rs))

            # 计算MACD
            exp1 = df['close'].ewm(span=12, adjust=False).mean()
            exp2 = df['close'].ewm(span=26, adjust=False).mean()
            df['MACD'] = exp1 - exp2
            df['Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
            df['Histogram'] = df['MACD'] - df['Signal']

            # 计算布林带
            df['BB_middle'] = df['close'].rolling(window=20).mean()
            df['BB_std'] = df['close'].rolling(window=20).std()
            df['BB_upper'] = df['BB_middle'] + (df['BB_std'] * 2)
            df['BB_lower'] = df['BB_middle'] - (df['BB_std'] * 2)

            return df.iloc[-1].to_dict()

        except Exception as e:
            logger.error(f"Error calculating indicators: {str(e)}")
            raise

    def generate_signal(self, indicators: Dict) -> Optional[Dict]:
        """生成交易信号"""
        try:
            current_time = time.time()
            if current_time - self.strategy_state['last_signal_time'] < self.config['min_signal_interval']:
                return None

            signal = None
            # 趋势跟踪策略
            if indicators['MA20'] > indicators['MA50'] and indicators['MA50'] > indicators['MA200']:
                if indicators['RSI'] < 70:  # 避免超买
                    signal = {
                        'type': 'LONG',
                        'strength': min((70 - indicators['RSI']) / 70, 1.0),
                        'reason': 'Uptrend with RSI confirmation'
                    }
            elif indicators['MA20'] < indicators['MA50'] and indicators['MA50'] < indicators['MA200']:
                if indicators['RSI'] > 30:  # 避免超卖
                    signal = {
                        'type': 'SHORT',
                        'strength': min((indicators['RSI'] - 30) / 70, 1.0),
                        'reason': 'Downtrend with RSI confirmation'
                    }

            # MACD确认
            if signal:
                if signal['type'] == 'LONG' and indicators['MACD'] < indicators['Signal']:
                    signal = None
                elif signal['type'] == 'SHORT' and indicators['MACD'] > indicators['Signal']:
                    signal = None

            # 布林带过滤
            if signal:
                if signal['type'] == 'LONG' and indicators['close'] > indicators['BB_upper']:
                    signal = None
                elif signal['type'] == 'SHORT' and indicators['close'] < indicators['BB_lower']:
                    signal = None

            if signal:
                self.strategy_state['last_signal_time'] = current_time
                self.strategy_state['signal_count'] += 1
                logger.info(f"Generated signal: {json.dumps(signal)}")

            return signal

        except Exception as e:
            logger.error(f"Error generating signal: {str(e)}")
            raise

    def calculate_position_size(self, signal: Dict, account_balance: float) -> float:
        """计算仓位大小"""
        try:
            # 基础仓位大小
            base_position = account_balance * self.config['base_position_size']
            
            # 根据信号强度调整
            position_size = base_position * signal['strength']
            
            # 根据风险限制调整
            max_position = account_balance * self.config['max_position_size']
            position_size = min(position_size, max_position)
            
            # 根据当前持仓调整
            if self.strategy_state['current_position']:
                position_size = min(position_size, 
                                  self.config['max_additional_position'] * account_balance)
            
            return position_size

        except Exception as e:
            logger.error(f"Error calculating position size: {str(e)}")
            raise

    def calculate_stop_loss(self, signal: Dict, current_price: float) -> float:
        """计算止损价格"""
        try:
            if signal['type'] == 'LONG':
                return current_price * (1 - self.config['stop_loss_pct'])
            else:
                return current_price * (1 + self.config['stop_loss_pct'])
        except Exception as e:
            logger.error(f"Error calculating stop loss: {str(e)}")
            raise

    def calculate_take_profit(self, signal: Dict, current_price: float) -> float:
        """计算止盈价格"""
        try:
            if signal['type'] == 'LONG':
                return current_price * (1 + self.config['take_profit_pct'])
            else:
                return current_price * (1 - self.config['take_profit_pct'])
        except Exception as e:
            logger.error(f"Error calculating take profit: {str(e)}")
            raise

    def execute_signal(self, signal: Dict, symbol: str):
        """执行交易信号"""
        try:
            # 获取账户余额
            account_balance = self.exchange_api.get_account_balance()
            available_balance = account_balance['available_balance']

            # 计算仓位大小
            position_size = self.calculate_position_size(signal, available_balance)

            # 获取当前价格
            market_data = self.exchange_api.get_market_data(symbol, limit=1)
            current_price = market_data[0]['close']

            # 计算止损止盈价格
            stop_loss = self.calculate_stop_loss(signal, current_price)
            take_profit = self.calculate_take_profit(signal, current_price)

            # 执行订单
            order = self.exchange_api.place_order(
                symbol=symbol,
                side='BUY' if signal['type'] == 'LONG' else 'SELL',
                quantity=position_size,
                stop_loss=stop_loss,
                take_profit=take_profit
            )

            # 更新策略状态
            self.strategy_state['current_position'] = {
                'symbol': symbol,
                'side': signal['type'],
                'entry_price': current_price,
                'size': position_size,
                'stop_loss': stop_loss,
                'take_profit': take_profit,
                'order_id': order['orderId']
            }

            logger.info(f"Executed signal: {json.dumps(order)}")
            return order

        except Exception as e:
            logger.error(f"Error executing signal: {str(e)}")
            raise

    def update_position_status(self, symbol: str):
        """更新持仓状态"""
        try:
            if not self.strategy_state['current_position']:
                return

            position = self.strategy_state['current_position']
            if position['symbol'] != symbol:
                return

            # 获取当前价格
            market_data = self.exchange_api.get_market_data(symbol, limit=1)
            current_price = market_data[0]['close']

            # 计算未实现盈亏
            if position['side'] == 'LONG':
                unrealized_pnl = (current_price - position['entry_price']) * position['size']
            else:
                unrealized_pnl = (position['entry_price'] - current_price) * position['size']

            # 更新策略状态
            self.strategy_state['total_pnl'] += unrealized_pnl

            # 检查是否需要平仓
            if position['side'] == 'LONG':
                if current_price <= position['stop_loss'] or current_price >= position['take_profit']:
                    self.close_position(symbol)
            else:
                if current_price >= position['stop_loss'] or current_price <= position['take_profit']:
                    self.close_position(symbol)

        except Exception as e:
            logger.error(f"Error updating position status: {str(e)}")
            raise

    def close_position(self, symbol: str):
        """平仓"""
        try:
            if not self.strategy_state['current_position']:
                return

            position = self.strategy_state['current_position']
            if position['symbol'] != symbol:
                return

            # 获取当前价格
            market_data = self.exchange_api.get_market_data(symbol, limit=1)
            current_price = market_data[0]['close']

            # 计算最终盈亏
            if position['side'] == 'LONG':
                pnl = (current_price - position['entry_price']) * position['size']
            else:
                pnl = (position['entry_price'] - current_price) * position['size']

            # 更新统计数据
            if pnl > 0:
                self.strategy_state['win_count'] += 1
            else:
                self.strategy_state['loss_count'] += 1

            self.strategy_state['total_pnl'] += pnl
            self.strategy_state['current_position'] = None

            logger.info(f"Position closed with PnL: {pnl}")

        except Exception as e:
            logger.error(f"Error closing position: {str(e)}")
            raise

    def get_strategy_stats(self) -> Dict:
        """获取策略统计信息"""
        return {
            'signal_count': self.strategy_state['signal_count'],
            'win_count': self.strategy_state['win_count'],
            'loss_count': self.strategy_state['loss_count'],
            'total_pnl': self.strategy_state['total_pnl'],
            'win_rate': (self.strategy_state['win_count'] / 
                        (self.strategy_state['win_count'] + self.strategy_state['loss_count'])
                        if (self.strategy_state['win_count'] + self.strategy_state['loss_count']) > 0
                        else 0),
            'current_position': self.strategy_state['current_position']
        } 