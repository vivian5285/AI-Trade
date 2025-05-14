import sqlite3
import os

def update_database():
    # 获取数据库文件路径
    db_path = os.path.join('instance', 'trade.db')
    
    # 连接到数据库
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # 检查列是否存在
        cursor.execute("PRAGMA table_info(trade_history)")
        columns = [column[1] for column in cursor.fetchall()]
        
        # 如果列不存在，则添加
        if 'strategy' not in columns:
            cursor.execute('ALTER TABLE trade_history ADD COLUMN strategy VARCHAR(20)')
            print("已添加 strategy 列")
            
        if 'strategy_params' not in columns:
            cursor.execute('ALTER TABLE trade_history ADD COLUMN strategy_params VARCHAR(255)')
            print("已添加 strategy_params 列")
        
        # 提交更改
        conn.commit()
        print("数据库更新成功！")
    except sqlite3.OperationalError as e:
        print(f"更新数据库时出错: {e}")
    finally:
        # 关闭连接
        conn.close()

if __name__ == '__main__':
    update_database() 