import sqlite3

def upgrade():
    # 连接到数据库
    conn = sqlite3.connect('trading.db')
    cursor = conn.cursor()
    
    try:
        # 添加 strategy 列
        cursor.execute('ALTER TABLE trade_history ADD COLUMN strategy VARCHAR(20)')
        
        # 提交更改
        conn.commit()
        print("Successfully added strategy column to trade_history table")
    except Exception as e:
        conn.rollback()
        print(f"Error adding strategy column: {str(e)}")
        raise e
    finally:
        conn.close()

def downgrade():
    # 连接到数据库
    conn = sqlite3.connect('trading.db')
    cursor = conn.cursor()
    
    try:
        # 创建一个临时表，不包含 strategy 列
        cursor.execute('''
            CREATE TABLE trade_history_temp (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bot_id INTEGER,
                exchange VARCHAR(20) NOT NULL,
                symbol VARCHAR(20) NOT NULL,
                side VARCHAR(10) NOT NULL,
                position_type VARCHAR(10) NOT NULL,
                price FLOAT NOT NULL,
                quantity FLOAT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                status VARCHAR(20) NOT NULL,
                strategy_params VARCHAR(255),
                pnl FLOAT,
                pnl_percentage FLOAT
            )
        ''')
        
        # 复制数据到临时表
        cursor.execute('''
            INSERT INTO trade_history_temp 
            SELECT id, bot_id, exchange, symbol, side, position_type, 
                   price, quantity, timestamp, status, strategy_params,
                   pnl, pnl_percentage
            FROM trade_history
        ''')
        
        # 删除原表
        cursor.execute('DROP TABLE trade_history')
        
        # 重命名临时表
        cursor.execute('ALTER TABLE trade_history_temp RENAME TO trade_history')
        
        conn.commit()
        print("Successfully removed strategy column from trade_history table")
    except Exception as e:
        conn.rollback()
        print(f"Error removing strategy column: {str(e)}")
        raise e
    finally:
        conn.close()

if __name__ == '__main__':
    upgrade() 