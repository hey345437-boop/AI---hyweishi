"""检查决策记录"""
import sys
sys.path.insert(0, '.')

import sqlite3

conn = sqlite3.connect('arena.db')
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# 获取最新 20 条决策
cursor.execute("""
    SELECT agent_name, symbol, signal, confidence, created_at, reasoning
    FROM ai_decisions 
    ORDER BY id DESC 
    LIMIT 20
""")

rows = cursor.fetchall()
print(f"最新 {len(rows)} 条决策:")
print("-" * 80)

for row in rows:
    reasoning = (row['reasoning'] or '')[:50]
    print(f"{row['agent_name']:12} | {row['symbol']:20} | {row['signal']:12} | {row['confidence']:5.0f}% | {row['created_at']}")
    if reasoning:
        print(f"             | {reasoning}...")
    print()

conn.close()
