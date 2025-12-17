import sqlite3

# 连接数据库
conn = sqlite3.connect('quant_system.db')
cursor = conn.cursor()

# 获取所有表名
cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables = cursor.fetchall()
print("数据库中的所有表:")
for table in tables:
    print(f"- {table[0]}")

# 显示每个表的结构
print("\n各表的结构:")
for table in tables:
    table_name = table[0]
    print(f"\n表 {table_name} 的列:")
    cursor.execute(f"PRAGMA table_info({table_name});")
    columns = cursor.fetchall()
    for column in columns:
        print(f"  - {column[1]} ({column[2]})")

# 关闭数据库连接
conn.close()
