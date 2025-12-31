# -*- coding: utf-8 -*-
# ============================================================================
#
#    _   _  __   __ __        __  _____ ___  ____   _   _  ___ 
#   | | | | \ \ / / \ \      / / | ____||_ _|/ ___| | | | ||_ _|
#   | |_| |  \ V /   \ \ /\ / /  |  _|   | | \___ \ | |_| | | | 
#   |  _  |   | |     \ V  V /   | |___  | |  ___) ||  _  | | | 
#   |_| |_|   |_|      \_/\_/    |_____||___||____/ |_| |_||___|
#
#                         何 以 为 势
#                  Quantitative Trading System
#
#   Copyright (c) 2024-2025 HeWeiShi. All Rights Reserved.
#   License: Apache License 2.0
#
# ============================================================================
"""
重置 AI 统计数据

由于之前的盈亏计算公式错误，需要重置统计数据
"""

import sqlite3
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ARENA_DB_PATH = "arena.db"


def reset_ai_stats():
    """重置所有 AI 的统计数据"""
    conn = sqlite3.connect(ARENA_DB_PATH)
    cursor = conn.cursor()
    
    print("=" * 50)
    print("重置 AI 统计数据")
    print("=" * 50)
    
    # 查看当前统计
    cursor.execute("SELECT * FROM ai_stats")
    rows = cursor.fetchall()
    print(f"\n当前统计数据 ({len(rows)} 条):")
    for row in rows:
        print(f"  {row}")
    
    # 重置统计数据
    cursor.execute("""
        UPDATE ai_stats SET
            total_trades = 0,
            win_count = 0,
            loss_count = 0,
            win_rate = 0.0,
            total_pnl = 0.0,
            current_streak = 0,
            best_trade = 0.0,
            worst_trade = 0.0,
            avg_pnl = 0.0
    """)
    conn.commit()
    print(f"\n 已重置 {cursor.rowcount} 条统计记录")
    
    # 关闭所有持仓（可选）
    cursor.execute("SELECT COUNT(*) FROM ai_positions WHERE status = 'open'")
    open_count = cursor.fetchone()[0]
    
    if open_count > 0:
        print(f"\n发现 {open_count} 个未平仓持仓")
        response = input("是否关闭所有持仓？(y/n): ")
        if response.lower() == 'y':
            cursor.execute("DELETE FROM ai_positions WHERE status = 'open'")
            conn.commit()
            print(f" 已删除 {cursor.rowcount} 个持仓")
    
    # 查看重置后的统计
    cursor.execute("SELECT * FROM ai_stats")
    rows = cursor.fetchall()
    print(f"\n重置后统计数据:")
    for row in rows:
        print(f"  {row}")
    
    conn.close()
    print("\n完成！")


if __name__ == "__main__":
    reset_ai_stats()
