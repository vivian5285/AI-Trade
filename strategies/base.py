from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
import pandas as pd
from trading.base import BaseTrading

class BaseStrategy(ABC):
    """基础策略类"""
    
    def __init__(self, trading: BaseTrading, config: Dict[str, Any]):
        self.trading = trading
        self.config = config
        self.position = None
        self.orders = []
        self.trades = []
        
    @abstractmethod
    def initialize(self) -> bool:
        """初始化策略"""
        pass
        
    @abstractmethod
    def on_tick(self, tick_data: Dict[str, Any]) -> None:
        """处理行情数据"""
        pass
        
    @abstractmethod
    def on_order(self, order_data: Dict[str, Any]) -> None:
        """处理订单更新"""
        pass
        
    @abstractmethod
    def on_trade(self, trade_data: Dict[str, Any]) -> None:
        """处理成交更新"""
        pass
        
    @abstractmethod
    def calculate_signals(self, data: pd.DataFrame) -> Dict[str, Any]:
        """计算交易信号"""
        pass
        
    @abstractmethod
    def should_open_position(self, signals: Dict[str, Any]) -> bool:
        """判断是否开仓"""
        pass
        
    @abstractmethod
    def should_close_position(self, signals: Dict[str, Any]) -> bool:
        """判断是否平仓"""
        pass
        
    @abstractmethod
    def calculate_position_size(self) -> float:
        """计算仓位大小"""
        pass
        
    @abstractmethod
    def calculate_stop_loss(self, entry_price: float, side: str) -> float:
        """计算止损价格"""
        pass
        
    @abstractmethod
    def calculate_take_profit(self, entry_price: float, side: str) -> float:
        """计算止盈价格"""
        pass
        
    def update_position(self, position_data: Dict[str, Any]) -> None:
        """更新持仓信息"""
        self.position = position_data
        
    def update_orders(self, orders_data: List[Dict[str, Any]]) -> None:
        """更新订单信息"""
        self.orders = orders_data
        
    def update_trades(self, trades_data: List[Dict[str, Any]]) -> None:
        """更新成交信息"""
        self.trades = trades_data
        
    def get_position(self) -> Optional[Dict[str, Any]]:
        """获取当前持仓"""
        return self.position
        
    def get_orders(self) -> List[Dict[str, Any]]:
        """获取当前订单"""
        return self.orders
        
    def get_trades(self) -> List[Dict[str, Any]]:
        """获取成交历史"""
        return self.trades 