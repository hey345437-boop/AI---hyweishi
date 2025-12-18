#!/usr/bin/env python3
"""诊断信号执行失败的原因"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db_bridge import get_bot_config, get_control_flags, get_trading_params, get_paper_balance, get_paper_positions, get_hedge_positions

def main():
    print("=" * 70)
    print("🔍 信号执行失败诊断")
    print("=" * 70)
    
    # 1. 检查交易开关
    bot_config = get_bot_config()
    control = get_control_flags()
    
    enable_trading = bot_config.get('enable_trading', 0)
    pause_trading = control.get("pause_trading", 0)
    run_mode = bot_config.get('run_mode', 'sim')
    
    print(f"\n🔧 交易开关状态:")
    print(f"   enable_trading = {enable_trading} {'✅ 已启用' if enable_trading == 1 else '❌ 未启用'}")
    print(f"   pause_trading  = {pause_trading} {'❌ 已暂停' if pause_trading == 1 else '✅ 未暂停'}")
    print(f"   run_mode       = {run_mode}")
    
    trading_enabled = enable_trading == 1 and pause_trading != 1
    print(f"\n   📊 综合判断: trading_enabled = {trading_enabled} {'✅ 可以交易' if trading_enabled else '❌ 无法交易'}")
    
    if not trading_enabled:
        print(f"\n   ⚠️ 问题: 交易未启用!")
        if enable_trading != 1:
            print(f"      原因: enable_trading = {enable_trading} (需要 = 1)")
        if pause_trading == 1:
            print(f"      原因: pause_trading = {pause_trading} (需要 = 0)")
    
    # 2. 检查账户余额
    balance = get_paper_balance()
    equity = float(balance.get('equity', 0) or 0)
    available = float(balance.get('available', 0) or 0)
    
    print(f"\n💰 账户状态:")
    print(f"   权益 (equity)   = ${equity:.2f}")
    print(f"   可用 (available) = ${available:.2f}")
    
    if equity <= 0:
        print(f"\n   ⚠️ 问题: 权益为零或负数!")
    
    # 3. 检查持仓
    positions = get_paper_positions()
    hedge_positions = get_hedge_positions()
    
    print(f"\n📋 持仓状态:")
    print(f"   主仓数量: {len(positions) if positions else 0}")
    print(f"   对冲仓数量: {len(hedge_positions) if hedge_positions else 0}")
    
    if positions:
        for key, pos in positions.items():
            print(f"      {key}: {pos.get('pos_side')} qty={pos.get('qty')}")
    
    # 4. 检查风控参数
    params = get_trading_params()
    leverage = params.get('leverage', 20)
    main_pct = params.get('main_position_pct', 0.03)
    
    print(f"\n⚙️ 风控参数:")
    print(f"   杠杆: {leverage}x")
    print(f"   主仓比例: {main_pct * 100:.2f}%")
    
    # 5. 计算预期下单金额
    if equity > 0:
        expected_margin = equity * main_pct
        expected_notional = expected_margin * leverage
        print(f"\n📐 预期下单:")
        print(f"   保证金 = ${expected_margin:.2f}")
        print(f"   名义价值 = ${expected_notional:.2f}")
        
        if expected_notional < 5:
            print(f"\n   ⚠️ 问题: 名义价值太小 (< $5)，可能被交易所拒绝!")
    
    # 6. 检查 preflight 状态
    print(f"\n🔍 预检查状态:")
    print(f"   (需要运行引擎后查看日志中的 preflight_status)")
    
    print("\n" + "=" * 70)
    print("📝 建议:")
    print("   1. 确保 enable_trading = 1")
    print("   2. 确保 pause_trading = 0")
    print("   3. 确保账户有足够权益")
    print("   4. 查看引擎日志中的 [DEBUG] 信息")
    print("=" * 70)

if __name__ == "__main__":
    main()
