from .base_config import BaseConfig
from typing import Dict, Any

class LBankConfig(BaseConfig):
    """LBank配置类"""
    def __init__(self):
        super().__init__()
        self.api_key = self.get_env('LBANK_API_KEY')
        self.secret_key = self.get_env('LBANK_SECRET_KEY')
        self.trading_pair = self.get_env('TRADING_PAIR', 'btc_usdt')
        self.leverage = int(self.get_env('LEVERAGE', '20'))
        self.position_size = float(self.get_env('POSITION_SIZE', '0.001'))
        self.max_positions = int(self.get_env('MAX_POSITIONS', '5'))
        self.max_drawdown = float(self.get_env('MAX_DRAWDOWN', '10.0'))
        self.daily_loss_limit = float(self.get_env('DAILY_LOSS_LIMIT', '5.0'))
        self.max_leverage = int(self.get_env('MAX_LEVERAGE', '20'))
        self.fast_ema = int(self.get_env('FAST_EMA', '12'))
        self.slow_ema = int(self.get_env('SLOW_EMA', '26'))
        self.rsi_period = int(self.get_env('RSI_PERIOD', '14'))
        self.rsi_overbought = int(self.get_env('RSI_OVERBOUGHT', '70'))
        self.rsi_oversold = int(self.get_env('RSI_OVERSOLD', '30'))
        self.bb_period = int(self.get_env('BB_PERIOD', '20'))
        self.bb_std = float(self.get_env('BB_STD', '2.0'))
        self.min_volume = float(self.get_env('MIN_VOLUME', '1000000'))
        self.price_change_threshold = float(self.get_env('PRICE_CHANGE_THRESHOLD', '0.5'))
        self.execution_interval = float(self.get_env('EXECUTION_INTERVAL', '1.0'))
        
    def validate(self) -> bool:
        """验证配置是否有效"""
        if not self.api_key or not self.secret_key:
            return False
        if self.leverage <= 0 or self.position_size <= 0:
            return False
        return True 