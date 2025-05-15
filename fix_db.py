import sqlite3
import os

def fix_database():
    # 获取数据库文件路径
    db_path = 'trading.db'
    
    # 如果数据库文件存在，先删除它
    if os.path.exists(db_path):
        os.remove(db_path)
        print("已删除旧的数据库文件")
    
    # 创建新的数据库连接
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # 创建交易历史表
        cursor.execute('''
        CREATE TABLE trade_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            exchange VARCHAR(20) NOT NULL,
            symbol VARCHAR(20) NOT NULL,
            side VARCHAR(10) NOT NULL,
            price FLOAT NOT NULL,
            quantity FLOAT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            status VARCHAR(20) NOT NULL,
            strategy VARCHAR(20),
            strategy_params VARCHAR(255)
        )
        ''')
        
        # 创建API密钥表
        cursor.execute('''
        CREATE TABLE api_key (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            exchange VARCHAR(20) NOT NULL,
            api_key VARCHAR(100) NOT NULL,
            api_secret VARCHAR(100) NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            is_active BOOLEAN DEFAULT TRUE
        )
        ''')
        
        # 提交更改
        conn.commit()
        print("数据库修复成功！")
    except Exception as e:
        print(f"修复数据库时出错: {e}")
    finally:
        # 关闭连接
        conn.close()

if __name__ == '__main__':
    fix_database() 