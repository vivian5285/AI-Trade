from typing import Dict, List, Any, Optional
import pandas as pd
import numpy as np
from strategies.base import BaseStrategy
from mt4_connector.mt4_client import MT4Client

class MT4Strategy(BaseStrategy):
    """MT4交易策略"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.client = MT4Client(config)
        self.positions = {}
        self.orders = {}
        self.trades = []
        
    def initialize(self) -> bool:
        """初始化策略"""
        try:
            # 连接MT4
            if not self.client.connect():
                return False
                
            # 获取当前持仓
            position = self.client.get_position()
            if position:
                self.positions[self.config['symbol']] = position
                
            # 获取未完成订单
            orders = self.client.get_open_orders()
            for order in orders:
                self.orders[order['ticket']] = order
                
            # 获取交易历史
            self.trades = self.client.get_trades()
            
            return True
        except Exception as e:
            print(f"策略初始化失败: {e}")
            return False
            
    def on_tick(self, tick_data: Dict[str, Any]) -> None:
        """处理行情数据"""
        try:
            # 更新持仓信息
            position = self.client.get_position()
            if position:
                self.positions[self.config['symbol']] = position
                
            # 更新订单信息
            orders = self.client.get_open_orders()
            self.orders.clear()
            for order in orders:
                self.orders[order['ticket']] = order
                
            # 计算交易信号
            signals = self.calculate_signals()
            
            # 检查是否需要开仓
            if self.should_open_position(signals):
                self.open_position(signals)
                
            # 检查是否需要平仓
            if self.should_close_position(signals):
                self.close_position()
                
        except Exception as e:
            print(f"处理行情数据失败: {e}")
            
    def calculate_signals(self) -> Dict[str, Any]:
        """计算交易信号"""
        try:
            # 获取历史数据
            df = self.client.get_historical_data(
                interval=self.config.get('interval', '1m'),
                limit=self.config.get('lookback', 100)
            )
            
            if df.empty:
                return {}
                
            # 计算技术指标
            df['sma_fast'] = df['close'].rolling(window=self.config.get('fast_ma_period', 10)).mean()
            df['sma_slow'] = df['close'].rolling(window=self.config.get('slow_ma_period', 20)).mean()
            df['rsi'] = self.calculate_rsi(df['close'], self.config.get('rsi_period', 14))
            
            # 生成信号
            signals = {
                'trend': 0,  # 1: 上涨, -1: 下跌, 0: 盘整
                'momentum': 0,  # 1: 超买, -1: 超卖, 0: 中性
                'volatility': 0,  # 1: 高波动, -1: 低波动, 0: 正常
                'volume': 0  # 1: 放量, -1: 缩量, 0: 正常
            }
            
            # 趋势信号
            if df['sma_fast'].iloc[-1] > df['sma_slow'].iloc[-1]:
                signals['trend'] = 1
            elif df['sma_fast'].iloc[-1] < df['sma_slow'].iloc[-1]:
                signals['trend'] = -1
                
            # 动量信号
            if df['rsi'].iloc[-1] > self.config.get('rsi_overbought', 70):
                signals['momentum'] = 1
            elif df['rsi'].iloc[-1] < self.config.get('rsi_oversold', 30):
                signals['momentum'] = -1
                
            # 波动率信号
            volatility = df['close'].pct_change().std()
            if volatility > self.config.get('high_volatility', 0.02):
                signals['volatility'] = 1
            elif volatility < self.config.get('low_volatility', 0.005):
                signals['volatility'] = -1
                
            # 成交量信号
            volume_ma = df['volume'].rolling(window=20).mean()
            if df['volume'].iloc[-1] > volume_ma.iloc[-1] * 1.5:
                signals['volume'] = 1
            elif df['volume'].iloc[-1] < volume_ma.iloc[-1] * 0.5:
                signals['volume'] = -1
                
            return signals
            
        except Exception as e:
            print(f"计算交易信号失败: {e}")
            return {}
            
    def should_open_position(self, signals: Dict[str, Any]) -> bool:
        """判断是否应该开仓"""
        try:
            # 检查是否已有持仓
            if self.config['symbol'] in self.positions:
                return False
                
            # 检查信号强度
            signal_strength = (
                signals.get('trend', 0) * self.config.get('trend_weight', 0.4) +
                signals.get('momentum', 0) * self.config.get('momentum_weight', 0.3) +
                signals.get('volatility', 0) * self.config.get('volatility_weight', 0.2) +
                signals.get('volume', 0) * self.config.get('volume_weight', 0.1)
            )
            
            # 开仓条件
            if signal_strength > self.config.get('open_threshold', 0.6):
                return True
                
            return False
            
        except Exception as e:
            print(f"判断开仓条件失败: {e}")
            return False
            
    def should_close_position(self, signals: Dict[str, Any]) -> bool:
        """判断是否应该平仓"""
        try:
            # 检查是否有持仓
            if self.config['symbol'] not in self.positions:
                return False
                
            position = self.positions[self.config['symbol']]
            
            # 检查止损止盈
            current_price = self.client.get_ticker()['last']
            if position['type'] == 0:  # 多单
                if current_price <= position['sl'] or current_price >= position['tp']:
                    return True
            else:  # 空单
                if current_price >= position['sl'] or current_price <= position['tp']:
                    return True
                    
            # 检查信号强度
            signal_strength = (
                signals.get('trend', 0) * self.config.get('trend_weight', 0.4) +
                signals.get('momentum', 0) * self.config.get('momentum_weight', 0.3) +
                signals.get('volatility', 0) * self.config.get('volatility_weight', 0.2) +
                signals.get('volume', 0) * self.config.get('volume_weight', 0.1)
            )
            
            # 平仓条件
            if (position['type'] == 0 and signal_strength < -self.config.get('close_threshold', 0.4)) or \
               (position['type'] == 1 and signal_strength > self.config.get('close_threshold', 0.4)):
                return True
                
            return False
            
        except Exception as e:
            print(f"判断平仓条件失败: {e}")
            return False
            
    def open_position(self, signals: Dict[str, Any]) -> None:
        """开仓"""
        try:
            # 计算开仓方向
            if signals['trend'] > 0:
                order_type = 0  # 多单
            else:
                order_type = 1  # 空单
                
            # 计算开仓数量
            volume = self.calculate_position_size()
            
            # 计算止损止盈价格
            current_price = self.client.get_ticker()['last']
            sl, tp = self.calculate_stop_loss_take_profit(order_type, current_price)
            
            # 下单
            order = self.client.place_order(
                side=order_type,
                order_type='MARKET',
                quantity=volume,
                price=current_price
            )
            
            if order:
                self.orders[order['ticket']] = order
                
        except Exception as e:
            print(f"开仓失败: {e}")
            
    def close_position(self) -> None:
        """平仓"""
        try:
            position = self.positions.get(self.config['symbol'])
            if not position:
                return
                
            # 平仓
            order = self.client.place_order(
                side=1 if position['type'] == 0 else 0,
                order_type='MARKET',
                quantity=position['volume'],
                price=self.client.get_ticker()['last']
            )
            
            if order:
                self.orders[order['ticket']] = order
                del self.positions[self.config['symbol']]
                
        except Exception as e:
            print(f"平仓失败: {e}")
            
    def calculate_position_size(self) -> float:
        """计算开仓数量"""
        try:
            # 获取账户余额
            balance = self.client.get_balance()
            
            # 计算风险金额
            risk_amount = balance * self.config.get('risk_per_trade', 0.02)
            
            # 计算止损点数
            stop_loss_pips = self.config.get('stop_loss_pips', 50)
            
            # 计算每点价值
            point_value = self.config.get('point_value', 0.1)
            
            # 计算开仓数量
            position_size = risk_amount / (stop_loss_pips * point_value)
            
            # 限制最大开仓数量
            max_position_size = self.config.get('max_position_size', 1.0)
            position_size = min(position_size, max_position_size)
            
            return position_size
            
        except Exception as e:
            print(f"计算开仓数量失败: {e}")
            return self.config.get('default_position_size', 0.1)
            
    def calculate_stop_loss_take_profit(self, order_type: int, entry_price: float) -> tuple:
        """计算止损止盈价格"""
        try:
            # 计算止损点数
            stop_loss_pips = self.config.get('stop_loss_pips', 50)
            take_profit_pips = self.config.get('take_profit_pips', 100)
            
            # 计算每点价值
            point_value = self.config.get('point_value', 0.1)
            
            # 计算止损止盈价格
            if order_type == 0:  # 多单
                stop_loss = entry_price - stop_loss_pips * point_value
                take_profit = entry_price + take_profit_pips * point_value
            else:  # 空单
                stop_loss = entry_price + stop_loss_pips * point_value
                take_profit = entry_price - take_profit_pips * point_value
                
            return stop_loss, take_profit
            
        except Exception as e:
            print(f"计算止损止盈价格失败: {e}")
            return 0, 0
            
    def calculate_rsi(self, prices: pd.Series, period: int) -> pd.Series:
        """计算RSI指标"""
        try:
            delta = prices.diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            return rsi
        except Exception as e:
            print(f"计算RSI失败: {e}")
            return pd.Series() 