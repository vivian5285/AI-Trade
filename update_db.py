import sqlite3
import os

def update_database():
    # 获取数据库文件路径
    db_path = os.path.join('instance', 'trade.db')
    
    # 连接到数据库
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # 添加新列
        cursor.execute('ALTER TABLE trade_history ADD COLUMN strategy VARCHAR(20)')
        cursor.execute('ALTER TABLE trade_history ADD COLUMN strategy_params VARCHAR(255)')
        
        # 提交更改
        conn.commit()
        print("数据库更新成功！")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e):
            print("列已存在，无需更新。")
        else:
            print(f"更新数据库时出错: {e}")
    finally:
        # 关闭连接
        conn.close()

if __name__ == '__main__':
    update_database() 