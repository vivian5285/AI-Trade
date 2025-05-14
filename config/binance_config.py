from .base_config import BaseConfig
from typing import Dict, Any

class BinanceConfig(BaseConfig):
    """币安配置类"""
    def __init__(self):
        super().__init__()
        self.api_key = self.get_env('BINANCE_API_KEY')
        self.api_secret = self.get_env('BINANCE_API_SECRET')
        self.trading_pair = self.get_env('TRADING_PAIR', 'BTCUSDT')
        self.leverage = int(self.get_env('LEVERAGE', '20'))
        self.quantity = float(self.get_env('QUANTITY', '0.001'))
        self.stop_loss_percentage = float(self.get_env('STOP_LOSS_PERCENTAGE', '2.0'))
        self.take_profit_percentage = float(self.get_env('TAKE_PROFIT_PERCENTAGE', '4.0'))
        self.max_daily_trades = int(self.get_env('MAX_DAILY_TRADES', '10'))
        self.max_daily_loss_percentage = float(self.get_env('MAX_DAILY_LOSS_PERCENTAGE', '5.0'))
        self.min_volume_threshold = float(self.get_env('MIN_VOLUME_THRESHOLD', '1000000'))
        self.grid_size = int(self.get_env('GRID_SIZE', '5'))
        self.grid_spacing = float(self.get_env('GRID_SPACING', '100'))
        self.trend_ema_fast = int(self.get_env('TREND_EMA_FAST', '12'))
        self.trend_ema_slow = int(self.get_env('TREND_EMA_SLOW', '26'))
        self.scalping_profit_target = float(self.get_env('SCALPING_PROFIT_TARGET', '0.5'))
        self.scalping_stop_loss = float(self.get_env('SCALPING_STOP_LOSS', '0.3'))
        
    def validate(self) -> bool:
        """验证配置是否有效"""
        if not self.api_key or not self.api_secret:
            return False
        if self.leverage <= 0 or self.quantity <= 0:
            return False
        return True 