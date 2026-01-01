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
#   Copyright (c) 2024-2025 HyWeiShi. All Rights Reserved.
#   License: AGPL-3.0
#
# ============================================================================
"""
修复数据库中错误的 PnL 数据

问题：部分交易的 pnl 计算错误，导致资金曲线显示异常
解决：重新计算所有已平仓交易的 pnl
"""
import sys
sys.path.insert(0, '.')

import sqlite3
from ai.ai_db_manager import ARENA_DB_PATH

def fix_pnl():
    conn = sqlite3.connect(ARENA_DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # 获取所有已平仓交易
    cursor.execute("""
        SELECT id, agent_name, symbol, side, qty, entry_price, exit_price, leverage, pnl
        FROM ai_positions
        WHERE status = 'closed'
    """)
    
    rows = cursor.fetchall()
    print(f"找到 {len(rows)} 笔已平仓交易")
    
    fixed_count = 0
    for row in rows:
        pos_id = row['id']
        entry = row['entry_price'] or 0
        exit_p = row['exit_price'] or 0
        qty = row['qty'] or 0
        side = row['side']
        leverage = row['leverage'] or 1
        old_pnl = row['pnl'] or 0
        
        # 重新计算 pnl
        if entry > 0:
            price_change_pct = (exit_p - entry) / entry
            if side == 'long':
                new_pnl = price_change_pct * qty * leverage
            else:  # short
                new_pnl = -price_change_pct * qty * leverage
        else:
            new_pnl = 0
        
        # 检查是否需要修复
        if abs(old_pnl - new_pnl) > 0.01:
            print(f"修复 {row['agent_name']} {row['symbol']} {side}: {old_pnl:.2f} -> {new_pnl:.2f}")
            cursor.execute("""
                UPDATE ai_positions SET pnl = ? WHERE id = ?
            """, (new_pnl, pos_id))
            fixed_count += 1
    
    conn.commit()
    print(f"\n修复了 {fixed_count} 笔交易的 PnL")
    
    # 重新计算每个 AI 的统计数据
    print("\n重新计算 AI 统计数据...")
    
    cursor.execute("SELECT DISTINCT agent_name FROM ai_positions WHERE status = 'closed'")
    agents = [row['agent_name'] for row in cursor.fetchall()]
    
    for agent in agents:
        # 获取该 AI 的所有已平仓交易
        cursor.execute("""
            SELECT pnl FROM ai_positions 
            WHERE agent_name = ? AND status = 'closed'
            ORDER BY exit_time ASC
        """, (agent,))
        
        trades = cursor.fetchall()
        total_trades = len(trades)
        win_count = sum(1 for t in trades if (t['pnl'] or 0) > 0)
        loss_count = sum(1 for t in trades if (t['pnl'] or 0) < 0)
        total_pnl = sum(t['pnl'] or 0 for t in trades)
        win_rate = win_count / total_trades if total_trades > 0 else 0
        avg_pnl = total_pnl / total_trades if total_trades > 0 else 0
        best_trade = max((t['pnl'] or 0) for t in trades) if trades else 0
        worst_trade = min((t['pnl'] or 0) for t in trades) if trades else 0
        
        # 计算连胜/连败
        current_streak = 0
        for t in reversed(trades):
            pnl = t['pnl'] or 0
            if pnl > 0:
                if current_streak >= 0:
                    current_streak += 1
                else:
                    break
            elif pnl < 0:
                if current_streak <= 0:
                    current_streak -= 1
                else:
                    break
        
        # 更新统计
        cursor.execute("""
            UPDATE ai_stats SET
                total_trades = ?, win_count = ?, loss_count = ?,
                win_rate = ?, total_pnl = ?, current_streak = ?,
                best_trade = ?, worst_trade = ?, avg_pnl = ?
            WHERE agent_name = ?
        """, (
            total_trades, win_count, loss_count, win_rate,
            total_pnl, current_streak, best_trade, worst_trade,
            avg_pnl, agent
        ))
        
        print(f"  {agent}: trades={total_trades}, pnl={total_pnl:.2f}, win_rate={win_rate:.1%}")
    
    conn.commit()
    conn.close()
    print("\n 修复完成！")

if __name__ == "__main__":
    fix_pnl()
