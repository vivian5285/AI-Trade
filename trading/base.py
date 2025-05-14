from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
import pandas as pd

class BaseTrading(ABC):
    """基础交易接口"""
    
    @abstractmethod
    def connect(self) -> bool:
        """连接交易所"""
        pass
        
    @abstractmethod
    def disconnect(self) -> bool:
        """断开连接"""
        pass
        
    @abstractmethod
    def get_balance(self) -> float:
        """获取账户余额"""
        pass
        
    @abstractmethod
    def get_position(self) -> Dict[str, Any]:
        """获取当前持仓"""
        pass
        
    @abstractmethod
    def get_historical_data(self, interval: str = '1m', limit: int = 100) -> pd.DataFrame:
        """获取历史数据"""
        pass
        
    @abstractmethod
    def place_order(self, side: str, order_type: str, quantity: float, 
                   price: Optional[float] = None) -> Dict[str, Any]:
        """下单"""
        pass
        
    @abstractmethod
    def cancel_order(self, order_id: str) -> bool:
        """取消订单"""
        pass
        
    @abstractmethod
    def get_order(self, order_id: str) -> Dict[str, Any]:
        """获取订单信息"""
        pass
        
    @abstractmethod
    def get_open_orders(self) -> List[Dict[str, Any]]:
        """获取未完成订单"""
        pass
        
    @abstractmethod
    def get_trades(self) -> List[Dict[str, Any]]:
        """获取交易历史"""
        pass
        
    @abstractmethod
    def set_leverage(self, leverage: int) -> bool:
        """设置杠杆"""
        pass
        
    @abstractmethod
    def get_ticker(self) -> Dict[str, Any]:
        """获取当前行情"""
        pass 