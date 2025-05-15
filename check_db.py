import sqlite3

# 连接到数据库
conn = sqlite3.connect('trading.db')
cursor = conn.cursor()

# 获取表结构
cursor.execute("PRAGMA table_info(trade_history)")
columns = cursor.fetchall()

print("trade_history 表的结构：")
for col in columns:
    print(f"列名: {col[1]}, 类型: {col[2]}, 可空: {col[3]}")

# 获取表中的记录数
cursor.execute("SELECT COUNT(*) FROM trade_history")
count = cursor.fetchone()[0]
print(f"\n表中的记录数: {count}")

# 获取一些示例数据
cursor.execute("SELECT * FROM trade_history LIMIT 5")
rows = cursor.fetchall()
print("\n示例数据:")
for row in rows:
    print(row)

# 关闭连接
conn.close() 