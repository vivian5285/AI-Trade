from typing import Dict, Any
from config.base_config import BaseConfig

class MT4StrategyConfig(BaseConfig):
    """MT4策略配置"""
    
    def __init__(self):
        super().__init__()
        
        # MT4连接配置
        self.server = self.get_env('MT4_SERVER', 'localhost')
        self.port = int(self.get_env('MT4_PORT', '8222'))
        self.symbol = self.get_env('MT4_SYMBOL', 'EURUSD')
        self.magic_number = int(self.get_env('MT4_MAGIC_NUMBER', '123456'))
        
        # 交易参数
        self.interval = self.get_env('MT4_INTERVAL', '1m')
        self.lookback = int(self.get_env('MT4_LOOKBACK', '100'))
        self.risk_per_trade = float(self.get_env('MT4_RISK_PER_TRADE', '0.02'))
        self.max_position_size = float(self.get_env('MT4_MAX_POSITION_SIZE', '1.0'))
        self.default_position_size = float(self.get_env('MT4_DEFAULT_POSITION_SIZE', '0.1'))
        
        # 技术指标参数
        self.fast_ma_period = int(self.get_env('MT4_FAST_MA_PERIOD', '10'))
        self.slow_ma_period = int(self.get_env('MT4_SLOW_MA_PERIOD', '20'))
        self.rsi_period = int(self.get_env('MT4_RSI_PERIOD', '14'))
        self.rsi_overbought = float(self.get_env('MT4_RSI_OVERBOUGHT', '70'))
        self.rsi_oversold = float(self.get_env('MT4_RSI_OVERSOLD', '30'))
        
        # 波动率参数
        self.high_volatility = float(self.get_env('MT4_HIGH_VOLATILITY', '0.02'))
        self.low_volatility = float(self.get_env('MT4_LOW_VOLATILITY', '0.005'))
        
        # 信号权重
        self.trend_weight = float(self.get_env('MT4_TREND_WEIGHT', '0.4'))
        self.momentum_weight = float(self.get_env('MT4_MOMENTUM_WEIGHT', '0.3'))
        self.volatility_weight = float(self.get_env('MT4_VOLATILITY_WEIGHT', '0.2'))
        self.volume_weight = float(self.get_env('MT4_VOLUME_WEIGHT', '0.1'))
        
        # 开平仓阈值
        self.open_threshold = float(self.get_env('MT4_OPEN_THRESHOLD', '0.6'))
        self.close_threshold = float(self.get_env('MT4_CLOSE_THRESHOLD', '0.4'))
        
        # 止损止盈参数
        self.stop_loss_pips = int(self.get_env('MT4_STOP_LOSS_PIPS', '50'))
        self.take_profit_pips = int(self.get_env('MT4_TAKE_PROFIT_PIPS', '100'))
        self.point_value = float(self.get_env('MT4_POINT_VALUE', '0.1'))
        
    def validate(self) -> bool:
        """验证配置"""
        try:
            # 验证MT4连接配置
            if not self.server or not self.port or not self.symbol:
                return False
                
            # 验证交易参数
            if self.risk_per_trade <= 0 or self.risk_per_trade > 1:
                return False
            if self.max_position_size <= 0:
                return False
            if self.default_position_size <= 0:
                return False
                
            # 验证技术指标参数
            if self.fast_ma_period <= 0 or self.slow_ma_period <= 0:
                return False
            if self.fast_ma_period >= self.slow_ma_period:
                return False
            if self.rsi_period <= 0:
                return False
            if self.rsi_overbought <= 50 or self.rsi_overbought > 100:
                return False
            if self.rsi_oversold >= 50 or self.rsi_oversold < 0:
                return False
                
            # 验证波动率参数
            if self.high_volatility <= 0 or self.low_volatility <= 0:
                return False
            if self.high_volatility <= self.low_volatility:
                return False
                
            # 验证信号权重
            weights = [
                self.trend_weight,
                self.momentum_weight,
                self.volatility_weight,
                self.volume_weight
            ]
            if not all(0 <= w <= 1 for w in weights):
                return False
            if abs(sum(weights) - 1.0) > 0.0001:
                return False
                
            # 验证开平仓阈值
            if not 0 < self.open_threshold < 1:
                return False
            if not 0 < self.close_threshold < 1:
                return False
                
            # 验证止损止盈参数
            if self.stop_loss_pips <= 0 or self.take_profit_pips <= 0:
                return False
            if self.point_value <= 0:
                return False
                
            return True
            
        except Exception as e:
            print(f"验证配置失败: {e}")
            return False
            
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'server': self.server,
            'port': self.port,
            'symbol': self.symbol,
            'magic_number': self.magic_number,
            'interval': self.interval,
            'lookback': self.lookback,
            'risk_per_trade': self.risk_per_trade,
            'max_position_size': self.max_position_size,
            'default_position_size': self.default_position_size,
            'fast_ma_period': self.fast_ma_period,
            'slow_ma_period': self.slow_ma_period,
            'rsi_period': self.rsi_period,
            'rsi_overbought': self.rsi_overbought,
            'rsi_oversold': self.rsi_oversold,
            'high_volatility': self.high_volatility,
            'low_volatility': self.low_volatility,
            'trend_weight': self.trend_weight,
            'momentum_weight': self.momentum_weight,
            'volatility_weight': self.volatility_weight,
            'volume_weight': self.volume_weight,
            'open_threshold': self.open_threshold,
            'close_threshold': self.close_threshold,
            'stop_loss_pips': self.stop_loss_pips,
            'take_profit_pips': self.take_profit_pips,
            'point_value': self.point_value
        } 