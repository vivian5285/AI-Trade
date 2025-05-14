import sqlite3
import os

def fix_database():
    # 数据库文件路径
    db_path = 'instance/trade.db'
    
    # 如果数据库文件存在，先备份
    if os.path.exists(db_path):
        backup_path = f"{db_path}.backup"
        os.rename(db_path, backup_path)
        print(f"Created backup at {backup_path}")
    
    # 创建新的数据库连接
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # 创建 trade_history 表
        cursor.execute('''
        CREATE TABLE trade_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            exchange VARCHAR(50) NOT NULL,
            symbol VARCHAR(20) NOT NULL,
            side VARCHAR(10) NOT NULL,
            price DECIMAL(20, 8) NOT NULL,
            quantity DECIMAL(20, 8) NOT NULL,
            timestamp DATETIME NOT NULL,
            status VARCHAR(20) NOT NULL,
            strategy VARCHAR(50),
            strategy_params TEXT
        )
        ''')
        
        # 创建 api_key 表
        cursor.execute('''
        CREATE TABLE api_key (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            exchange VARCHAR(50) NOT NULL,
            api_key VARCHAR(255) NOT NULL,
            api_secret VARCHAR(255) NOT NULL,
            is_active BOOLEAN NOT NULL DEFAULT 1
        )
        ''')
        
        # 提交更改
        conn.commit()
        print("Database structure fixed successfully")
        
    except Exception as e:
        print(f"Error fixing database: {str(e)}")
        # 如果出错，恢复备份
        if os.path.exists(backup_path):
            os.remove(db_path)
            os.rename(backup_path, db_path)
            print("Restored database from backup")
    
    finally:
        conn.close()

if __name__ == '__main__':
    fix_database() 