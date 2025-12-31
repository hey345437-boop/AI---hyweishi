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
重置模拟账户到初始状态

只清除：
- paper_positions（主仓持仓）
- hedge_positions（对冲仓位）
- paper_balance（重置为初始余额）

保留：
- bot_config（机器人配置）
- signal_events（信号历史）
- paper_fills（成交记录）
- 其他所有数据
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.db_bridge import (
    get_paper_balance, get_paper_positions, get_hedge_positions,
    _get_connection
)
import time

def reset_paper_account(initial_balance: float = 200.0):
    """重置模拟账户到初始状态"""
    
    print("=" * 60)
    print("🔄 重置模拟账户")
    print("=" * 60)
    
    # 1. 显示当前状态
    print("\n 当前状态:")
    balance = get_paper_balance()
    positions = get_paper_positions()
    hedge_positions = get_hedge_positions()
    
    print(f"   余额: ${balance.get('equity', 0):.2f}")
    print(f"   主仓数量: {len(positions) if positions else 0}")
    print(f"   对冲仓数量: {len(hedge_positions) if hedge_positions else 0}")
    
    # 2. 确认操作
    print(f"\n⚠️ 即将执行以下操作:")
    print(f"   - 清除所有主仓持仓")
    print(f"   - 清除所有对冲仓位")
    print(f"   - 重置余额为 ${initial_balance:.2f}")
    print(f"   - 保留其他所有数据（配置、信号历史、成交记录等）")
    
    confirm = input("\n确认执行? (输入 'yes' 确认): ")
    if confirm.lower() != 'yes':
        print(" 操作已取消")
        return False
    
    # 3. 执行重置
    conn, db_kind = _get_connection()
    try:
        cursor = conn.cursor()
        current_ts = int(time.time())
        
        # 清除主仓持仓
        if db_kind == "postgres":
            cursor.execute("DELETE FROM paper_positions")
        else:
            cursor.execute("DELETE FROM paper_positions")
        deleted_positions = cursor.rowcount
        print(f"    已清除 {deleted_positions} 个主仓持仓")
        
        # 清除对冲仓位
        if db_kind == "postgres":
            cursor.execute("DELETE FROM hedge_positions")
        else:
            cursor.execute("DELETE FROM hedge_positions")
        deleted_hedges = cursor.rowcount
        print(f"    已清除 {deleted_hedges} 个对冲仓位")
        
        # 重置余额
        if db_kind == "postgres":
            cursor.execute('''
                UPDATE paper_balance 
                SET wallet_balance = %s, unrealized_pnl = 0, used_margin = 0,
                    equity = %s, available = %s, updated_at = %s
                WHERE id = 1
            ''', (initial_balance, initial_balance, initial_balance, current_ts))
        else:
            cursor.execute('''
                UPDATE paper_balance 
                SET wallet_balance = ?, unrealized_pnl = 0, used_margin = 0,
                    equity = ?, available = ?, updated_at = ?
                WHERE id = 1
            ''', (initial_balance, initial_balance, initial_balance, current_ts))
        print(f"    已重置余额为 ${initial_balance:.2f}")
        
        conn.commit()
        
    finally:
        conn.close()
    
    # 4. 验证结果
    print("\n 重置后状态:")
    balance = get_paper_balance()
    positions = get_paper_positions()
    hedge_positions = get_hedge_positions()
    
    print(f"   钱包余额: ${balance.get('wallet_balance', 0):.2f}")
    print(f"   权益: ${balance.get('equity', 0):.2f}")
    print(f"   可用保证金: ${balance.get('available', 0):.2f}")
    print(f"   已用保证金: ${balance.get('used_margin', 0):.2f}")
    print(f"   主仓数量: {len(positions) if positions else 0}")
    print(f"   对冲仓数量: {len(hedge_positions) if hedge_positions else 0}")
    
    print("\n" + "=" * 60)
    print(" 模拟账户已重置完成！")
    print("=" * 60)
    
    return True


if __name__ == "__main__":
    # 默认初始余额 200u，可以通过命令行参数修改
    initial_balance = 200.0
    if len(sys.argv) > 1:
        try:
            initial_balance = float(sys.argv[1])
        except ValueError:
            print(f"无效的初始余额参数: {sys.argv[1]}")
            sys.exit(1)
    
    reset_paper_account(initial_balance)
