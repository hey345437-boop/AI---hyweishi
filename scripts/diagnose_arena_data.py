#!/usr/bin/env python3
"""
诊断 AI 竞技场数据
"""

import sqlite3
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ARENA_DB_PATH = "arena.db"


def diagnose():
    conn = sqlite3.connect(ARENA_DB_PATH)
    cursor = conn.cursor()
    
    print("=" * 60)
    print("AI 竞技场数据诊断")
    print("=" * 60)
    
    print("\n=== AI 持仓 ===")
    cursor.execute("""
        SELECT agent_name, symbol, side, qty, entry_price, leverage 
        FROM ai_positions WHERE status = 'open'
    """)
    positions = cursor.fetchall()
    for row in positions:
        print(f"  {row[0]}: {row[1]} {row[2]} qty={row[3]} entry={row[4]} lev={row[5]}")
    print(f"  共 {len(positions)} 个持仓")
    
    print("\n=== AI 统计 ===")
    cursor.execute("SELECT agent_name, total_pnl, win_rate, total_trades FROM ai_stats")
    for row in cursor.fetchall():
        print(f"  {row[0]}: PnL={row[1]:.4f}, WinRate={row[2]:.2f}, Trades={row[3]}")
    
    print("\n=== 按 AI 分组的持仓数量 ===")
    cursor.execute("""
        SELECT agent_name, COUNT(*) as cnt 
        FROM ai_positions WHERE status = 'open'
        GROUP BY agent_name
    """)
    for row in cursor.fetchall():
        print(f"  {row[0]}: {row[1]} 个持仓")
    
    conn.close()
    
    # 测试 get_arena_real_data
    print("\n=== get_arena_real_data 输出 ===")
    try:
        from ui_arena import get_arena_real_data
        data = get_arena_real_data()
        for name, d in data.items():
            print(f"  {name}:")
            print(f"    ROI: {d.get('roi', 0):.4f}%")
            print(f"    total_pnl_usd: {d.get('total_pnl_usd', 0):.4f}")
            print(f"    unrealized_pnl: {d.get('unrealized_pnl', 0):.4f}")
    except Exception as e:
        print(f"  错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    diagnose()
