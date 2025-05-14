import os
import sys
import logging
from dotenv import load_dotenv
from trading_bot import BinanceTradingBot
from lbank_trading.trading_bot import LBankTradingBot

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('trading_bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def main():
    # 加载环境变量
    load_dotenv()
    
    # 获取当前选择的交易所
    current_exchange = os.getenv('CURRENT_EXCHANGE', 'binance').lower()
    
    try:
        if current_exchange == 'binance':
            logger.info("启动 Binance 交易机器人...")
            bot = BinanceTradingBot()
        elif current_exchange == 'lbank':
            logger.info("启动 LBank 交易机器人...")
            bot = LBankTradingBot()
        else:
            logger.error(f"不支持的交易所: {current_exchange}")
            sys.exit(1)
            
        # 运行交易机器人
        bot.run()
        
    except KeyboardInterrupt:
        logger.info("交易机器人被用户停止")
    except Exception as e:
        logger.error(f"交易机器人运行错误: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main() 