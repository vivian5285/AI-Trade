from typing import Dict, List
import threading
import time
import logging

class TradingBotManager:
    def __init__(self):
        self.bots: Dict[str, 'TradingBot'] = {}
        self.lock = threading.Lock()
        self.logger = logging.getLogger(__name__)

    def add_bot(self, bot_id: str, bot: 'TradingBot') -> bool:
        with self.lock:
            if bot_id in self.bots:
                return False
            self.bots[bot_id] = bot
            return True

    def remove_bot(self, bot_id: str) -> bool:
        with self.lock:
            if bot_id not in self.bots:
                return False
            del self.bots[bot_id]
            return True

    def get_bot(self, bot_id: str) -> 'TradingBot':
        return self.bots.get(bot_id)

    def get_all_bots(self) -> List['TradingBot']:
        return list(self.bots.values())

    def start_bot(self, bot_id: str) -> bool:
        bot = self.get_bot(bot_id)
        if not bot:
            return False
        try:
            bot.start()
            return True
        except Exception as e:
            self.logger.error(f"Failed to start bot {bot_id}: {str(e)}")
            return False

    def stop_bot(self, bot_id: str) -> bool:
        bot = self.get_bot(bot_id)
        if not bot:
            return False
        try:
            bot.stop()
            return True
        except Exception as e:
            self.logger.error(f"Failed to stop bot {bot_id}: {str(e)}")
            return False

# 创建全局实例
trading_bot_manager = TradingBotManager() 