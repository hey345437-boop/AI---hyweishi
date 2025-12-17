import sqlite3
import json

# 连接到数据库
db_path = 'quant_system.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("执行简单数据清理...")

# 1. 清空simulation_history表
print("清空simulation_history表...")
cursor.execute("DELETE FROM simulation_history")

# 2. 清空equity_history表
print("清空equity_history表...")
cursor.execute("DELETE FROM equity_history")

# 3. 清空trade_logs表
print("清空trade_logs表...")
cursor.execute("DELETE FROM trade_logs")

# 4. 清空user_states表中的持仓
print("清空user_states表中的持仓...")
cursor.execute("UPDATE user_states SET open_positions = ?, hedge_positions = ? WHERE username = ?", 
              (json.dumps({}), json.dumps({}), "admin"))

# 提交更改
conn.commit()
print("清理完成!")

# 5. 检查结果
print("\n检查清理结果:")
tables = ['simulation_history', 'equity_history', 'trade_logs']
for table in tables:
    cursor.execute(f"SELECT COUNT(*) FROM {table}")
    count = cursor.fetchone()[0]
    print(f"{table}表记录数: {count}")

# 检查user_states表中的持仓
cursor.execute("SELECT open_positions, hedge_positions FROM user_states WHERE username = ?", ("admin",))
user_state = cursor.fetchone()
if user_state:
    open_positions = json.loads(user_state[0]) if user_state[0] else {}
    hedge_positions = json.loads(user_state[1]) if user_state[1] else {}
    print(f"user_states表中持仓数: 主持仓{len(open_positions)}, 对冲持仓{len(hedge_positions)}")

# 关闭连接
conn.close()