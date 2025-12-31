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
清理重复的 AI 持仓

保留每个 AI 每个币种每个方向只有一个持仓
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ai_db_manager import get_ai_db_manager

def main():
    print("=" * 60)
    print("清理重复 AI 持仓")
    print("=" * 60)
    
    db = get_ai_db_manager()
    
    # 获取所有 AI
    agents = ['deepseek', 'qwen', 'perplexity', 'spark_lite', 'hunyuan']
    
    total_closed = 0
    
    for agent in agents:
        positions = db.get_open_positions(agent)
        if not positions:
            continue
        
        # 按 (symbol, side) 分组
        groups = {}
        for pos in positions:
            key = (pos['symbol'], pos['side'])
            if key not in groups:
                groups[key] = []
            groups[key].append(pos)
        
        # 对于每个组，只保留最新的一个（ID 最大的）
        for key, pos_list in groups.items():
            if len(pos_list) > 1:
                # 按 ID 排序，保留最大的
                pos_list.sort(key=lambda x: x['id'], reverse=True)
                keep = pos_list[0]
                to_close = pos_list[1:]
                
                print(f"\n{agent} | {key[0]} | {key[1]}:")
                print(f"  保留: ID={keep['id']}, 入场价={keep['entry_price']}")
                
                for pos in to_close:
                    # 以入场价平仓（不计算盈亏）
                    db.close_position(pos['id'], pos['entry_price'])
                    print(f"  关闭: ID={pos['id']}, 入场价={pos['entry_price']}")
                    total_closed += 1
    
    print(f"\n共关闭 {total_closed} 个重复持仓")
    print("=" * 60)

if __name__ == "__main__":
    main()
