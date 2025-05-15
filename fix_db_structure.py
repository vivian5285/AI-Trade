import sqlite3
import os
import shutil
from datetime import datetime

def backup_database():
    """备份数据库文件"""
    db_path = 'instance/trade.db'
    if os.path.exists(db_path):
        backup_path = f'instance/trade_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.db'
        shutil.copy2(db_path, backup_path)
        print(f"数据库已备份到: {backup_path}")
        return True
    return False

def column_exists(cursor, table_name, column_name):
    """检查列是否存在"""
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = cursor.fetchall()
    return any(col[1] == column_name for col in columns)

def fix_database():
    """修复数据库结构"""
    try:
        # 备份数据库
        if not backup_database():
            print("无法备份数据库，请确保数据库文件存在")
            return False

        # 连接到数据库
        conn = sqlite3.connect('instance/trade.db')
        cursor = conn.cursor()

        # 检查bot_id列是否存在
        if not column_exists(cursor, 'trade_history', 'bot_id'):
            # 添加bot_id列到trade_history表
            cursor.execute('''
                ALTER TABLE trade_history 
                ADD COLUMN bot_id INTEGER REFERENCES trading_bot_config(id)
            ''')
            print("成功添加bot_id列到trade_history表")
        else:
            print("bot_id列已存在，无需添加")

        # 提交更改
        conn.commit()

        # 关闭连接
        conn.close()
        return True

    except Exception as e:
        print(f"修复数据库时出错: {str(e)}")
        return False

if __name__ == '__main__':
    if fix_database():
        print("数据库结构修复成功")
    else:
        print("数据库结构修复失败") 