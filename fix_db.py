import sqlite3
import time

# 连接到数据库
db_path = "quant_system.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# 更新交易对为正确格式
new_symbols = "BTC/USDT:USDT,ETH/USDT:USDT"
update_time = int(time.time())

cursor.execute("UPDATE bot_config SET symbols = ?, updated_at = ? WHERE id = 1;", (new_symbols, update_time))
conn.commit()

print("已更新交易对配置为正确格式:")
print(f"symbols: {new_symbols}")

# 关闭连接
conn.close()