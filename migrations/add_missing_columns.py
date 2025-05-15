import sqlite3

def upgrade():
    # 连接到数据库
    conn = sqlite3.connect('trading.db')
    cursor = conn.cursor()
    
    try:
        # 添加缺失的列
        cursor.execute('ALTER TABLE trade_history ADD COLUMN position_type VARCHAR(10)')
        cursor.execute('ALTER TABLE trade_history ADD COLUMN pnl FLOAT')
        cursor.execute('ALTER TABLE trade_history ADD COLUMN pnl_percentage FLOAT')
        
        # 提交更改
        conn.commit()
        print("Successfully added missing columns to trade_history table")
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

def downgrade():
    # 连接到数据库
    conn = sqlite3.connect('trading.db')
    cursor = conn.cursor()
    
    try:
        # 创建一个临时表，不包含新添加的列
        cursor.execute('''
            CREATE TABLE trade_history_temp (
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
        
        # 复制数据到临时表
        cursor.execute('''
            INSERT INTO trade_history_temp 
            SELECT id, exchange, symbol, side, price, quantity, 
                   timestamp, status, strategy, strategy_params 
            FROM trade_history
        ''')
        
        # 删除原表
        cursor.execute('DROP TABLE trade_history')
        
        # 重命名临时表
        cursor.execute('ALTER TABLE trade_history_temp RENAME TO trade_history')
        
        conn.commit()
        print("Successfully removed added columns from trade_history table")
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

if __name__ == '__main__':
    upgrade() 