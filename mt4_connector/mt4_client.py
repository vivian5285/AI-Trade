import socket
import json
import time
from typing import Dict, List, Any, Optional
import pandas as pd
from trading.base import BaseTrading

class MT4Client(BaseTrading):
    """MT4客户端"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.socket = None
        self.connected = False
        
    def connect(self) -> bool:
        """连接MT4服务器"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.config['server'], 8222))
            self.connected = True
            return True
        except Exception as e:
            print(f"连接MT4服务器失败: {e}")
            return False
            
    def disconnect(self) -> bool:
        """断开连接"""
        if self.socket:
            self.socket.close()
            self.connected = False
        return True
        
    def _send_command(self, command: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """发送命令到MT4"""
        if not self.connected:
            raise Exception("未连接到MT4服务器")
            
        data = {
            'command': command,
            'params': params or {}
        }
        
        self.socket.send(json.dumps(data).encode())
        response = self.socket.recv(4096)
        return json.loads(response.decode())
        
    def get_balance(self) -> float:
        """获取账户余额"""
        response = self._send_command('GET_BALANCE')
        return float(response.get('balance', 0))
        
    def get_position(self) -> Dict[str, Any]:
        """获取当前持仓"""
        response = self._send_command('GET_POSITION', {
            'symbol': self.config['symbol']
        })
        return response.get('position', {})
        
    def get_historical_data(self, interval: str = '1m', limit: int = 100) -> pd.DataFrame:
        """获取历史数据"""
        response = self._send_command('GET_HISTORY', {
            'symbol': self.config['symbol'],
            'interval': interval,
            'limit': limit
        })
        
        data = response.get('data', [])
        df = pd.DataFrame(data)
        if not df.empty:
            df['time'] = pd.to_datetime(df['time'])
            df.set_index('time', inplace=True)
        return df
        
    def place_order(self, side: str, order_type: str, quantity: float, 
                   price: Optional[float] = None) -> Dict[str, Any]:
        """下单"""
        params = {
            'symbol': self.config['symbol'],
            'type': side,
            'volume': quantity,
            'price': price,
            'magic': self.config['magic_number']
        }
        
        response = self._send_command('PLACE_ORDER', params)
        return response.get('order', {})
        
    def cancel_order(self, order_id: str) -> bool:
        """取消订单"""
        response = self._send_command('CANCEL_ORDER', {
            'order_id': order_id
        })
        return response.get('success', False)
        
    def get_order(self, order_id: str) -> Dict[str, Any]:
        """获取订单信息"""
        response = self._send_command('GET_ORDER', {
            'order_id': order_id
        })
        return response.get('order', {})
        
    def get_open_orders(self) -> List[Dict[str, Any]]:
        """获取未完成订单"""
        response = self._send_command('GET_OPEN_ORDERS', {
            'symbol': self.config['symbol']
        })
        return response.get('orders', [])
        
    def get_trades(self) -> List[Dict[str, Any]]:
        """获取交易历史"""
        response = self._send_command('GET_TRADES', {
            'symbol': self.config['symbol']
        })
        return response.get('trades', [])
        
    def set_leverage(self, leverage: int) -> bool:
        """设置杠杆"""
        response = self._send_command('SET_LEVERAGE', {
            'symbol': self.config['symbol'],
            'leverage': leverage
        })
        return response.get('success', False)
        
    def get_ticker(self) -> Dict[str, Any]:
        """获取当前行情"""
        response = self._send_command('GET_TICKER', {
            'symbol': self.config['symbol']
        })
        return response.get('ticker', {}) 