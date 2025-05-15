import sqlite3

def upgrade():
    # 连接到数据库
    conn = sqlite3.connect('trading.db')
    cursor = conn.cursor()
    
    try:
        # 创建新的表结构
        cursor.execute('''
        CREATE TABLE trade_history_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            exchange VARCHAR(20) NOT NULL,
            symbol VARCHAR(20) NOT NULL,
            side VARCHAR(10) NOT NULL,
            position_type VARCHAR(10) NOT NULL,
            price FLOAT NOT NULL,
            quantity FLOAT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            status VARCHAR(20) NOT NULL,
            strategy VARCHAR(20),
            strategy_params VARCHAR(255),
            pnl FLOAT,
            pnl_percentage FLOAT
        )
        ''')
        
        # 复制现有数据
        cursor.execute('''
        INSERT INTO trade_history_new (
            id, exchange, symbol, side, position_type, price, quantity, 
            timestamp, status
        )
        SELECT 
            id, exchange, symbol, side, position_type, price, quantity, 
            timestamp, status
        FROM trade_history
        ''')
        
        # 删除旧表
        cursor.execute('DROP TABLE trade_history')
        
        # 重命名新表
        cursor.execute('ALTER TABLE trade_history_new RENAME TO trade_history')
        
        # 提交更改
        conn.commit()
        print("Successfully updated trade_history table structure")
    except Exception as e:
        conn.rollback()
        print(f"Error updating table: {str(e)}")
        raise e
    finally:
        conn.close()

if __name__ == '__main__':
    upgrade() 