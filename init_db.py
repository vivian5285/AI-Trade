from app import app, db, APIKey
from datetime import datetime

def init_db():
    with app.app_context():
        # 创建所有表
        db.create_all()
        
        # 检查是否已经有API密钥
        if not APIKey.query.first():
            # 添加Binance API密钥
            binance_key = APIKey(
                exchange='Binance',
                api_key='KbPt21dSnWRh9GVGjQbbVJrTepH0EWofGHrNGD0FPxd00G4msDEWytGwb1IdZZpJ',
                api_secret='R9JcLm8AYhYlPXcZNPek37EaS32ScfHjOTJlBnqDO9cNycVgANFCCGFmBS9mNI74',
                is_active=True
            )
            db.session.add(binance_key)
            
            # 添加LBank API密钥
            lbank_key = APIKey(
                exchange='LBank',
                api_key='a079f353-0461-4d7b-b435-0a4286df9e06',
                api_secret='598AB6A2A93FE411CF6F8C1401948874',
                is_active=True
            )
            db.session.add(lbank_key)
            
            # 提交更改
            db.session.commit()
            print("Database initialized with API keys")
        else:
            # 更新现有的API密钥
            binance_key = APIKey.query.filter_by(exchange='Binance').first()
            if binance_key:
                binance_key.api_key = 'KbPt21dSnWRh9GVGjQbbVJrTepH0EWofGHrNGD0FPxd00G4msDEWytGwb1IdZZpJ'
                binance_key.api_secret = 'R9JcLm8AYhYlPXcZNPek37EaS32ScfHjOTJlBnqDO9cNycVgANFCCGFmBS9mNI74'
                binance_key.is_active = True
            
            lbank_key = APIKey.query.filter_by(exchange='LBank').first()
            if lbank_key:
                lbank_key.api_key = 'a079f353-0461-4d7b-b435-0a4286df9e06'
                lbank_key.api_secret = '598AB6A2A93FE411CF6F8C1401948874'
                lbank_key.is_active = True
            
            db.session.commit()
            print("API keys updated")

if __name__ == '__main__':
    init_db() 