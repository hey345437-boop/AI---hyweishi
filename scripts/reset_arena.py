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
重置 AI 竞技场数据

清空所有：
- AI 决策记录
- AI 持仓（开仓和已平仓）
- AI 统计数据（重置为初始状态）

保留：
- AI API 配置（不需要重新输入 API Key）
"""
import sys
sys.path.insert(0, '.')

import sqlite3
from ai_db_manager import ARENA_DB_PATH

def reset_arena():
    print("=" * 60)
    print("🔄 重置 AI 竞技场数据")
    print("=" * 60)
    
    conn = sqlite3.connect(ARENA_DB_PATH)
    cursor = conn.cursor()
    
    # 1. 清空决策记录
    cursor.execute("DELETE FROM ai_decisions")
    decisions_deleted = cursor.rowcount
    print(f"✓ 清空决策记录: {decisions_deleted} 条")
    
    # 2. 清空持仓记录
    cursor.execute("DELETE FROM ai_positions")
    positions_deleted = cursor.rowcount
    print(f"✓ 清空持仓记录: {positions_deleted} 条")
    
    # 3. 重置统计数据（保留 agent_name，重置其他字段）
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
            avg_pnl = 0.0,
            last_signal = '',
            last_updated = 0
    """)
    stats_reset = cursor.rowcount
    print(f"✓ 重置统计数据: {stats_reset} 个 AI")
    
    conn.commit()
    conn.close()
    
    print("\n" + "=" * 60)
    print(" AI 竞技场已重置，可以重新开始比赛！")
    print("=" * 60)
    print("\n提示：")
    print("- API Key 配置已保留，无需重新输入")
    print("- 所有 AI 初始资金重置为 $10,000")
    print("- 刷新页面后生效")

if __name__ == "__main__":
    confirm = input("确认要清空所有 AI 竞技场数据吗？(y/n): ")
    if confirm.lower() == 'y':
        reset_arena()
    else:
        print("已取消")
