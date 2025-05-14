import os
import json
import time
import logging
from datetime import datetime
from strategies.combined_strategy import CombinedStrategy
from trading.binance_trading import BinanceTrading
from trading.lbank_trading import LBankTrading

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

def load_config(config_path: str) -> dict:
    """加载配置文件"""
    try:
        with open(config_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"加载配置文件失败: {str(e)}")
        raise

def initialize_trading(exchange: str) -> object:
    """初始化交易接口"""
    try:
        if exchange.lower() == 'binance':
            return BinanceTrading()
        elif exchange.lower() == 'lbank':
            return LBankTrading()
        else:
            raise ValueError(f"不支持的交易所: {exchange}")
    except Exception as e:
        logger.error(f"初始化交易接口失败: {str(e)}")
        raise

def main():
    """主函数"""
    try:
        # 加载配置
        config = load_config('config/combined_strategy.json')
        logger.info(f"加载配置成功: {config['strategy_name']}")
        
        # 初始化交易接口
        exchange = os.getenv('EXCHANGE', 'binance')
        trading = initialize_trading(exchange)
        logger.info(f"初始化交易接口成功: {exchange}")
        
        # 初始化策略
        strategy = CombinedStrategy(trading, config)
        if not strategy.initialize():
            raise Exception("策略初始化失败")
        logger.info("策略初始化成功")
        
        # 运行策略
        logger.info("开始运行策略...")
        while True:
            try:
                # 获取市场数据
                for pair in config['trading_pairs']:
                    tick_data = trading.get_tick_data(pair['symbol'])
                    if tick_data:
                        strategy.on_tick(tick_data)
                
                # 等待下一个周期
                time.sleep(1)
                
            except Exception as e:
                logger.error(f"策略运行错误: {str(e)}")
                time.sleep(60)  # 发生错误时等待一分钟后继续
                
    except Exception as e:
        logger.error(f"程序运行错误: {str(e)}")
        raise

if __name__ == "__main__":
    main() 