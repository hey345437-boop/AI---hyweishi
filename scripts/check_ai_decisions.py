#!/usr/bin/env python3
"""检查 AI 决策记录"""
import sqlite3

conn = sqlite3.connect('arena.db')
c = conn.cursor()

# 统计各 agent 的成功/失败记录
c.execute("""
    SELECT 
        agent_name,
        COUNT(*) as total,
        SUM(CASE WHEN reasoning LIKE '%批量分析未返回%' THEN 1 ELSE 0 END) as failed
    FROM ai_decisions 
    GROUP BY agent_name
""")
rows = c.fetchall()

print("Agent 决策统计:")
print("-" * 50)
for r in rows:
    success = r[1] - r[2]
    print(f"  {r[0]:12}: 总数={r[1]:3}, 成功={success:3}, 匹配失败={r[2]:3}")

conn.close()
