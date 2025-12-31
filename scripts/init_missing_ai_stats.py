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
初始化缺失的 AI 统计记录

为新增的 AI（spark_lite, hunyuan）创建统计记录
"""

import sqlite3
import time
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ARENA_DB_PATH = "arena.db"


def init_missing_ai_stats():
    """初始化缺失的 AI 统计记录"""
    conn = sqlite3.connect(ARENA_DB_PATH)
    cursor = conn.cursor()
    
    print("=" * 50)
    print("初始化缺失的 AI 统计记录")
    print("=" * 50)
    
    # 所有支持的 AI
    all_agents = ['deepseek', 'qwen', 'perplexity', 'gpt', 'claude', 'spark_lite', 'hunyuan']
    
    # 查看当前统计记录
    cursor.execute("SELECT agent_name FROM ai_stats")
    existing = set(row[0] for row in cursor.fetchall())
    print(f"\n当前已有统计记录: {existing}")
    
    # 添加缺失的记录
    missing = set(all_agents) - existing
    if missing:
        print(f"缺失的 AI: {missing}")
        for agent in missing:
            cursor.execute("""
                INSERT OR IGNORE INTO ai_stats (agent_name, last_updated)
                VALUES (?, ?)
            """, (agent, int(time.time() * 1000)))
            print(f"   已添加: {agent}")
        conn.commit()
    else:
        print("所有 AI 统计记录已存在")
    
    # 验证
    cursor.execute("SELECT agent_name, total_pnl, win_rate FROM ai_stats")
    rows = cursor.fetchall()
    print(f"\n当前所有统计记录 ({len(rows)} 条):")
    for row in rows:
        print(f"  {row[0]}: PnL={row[1]}, WinRate={row[2]}")
    
    conn.close()
    print("\n完成！")


if __name__ == "__main__":
    init_missing_ai_stats()
