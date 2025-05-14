import logging
from app import db, APIKey
from datetime import datetime

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def add_api_key():
    try:
        logger.info("Starting to add API key...")
        
        # 检查是否已存在
        existing_key = APIKey.query.filter_by(exchange='Binance').first()
        if existing_key:
            logger.info("API key already exists")
            return

        # 创建新的API密钥记录
        api_key = APIKey(
            exchange='Binance',
            api_key='KbPt21dSnWRh9GVGjQbbVJrTepH0EWofGHrNGD0FPxd00G4msDEWytGwb1IdZZpJ',
            api_secret='R9JcLm8AYhYlPXcZNPek37EaS32ScfHjOTJlBnqDO9cNycVgANFCCGFmBS9mNI74',
            created_at=datetime.utcnow(),
            is_active=True
        )

        # 添加到数据库
        logger.info("Adding API key to database...")
        db.session.add(api_key)
        db.session.commit()
        logger.info("API key added successfully")
    except Exception as e:
        logger.error(f"Error adding API key: {str(e)}")
        db.session.rollback()
        raise

if __name__ == '__main__':
    try:
        add_api_key()
    except Exception as e:
        logger.error(f"Script failed: {str(e)}")
        exit(1) 