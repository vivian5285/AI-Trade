import os
import json
import time
import logging
from exchange_api import ExchangeAPI
from strategy_engine import StrategyEngine
from datetime import datetime
import pandas as pd
import numpy as np

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('trading.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class TradingBot:
    def __init__(self, config_path: str):
        self.config = self.load_config(config_path)
        self.exchange_api = self.initialize_exchange()
        self.strategy_engines = {}
        self.initialize_strategies()
        self.trading_stats = {
            'start_time': datetime.now(),
            'total_trades': 0,
            'winning_trades': 0,
            'losing_trades': 0,
            'total_pnl': 0.0,
            'max_drawdown': 0.0,
            'current_drawdown': 0.0,
            'peak_balance': 0.0
        }

    def load_config(self, config_path: str) -> dict:
        """加载配置文件"""
        try:
            with open(config_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading config: {str(e)}")
            raise

    def initialize_exchange(self) -> ExchangeAPI:
        """初始化交易所API"""
        try:
            api_key = os.getenv('BINANCE_API_KEY')
            api_secret = os.getenv('BINANCE_API_SECRET')
            
            if not api_key or not api_secret:
                raise ValueError("API credentials not found in environment variables")
            
            return ExchangeAPI('binance', api_key, api_secret)
        except Exception as e:
            logger.error(f"Error initializing exchange: {str(e)}")
            raise

    def initialize_strategies(self):
        """初始化交易策略"""
        try:
            for pair in self.config['trading_pairs']:
                self.strategy_engines[pair['symbol']] = StrategyEngine(
                    self.exchange_api,
                    self.config['parameters']
                )
            logger.info(f"Initialized strategies for {len(self.strategy_engines)} trading pairs")
        except Exception as e:
            logger.error(f"Error initializing strategies: {str(e)}")
            raise

    def update_trading_stats(self, pnl: float):
        """更新交易统计信息"""
        self.trading_stats['total_trades'] += 1
        self.trading_stats['total_pnl'] += pnl
        
        if pnl > 0:
            self.trading_stats['winning_trades'] += 1
        else:
            self.trading_stats['losing_trades'] += 1
        
        # 更新最大回撤
        current_balance = self.trading_stats['total_pnl']
        if current_balance > self.trading_stats['peak_balance']:
            self.trading_stats['peak_balance'] = current_balance
        else:
            current_drawdown = (self.trading_stats['peak_balance'] - current_balance) / self.trading_stats['peak_balance']
            self.trading_stats['current_drawdown'] = current_drawdown
            self.trading_stats['max_drawdown'] = max(self.trading_stats['max_drawdown'], current_drawdown)

    def check_risk_limits(self) -> bool:
        """检查风险限制"""
        try:
            # 检查每日交易次数
            if self.trading_stats['total_trades'] >= self.config['parameters']['max_daily_trades']:
                logger.warning("Maximum daily trades reached")
                return False
            
            # 检查每日亏损限制
            if self.trading_stats['total_pnl'] < -self.config['parameters']['max_daily_loss']:
                logger.warning("Maximum daily loss reached")
                return False
            
            # 检查最大回撤限制
            if self.trading_stats['max_drawdown'] > self.config['parameters']['max_drawdown']:
                logger.warning("Maximum drawdown reached")
                return False
            
            return True
        except Exception as e:
            logger.error(f"Error checking risk limits: {str(e)}")
            return False

    def run(self):
        """运行交易策略"""
        logger.info("Starting trading bot...")
        
        while True:
            try:
                if not self.check_risk_limits():
                    logger.info("Risk limits reached, stopping trading")
                    break

                for symbol, engine in self.strategy_engines.items():
                    # 获取市场数据
                    market_data = self.exchange_api.get_market_data(symbol, limit=200)
                    
                    # 计算技术指标
                    indicators = engine.calculate_indicators(market_data)
                    
                    # 生成交易信号
                    signal = engine.generate_signal(indicators)
                    
                    if signal:
                        # 执行交易信号
                        order = engine.execute_signal(signal, symbol)
                        logger.info(f"Executed order for {symbol}: {json.dumps(order)}")
                    
                    # 更新持仓状态
                    engine.update_position_status(symbol)
                    
                    # 获取策略统计信息
                    stats = engine.get_strategy_stats()
                    self.update_trading_stats(stats['total_pnl'])
                    
                    # 记录交易统计
                    logger.info(f"Trading stats for {symbol}: {json.dumps(stats)}")
                
                # 等待下一个交易周期
                time.sleep(self.config['parameters']['min_signal_interval'])
                
            except Exception as e:
                logger.error(f"Error in main loop: {str(e)}")
                time.sleep(60)  # 发生错误时等待一分钟后继续

    def save_trading_stats(self):
        """保存交易统计信息"""
        try:
            stats_df = pd.DataFrame([{
                'timestamp': datetime.now(),
                'total_trades': self.trading_stats['total_trades'],
                'winning_trades': self.trading_stats['winning_trades'],
                'losing_trades': self.trading_stats['losing_trades'],
                'win_rate': self.trading_stats['winning_trades'] / self.trading_stats['total_trades'] if self.trading_stats['total_trades'] > 0 else 0,
                'total_pnl': self.trading_stats['total_pnl'],
                'max_drawdown': self.trading_stats['max_drawdown'],
                'current_drawdown': self.trading_stats['current_drawdown']
            }])
            
            stats_df.to_csv('trading_stats.csv', mode='a', header=not os.path.exists('trading_stats.csv'))
            logger.info("Trading stats saved successfully")
        except Exception as e:
            logger.error(f"Error saving trading stats: {str(e)}")

def main():
    try:
        # 创建交易机器人实例
        bot = TradingBot('strategy_config.json')
        
        # 运行策略
        bot.run()
        
        # 保存交易统计
        bot.save_trading_stats()
        
    except KeyboardInterrupt:
        logger.info("Trading bot stopped by user")
    except Exception as e:
        logger.error(f"Error in main: {str(e)}")
    finally:
        logger.info("Trading bot stopped")

if __name__ == "__main__":
    main() 