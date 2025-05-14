from .base_config import BaseConfig
from typing import Dict, Any

class MT4Config(BaseConfig):
    """MT4配置类"""
    def __init__(self):
        super().__init__()
        self.server = self.get_env('MT4_SERVER', 'MetaQuotes-Demo')
        self.login = self.get_env('MT4_LOGIN')
        self.password = self.get_env('MT4_PASSWORD')
        self.symbol = self.get_env('MT4_SYMBOL', 'XAUUSD')
        self.lot_size = float(self.get_env('MT4_LOT_SIZE', '0.1'))
        self.grid_step = int(self.get_env('MT4_GRID_STEP', '100'))
        self.grid_levels = int(self.get_env('MT4_GRID_LEVELS', '5'))
        self.lot_multiplier = float(self.get_env('MT4_LOT_MULTIPLIER', '1.5'))
        self.magic_number = int(self.get_env('MT4_MAGIC_NUMBER', '12345'))
        self.stop_loss = int(self.get_env('MT4_STOP_LOSS', '500'))
        self.take_profit = int(self.get_env('MT4_TAKE_PROFIT', '200'))
        self.use_trailing_stop = self.get_env('MT4_USE_TRAILING_STOP', 'true').lower() == 'true'
        self.trailing_stop = int(self.get_env('MT4_TRAILING_STOP', '300'))
        self.trailing_step = int(self.get_env('MT4_TRAILING_STEP', '50'))
        self.fast_ma_period = int(self.get_env('MT4_FAST_MA_PERIOD', '10'))
        self.slow_ma_period = int(self.get_env('MT4_SLOW_MA_PERIOD', '20'))
        self.signal_ma_period = int(self.get_env('MT4_SIGNAL_MA_PERIOD', '5'))
        self.ma_shift = int(self.get_env('MT4_MA_SHIFT', '0'))
        self.ma_method = int(self.get_env('MT4_MA_METHOD', '1'))  # 1=EMA, 0=SMA
        self.ma_price = int(self.get_env('MT4_MA_PRICE', '0'))    # 0=Close
        
    def validate(self) -> bool:
        """验证配置是否有效"""
        if not self.login or not self.password:
            return False
        if self.lot_size <= 0 or self.grid_levels <= 0:
            return False
        return True 