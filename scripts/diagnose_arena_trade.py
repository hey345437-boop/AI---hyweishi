#!/usr/bin/env python3
"""
诊断 AI 竞技场交易执行问题

检查：
1. AI 决策是否正确解析
2. 交易信号是否被正确识别
3. 模拟交易是否成功写入数据库
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ai_db_manager import get_ai_db_manager
from ai_trade_bridge import get_ai_trade_bridge, AITradeSignal, AITradeMode

def main():
    print("=" * 60)
    print("AI 竞技场交易诊断")
    print("=" * 60)
    
    # 1. 检查数据库中的最近决策
    print("\n[1] 最近的 AI 决策:")
    db = get_ai_db_manager()
    decisions = db.get_latest_decisions(limit=10)
    
    for d in decisions:
        print(f"  - {d.agent_name} | {d.symbol} | {d.signal} | 置信度: {d.confidence}%")
    
    # 2. 检查当前持仓
    print("\n[2] 当前 AI 持仓:")
    agents = ['deepseek', 'qwen', 'perplexity', 'spark_lite', 'hunyuan']
    total_positions = 0
    
    for agent in agents:
        positions = db.get_open_positions(agent)
        if positions:
            for pos in positions:
                print(f"  - {agent} | {pos['symbol']} | {pos['side']} | 入场: {pos['entry_price']}")
                total_positions += 1
    
    if total_positions == 0:
        print("  (无持仓)")
    
    # 3. 测试模拟交易
    print("\n[3] 测试模拟交易执行:")
    bridge = get_ai_trade_bridge()
    
    test_signal = AITradeSignal(
        agent_name="test_agent",
        symbol="BTC/USDT:USDT",
        signal="open_long",
        confidence=85,
        entry_price=100000,
        position_size_usd=100,
        leverage=5,
        reasoning="诊断测试"
    )
    
    print(f"  测试信号: {test_signal.agent_name} {test_signal.signal} {test_signal.symbol}")
    print(f"  仓位: {test_signal.position_size_usd} USD, 杠杆: {test_signal.leverage}x")
    
    # 执行模拟交易
    result = bridge.execute_signal(test_signal, ai_takeover=False)
    
    print(f"\n  执行结果:")
    print(f"    成功: {result.success}")
    print(f"    模式: {result.mode}")
    print(f"    消息: {result.message}")
    
    # 4. 检查测试持仓是否创建
    print("\n[4] 检查测试持仓:")
    test_positions = db.get_open_positions("test_agent")
    if test_positions:
        for pos in test_positions:
            print(f"  ✅ 持仓已创建: {pos['symbol']} | {pos['side']} | 入场: {pos['entry_price']}")
            # 清理测试持仓
            db.close_position(pos['id'], pos['entry_price'])
            print(f"  🧹 已清理测试持仓")
    else:
        print("  ❌ 测试持仓未创建！")
    
    # 5. 检查交易模式
    print("\n[5] 当前交易模式:")
    mode = bridge.get_current_trade_mode(ai_takeover=False)
    print(f"  模式: {mode}")
    print(f"  (SIMULATION = 模拟交易, LIVE = 实盘交易)")
    
    print("\n" + "=" * 60)
    print("诊断完成")
    print("=" * 60)

if __name__ == "__main__":
    main()
