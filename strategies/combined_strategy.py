from typing import Dict, List, Any, Optional
import pandas as pd
import numpy as np
from strategies.base import BaseStrategy
import talib
import logging

logger = logging.getLogger(__name__)

class CombinedStrategy(BaseStrategy):
    """组合策略，结合趋势跟踪、网格交易和剥头皮交易"""
    
    def __init__(self, trading: BaseTrading, config: Dict[str, Any]):
        super().__init__(trading, config)
        self.grid_levels = []
        self.active_orders = {}
        self.trades_buffer = []
        self.klines_buffer = []
        
    def initialize(self) -> bool:
        """初始化策略"""
        try:
            # 初始化技术指标参数
            self.fast_ema = self.config.get('fast_ema', 12)
            self.slow_ema = self.config.get('slow_ema', 26)
            self.rsi_period = self.config.get('rsi_period', 14)
            self.rsi_overbought = self.config.get('rsi_overbought', 70)
            self.rsi_oversold = self.config.get('rsi_oversold', 30)
            self.bb_period = self.config.get('bb_period', 20)
            self.bb_std = self.config.get('bb_std', 2)
            
            # 初始化网格参数
            self.grid_size = self.config.get('grid_size', 10)
            self.grid_spacing = self.config.get('grid_spacing', 0.002)
            
            # 初始化剥头皮参数
            self.scalping_profit_target = self.config.get('scalping_profit_target', 0.003)
            self.scalping_stop_loss = self.config.get('scalping_stop_loss', 0.002)
            
            # 初始化风险控制参数
            self.max_positions = self.config.get('max_positions', 3)
            self.max_daily_trades = self.config.get('max_daily_trades', 10)
            self.max_daily_loss = self.config.get('max_daily_loss', 0.05)
            
            logger.info("策略初始化成功")
            return True
            
        except Exception as e:
            logger.error(f"策略初始化失败: {str(e)}")
            return False
            
    def on_tick(self, tick_data: Dict[str, Any]) -> None:
        """处理行情数据"""
        try:
            # 更新K线数据
            self.klines_buffer.append(tick_data)
            if len(self.klines_buffer) > 100:
                self.klines_buffer = self.klines_buffer[-100:]
                
            # 更新交易数据
            self.trades_buffer.append(tick_data)
            if len(self.trades_buffer) > 100:
                self.trades_buffer = self.trades_buffer[-100:]
                
            # 分析市场并执行交易
            self.analyze_market()
            
        except Exception as e:
            logger.error(f"处理行情数据错误: {str(e)}")
            
    def analyze_market(self) -> None:
        """分析市场并生成交易信号"""
        try:
            if len(self.klines_buffer) < 100:
                return
                
            # 转换为DataFrame
            df = pd.DataFrame(self.klines_buffer)
            close_prices = df['close'].astype(float)
            
            # 计算技术指标
            fast_ema = talib.EMA(close_prices, timeperiod=self.fast_ema)
            slow_ema = talib.EMA(close_prices, timeperiod=self.slow_ema)
            rsi = talib.RSI(close_prices, timeperiod=self.rsi_period)
            upper, middle, lower = talib.BBANDS(
                close_prices,
                timeperiod=self.bb_period,
                nbdevup=self.bb_std,
                nbdevdn=self.bb_std
            )
            
            # 获取当前价格和指标值
            current_price = float(close_prices.iloc[-1])
            current_rsi = float(rsi.iloc[-1])
            
            # 生成交易信号
            signals = self.calculate_signals(df)
            
            # 检查交易机会
            if self.should_open_position(signals):
                self.execute_trade('buy', current_price)
            elif self.should_close_position(signals):
                self.execute_trade('sell', current_price)
                
            # 更新网格
            self.update_grid(current_price)
            
        except Exception as e:
            logger.error(f"市场分析错误: {str(e)}")
            
    def calculate_signals(self, df: pd.DataFrame) -> Dict[str, Any]:
        """计算交易信号"""
        try:
            signals = {
                'trend': 0,  # 1: 上涨, -1: 下跌, 0: 盘整
                'momentum': 0,  # 1: 超买, -1: 超卖, 0: 中性
                'volatility': 0,  # 1: 高波动, -1: 低波动, 0: 正常
                'volume': 0  # 1: 放量, -1: 缩量, 0: 正常
            }
            
            # 趋势信号
            if df['fast_ema'].iloc[-1] > df['slow_ema'].iloc[-1]:
                signals['trend'] = 1
            elif df['fast_ema'].iloc[-1] < df['slow_ema'].iloc[-1]:
                signals['trend'] = -1
                
            # 动量信号
            if df['rsi'].iloc[-1] > self.rsi_overbought:
                signals['momentum'] = 1
            elif df['rsi'].iloc[-1] < self.rsi_oversold:
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
            logger.error(f"计算信号错误: {str(e)}")
            return {}
            
    def should_open_position(self, signals: Dict[str, Any]) -> bool:
        """判断是否开仓"""
        try:
            # 检查持仓数量限制
            if len(self.positions) >= self.max_positions:
                return False
                
            # 检查每日交易限制
            if self.daily_trades >= self.max_daily_trades:
                return False
                
            # 检查每日亏损限制
            if self.daily_pnl <= -self.max_daily_loss:
                return False
                
            # 综合信号判断
            if (signals['trend'] == 1 and 
                signals['momentum'] == -1 and 
                signals['volatility'] == 0 and 
                signals['volume'] == 1):
                return True
                
            return False
            
        except Exception as e:
            logger.error(f"开仓判断错误: {str(e)}")
            return False
            
    def should_close_position(self, signals: Dict[str, Any]) -> bool:
        """判断是否平仓"""
        try:
            # 检查是否有持仓
            if not self.positions:
                return False
                
            # 综合信号判断
            if (signals['trend'] == -1 and 
                signals['momentum'] == 1 and 
                signals['volatility'] == 1):
                return True
                
            return False
            
        except Exception as e:
            logger.error(f"平仓判断错误: {str(e)}")
            return False
            
    def calculate_position_size(self) -> float:
        """计算仓位大小"""
        try:
            # 获取账户余额
            balance = self.trading.get_account_balance()
            
            # 计算风险金额
            risk_amount = balance * self.config.get('risk_per_trade', 0.02)
            
            # 计算波动率
            volatility = self.calculate_volatility()
            
            # 根据波动率调整仓位
            position_size = risk_amount / (self.current_price * volatility)
            
            # 确保不超过最大仓位
            position_size = min(position_size, self.config.get('max_position_size', 1.0))
            
            return position_size
            
        except Exception as e:
            logger.error(f"计算仓位大小错误: {str(e)}")
            return self.config.get('default_position_size', 0.1)
            
    def calculate_stop_loss(self, entry_price: float, side: str) -> float:
        """计算止损价格"""
        try:
            # 计算波动率
            volatility = self.calculate_volatility()
            
            # 根据波动率调整止损比例
            stop_loss_ratio = max(self.config.get('min_stop_loss', 0.01), volatility * 2)
            
            if side == 'buy':
                return entry_price * (1 - stop_loss_ratio)
            else:
                return entry_price * (1 + stop_loss_ratio)
                
        except Exception as e:
            logger.error(f"计算止损价格错误: {str(e)}")
            return entry_price * 0.95 if side == 'buy' else entry_price * 1.05
            
    def calculate_take_profit(self, entry_price: float, side: str) -> float:
        """计算止盈价格"""
        try:
            # 计算波动率
            volatility = self.calculate_volatility()
            
            # 根据波动率调整止盈比例
            take_profit_ratio = max(self.config.get('min_take_profit', 0.02), volatility * 3)
            
            if side == 'buy':
                return entry_price * (1 + take_profit_ratio)
            else:
                return entry_price * (1 - take_profit_ratio)
                
        except Exception as e:
            logger.error(f"计算止盈价格错误: {str(e)}")
            return entry_price * 1.05 if side == 'buy' else entry_price * 0.95
            
    def calculate_volatility(self) -> float:
        """计算波动率"""
        try:
            if len(self.klines_buffer) < 20:
                return 0.02
                
            # 计算价格变化
            prices = [float(kline['close']) for kline in self.klines_buffer]
            returns = np.diff(prices) / prices[:-1]
            
            # 计算波动率
            volatility = np.std(returns) * np.sqrt(252)  # 年化波动率
            
            return max(volatility, 0.01)  # 确保最小波动率
            
        except Exception as e:
            logger.error(f"计算波动率错误: {str(e)}")
            return 0.02
            
    def update_grid(self, current_price: float) -> None:
        """更新网格"""
        try:
            if not self.grid_levels:
                self.setup_grid(current_price)
                
            # 检查网格订单状态
            self.check_grid_orders()
            
        except Exception as e:
            logger.error(f"更新网格错误: {str(e)}")
            
    def setup_grid(self, current_price: float) -> None:
        """设置网格"""
        try:
            # 计算网格价格
            grid_prices = []
            for i in range(self.grid_size):
                price = current_price * (1 + self.grid_spacing * (i - self.grid_size // 2))
                grid_prices.append(price)
                
            # 创建网格订单
            for price in grid_prices:
                if price < current_price:
                    self.grid_levels.append({
                        'price': price,
                        'side': 'buy',
                        'quantity': self.calculate_position_size(),
                        'filled': False
                    })
                else:
                    self.grid_levels.append({
                        'price': price,
                        'side': 'sell',
                        'quantity': self.calculate_position_size(),
                        'filled': False
                    })
                    
            # 放置网格订单
            self.place_grid_orders()
            
        except Exception as e:
            logger.error(f"设置网格错误: {str(e)}")
            
    def place_grid_orders(self) -> None:
        """放置网格订单"""
        try:
            for level in self.grid_levels:
                if not level['filled']:
                    order = self.trading.place_order(
                        symbol=self.config['symbol'],
                        side=level['side'],
                        quantity=level['quantity'],
                        price=level['price'],
                        order_type='limit'
                    )
                    
                    if order:
                        level['order_id'] = order['order_id']
                        self.active_orders[order['order_id']] = level
                        
        except Exception as e:
            logger.error(f"放置网格订单错误: {str(e)}")
            
    def check_grid_orders(self) -> None:
        """检查网格订单状态"""
        try:
            for order_id, level in list(self.active_orders.items()):
                order = self.trading.get_order(order_id)
                
                if order['status'] == 'FILLED':
                    level['filled'] = True
                    del self.active_orders[order_id]
                    
                    # 创建对冲订单
                    self.create_hedge_order(level)
                    
        except Exception as e:
            logger.error(f"检查网格订单状态错误: {str(e)}")
            
    def create_hedge_order(self, level: Dict[str, Any]) -> None:
        """创建对冲订单"""
        try:
            hedge_side = 'sell' if level['side'] == 'buy' else 'buy'
            hedge_price = level['price'] * (1 + self.scalping_profit_target)
            
            order = self.trading.place_order(
                symbol=self.config['symbol'],
                side=hedge_side,
                quantity=level['quantity'],
                price=hedge_price,
                order_type='limit'
            )
            
            if order:
                level['hedge_order_id'] = order['order_id']
                
        except Exception as e:
            logger.error(f"创建对冲订单错误: {str(e)}") 