from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
import os

# 创建 Flask 应用
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///trading.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# 初始化数据库
db = SQLAlchemy(app)
migrate = Migrate(app, db)

# 导入模型以确保它们被注册
from app import TradeHistory, TradingBotConfig, APIKey, TradingBotLog

if __name__ == '__main__':
    with app.app_context():
        # 运行迁移
        from alembic import command
        from alembic.config import Config
        
        # 创建 Alembic 配置
        alembic_cfg = Config("alembic.ini")
        
        # 运行迁移
        command.upgrade(alembic_cfg, "head")
        
        print("数据库迁移完成！") 