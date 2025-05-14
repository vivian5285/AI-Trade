import logging
import time
import hmac
import hashlib
import requests
from binance.client import Client
from binance.exceptions import BinanceAPIException
from typing import Dict, List, Optional, Union
import json
import ccxt

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('exchange_api.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class ExchangeAPI:
    def __init__(self, exchange: str, api_key: str, api_secret: str):
        self.exchange = exchange.lower()
        self.api_key = api_key
        self.api_secret = api_secret
        self.client = None
        self.initialize_client()

    def initialize_client(self):
        """初始化交易所客户端"""
        try:
            if self.exchange == 'binance':
                self.client = Client(self.api_key, self.api_secret)
                logger.info(f"Successfully initialized {self.exchange} client")
            elif self.exchange == 'lbank':
                self.client = ccxt.lbank({
                    'apiKey': self.api_key,
                    'secret': self.api_secret,
                    'enableRateLimit': True
                })
                logger.info(f"Successfully initialized {self.exchange} client")
            else:
                logger.error(f"Unsupported exchange: {self.exchange}")
                raise ValueError(f"Unsupported exchange: {self.exchange}")
        except Exception as e:
            logger.error(f"Error initializing {self.exchange} client: {str(e)}")
            raise

    def get_account_balance(self) -> Dict:
        """获取账户余额"""
        try:
            if self.exchange == 'binance':
                account = self.client.futures_account()
                return {
                    'total_balance': float(account['totalWalletBalance']),
                    'unrealized_pnl': float(account['totalUnrealizedProfit']),
                    'available_balance': float(account['availableBalance']),
                    'positions': self._get_positions(account['positions'])
                }
            elif self.exchange == 'lbank':
                balance = self.client.fetch_balance()
                return {
                    'total_balance': float(balance['total']['USDT']),
                    'unrealized_pnl': 0.0,  # LBank可能不支持
                    'available_balance': float(balance['free']['USDT']),
                    'positions': self._get_lbank_positions(balance)
                }
        except Exception as e:
            logger.error(f"Error getting account balance: {str(e)}")
            raise

    def _get_positions(self, positions: List[Dict]) -> List[Dict]:
        """处理Binance持仓信息"""
        active_positions = []
        for position in positions:
            if float(position['positionAmt']) != 0:
                active_positions.append({
                    'symbol': position['symbol'],
                    'amount': float(position['positionAmt']),
                    'entry_price': float(position['entryPrice']),
                    'mark_price': float(position['markPrice']),
                    'unrealized_pnl': float(position['unRealizedProfit']),
                    'leverage': float(position['leverage']),
                    'side': 'LONG' if float(position['positionAmt']) > 0 else 'SHORT'
                })
        return active_positions

    def _get_lbank_positions(self, balance: Dict) -> List[Dict]:
        """处理LBank持仓信息"""
        active_positions = []
        for currency, amount in balance['total'].items():
            if currency != 'USDT' and amount > 0:
                active_positions.append({
                    'symbol': f"{currency}/USDT",
                    'amount': float(amount),
                    'entry_price': 0.0,  # LBank可能不支持
                    'mark_price': float(balance['info'].get('markPrice', 0)),
                    'unrealized_pnl': 0.0,  # LBank可能不支持
                    'leverage': 1.0,  # LBank可能不支持
                    'side': 'LONG'
                })
        return active_positions

    def get_market_data(self, symbol: str, interval: str = '1m', limit: int = 100) -> List[Dict]:
        """获取市场数据"""
        try:
            if self.exchange == 'binance':
                klines = self.client.futures_klines(
                    symbol=symbol,
                    interval=interval,
                    limit=limit
                )
                return [{
                    'timestamp': k[0],
                    'open': float(k[1]),
                    'high': float(k[2]),
                    'low': float(k[3]),
                    'close': float(k[4]),
                    'volume': float(k[5])
                } for k in klines]
            elif self.exchange == 'lbank':
                ohlcv = self.client.fetch_ohlcv(symbol, interval, limit=limit)
                return [{
                    'timestamp': candle[0],
                    'open': float(candle[1]),
                    'high': float(candle[2]),
                    'low': float(candle[3]),
                    'close': float(candle[4]),
                    'volume': float(candle[5])
                } for candle in ohlcv]
        except Exception as e:
            logger.error(f"Error getting market data: {str(e)}")
            raise

    def place_order(self, symbol: str, side: str, quantity: float, 
                   order_type: str = 'MARKET', price: Optional[float] = None,
                   stop_price: Optional[float] = None, 
                   stop_loss: Optional[float] = None,
                   take_profit: Optional[float] = None) -> Dict:
        """下单"""
        try:
            if self.exchange == 'binance':
                # 设置杠杆
                self.client.futures_change_leverage(symbol=symbol, leverage=20)
                
                # 主订单
                order = self.client.futures_create_order(
                    symbol=symbol,
                    side=side,
                    type=order_type,
                    quantity=quantity,
                    price=price,
                    stopPrice=stop_price
                )
                
                # 设置止损
                if stop_loss:
                    self.client.futures_create_order(
                        symbol=symbol,
                        side='SELL' if side == 'BUY' else 'BUY',
                        type='STOP_MARKET',
                        stopPrice=stop_loss,
                        closePosition=True
                    )
                
                # 设置止盈
                if take_profit:
                    self.client.futures_create_order(
                        symbol=symbol,
                        side='SELL' if side == 'BUY' else 'BUY',
                        type='TAKE_PROFIT_MARKET',
                        stopPrice=take_profit,
                        closePosition=True
                    )
                
                logger.info(f"Order placed successfully: {json.dumps(order)}")
                return order
            elif self.exchange == 'lbank':
                # LBank下单
                order = self.client.create_order(
                    symbol=symbol,
                    type=order_type.lower(),
                    side=side.lower(),
                    amount=quantity,
                    price=price
                )
                logger.info(f"Order placed successfully: {json.dumps(order)}")
                return order
                
        except Exception as e:
            logger.error(f"Error placing order: {str(e)}")
            raise

    def cancel_order(self, symbol: str, order_id: str) -> Dict:
        """取消订单"""
        try:
            if self.exchange == 'binance':
                result = self.client.futures_cancel_order(
                    symbol=symbol,
                    orderId=order_id
                )
                logger.info(f"Order cancelled successfully: {json.dumps(result)}")
                return result
            elif self.exchange == 'lbank':
                result = self.client.cancel_order(order_id, symbol)
                logger.info(f"Order cancelled successfully: {json.dumps(result)}")
                return result
        except Exception as e:
            logger.error(f"Error cancelling order: {str(e)}")
            raise

    def get_order_status(self, symbol: str, order_id: str) -> Dict:
        """获取订单状态"""
        try:
            if self.exchange == 'binance':
                order = self.client.futures_get_order(
                    symbol=symbol,
                    orderId=order_id
                )
                return order
            elif self.exchange == 'lbank':
                order = self.client.fetch_order(order_id, symbol)
                return order
        except Exception as e:
            logger.error(f"Error getting order status: {str(e)}")
            raise

    def get_trading_rules(self, symbol: str) -> Dict:
        """获取交易规则"""
        try:
            if self.exchange == 'binance':
                exchange_info = self.client.futures_exchange_info()
                symbol_info = next((s for s in exchange_info['symbols'] if s['symbol'] == symbol), None)
                if symbol_info:
                    return {
                        'min_qty': float(symbol_info['filters'][1]['minQty']),
                        'max_qty': float(symbol_info['filters'][1]['maxQty']),
                        'step_size': float(symbol_info['filters'][1]['stepSize']),
                        'min_price': float(symbol_info['filters'][0]['minPrice']),
                        'max_price': float(symbol_info['filters'][0]['maxPrice']),
                        'tick_size': float(symbol_info['filters'][0]['tickSize'])
                    }
            elif self.exchange == 'lbank':
                markets = self.client.load_markets()
                market = markets.get(symbol)
                if market:
                    return {
                        'min_qty': float(market['limits']['amount']['min']),
                        'max_qty': float(market['limits']['amount']['max']),
                        'step_size': float(market['precision']['amount']),
                        'min_price': float(market['limits']['price']['min']),
                        'max_price': float(market['limits']['price']['max']),
                        'tick_size': float(market['precision']['price'])
                    }
        except Exception as e:
            logger.error(f"Error getting trading rules: {str(e)}")
            raise

    def get_funding_rate(self, symbol: str) -> float:
        """获取资金费率"""
        try:
            if self.exchange == 'binance':
                funding_rate = self.client.futures_funding_rate(symbol=symbol, limit=1)
                return float(funding_rate[0]['fundingRate'])
            elif self.exchange == 'lbank':
                # LBank可能不支持资金费率
                return 0.0
        except Exception as e:
            logger.error(f"Error getting funding rate: {str(e)}")
            raise

    def get_market_depth(self, symbol: str, limit: int = 20) -> Dict:
        """获取市场深度"""
        try:
            if self.exchange == 'binance':
                depth = self.client.futures_order_book(symbol=symbol, limit=limit)
                return {
                    'bids': [[float(price), float(qty)] for price, qty in depth['bids']],
                    'asks': [[float(price), float(qty)] for price, qty in depth['asks']]
                }
            elif self.exchange == 'lbank':
                depth = self.client.fetch_order_book(symbol, limit)
                return {
                    'bids': [[float(price), float(qty)] for price, qty in depth['bids']],
                    'asks': [[float(price), float(qty)] for price, qty in depth['asks']]
                }
        except Exception as e:
            logger.error(f"Error getting market depth: {str(e)}")
            raise

    def get_recent_trades(self, symbol: str, limit: int = 50) -> List[Dict]:
        """获取最近成交"""
        try:
            if self.exchange == 'binance':
                trades = self.client.futures_account_trades(symbol=symbol, limit=limit)
                return [{
                    'id': trade['id'],
                    'price': float(trade['price']),
                    'qty': float(trade['qty']),
                    'quote_qty': float(trade['quoteQty']),
                    'time': trade['time'],
                    'side': trade['side'],
                    'realized_pnl': float(trade['realizedPnl'])
                } for trade in trades]
            elif self.exchange == 'lbank':
                trades = self.client.fetch_my_trades(symbol, limit=limit)
                return [{
                    'id': trade['id'],
                    'price': float(trade['price']),
                    'qty': float(trade['amount']),
                    'quote_qty': float(trade['cost']),
                    'time': trade['timestamp'],
                    'side': trade['side'],
                    'realized_pnl': 0.0  # LBank可能不支持
                } for trade in trades]
        except Exception as e:
            logger.error(f"Error getting recent trades: {str(e)}")
            raise 