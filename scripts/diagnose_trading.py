#!/usr/bin/env python3
"""诊断交易引擎问题"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db_bridge import (
    get_bot_config, get_control_flags, get_trading_params,
    get_paper_positions, get_hedge_positions, get_paper_balance,
    load_all_signal_cache
)

def main():
    print("=" * 60)
    print("交易引擎诊断")
    print("=" * 60)
    
    # 1. 检查机器人配置
    print("\n[1] 机器人配置:")
    bot_config = get_bot_config()
    print(f"  run_mode: {bot_config.get('run_mode')}")
    print(f"  enable_trading: {bot_config.get('enable_trading')}")
    print(f"  symbols: {bot_config.get('symbols')}")
    
    # 2. 检查控制标志
    print("\n[2] 控制标志:")
    control = get_control_flags()
    print(f"  pause_trading: {control.get('pause_trading')}")
    print(f"  allow_live: {control.get('allow_live')}")
    
    # 3. 检查交易参数
    print("\n[3] 交易参数:")
    params = get_trading_params()
    print(f"  leverage: {params.get('leverage')}")
    print(f"  main_position_pct: {params.get('main_position_pct')}")
    print(f"  sub_position_pct: {params.get('sub_position_pct')}")
    
    # 4. 检查持仓
    print("\n[4] 持仓状态:")
    positions = get_paper_positions()
    print(f"  主仓数量: {len(positions)}")
    for k, v in positions.items():
        print(f"    {k}: qty={v.get('qty')}, entry={v.get('entry_price')}")
    
    hedge = get_hedge_positions()
    print(f"  对冲仓数量: {len(hedge)}")
    for h in hedge:
        print(f"    {h.get('symbol')}: qty={h.get('qty')}, entry={h.get('entry_price')}")
    
    # 5. 检查余额
    print("\n[5] 账户余额:")
    balance = get_paper_balance()
    print(f"  equity: ${balance.get('equity', 0):.2f}")
    print(f"  available: ${balance.get('available', 0):.2f}")
    print(f"  used_margin: ${balance.get('used_margin', 0):.2f}")
    
    # 6. 检查信号缓存
    print("\n[6] 信号缓存:")
    cache = load_all_signal_cache()
    print(f"  缓存条数: {len(cache)}")
    
    # 7. 诊断结论
    print("\n" + "=" * 60)
    print("诊断结论:")
    print("=" * 60)
    
    issues = []
    
    if bot_config.get('enable_trading') != 1:
        issues.append("❌ enable_trading != 1，交易未启用")
    else:
        print("✅ enable_trading = 1，交易已启用")
    
    if control.get('pause_trading') != 0:
        issues.append("❌ pause_trading != 0，交易已暂停")
    else:
        print("✅ pause_trading = 0，交易未暂停")
    
    run_mode = bot_config.get('run_mode', '')
    if run_mode not in ('live', 'paper', 'sim', 'paper_on_real'):
        issues.append(f"❌ run_mode = '{run_mode}'，未知模式")
    else:
        print(f"✅ run_mode = '{run_mode}'，模式正确")
    
    if run_mode == 'live' and control.get('allow_live') != 1:
        issues.append("❌ live模式但 allow_live != 1")
    
    if balance.get('equity', 0) <= 0:
        issues.append("❌ equity <= 0，账户无资金")
    else:
        print(f"✅ equity = ${balance.get('equity', 0):.2f}，账户有资金")
    
    if issues:
        print("\n发现问题:")
        for issue in issues:
            print(f"  {issue}")
    else:
        print("\n✅ 所有检查通过，交易应该能正常执行")
        print("\n如果仍然无法下单，可能的原因:")
        print("  1. is_first_scan_after_warmup = True（首次扫描跳过）")
        print("  2. 信号去重（同一根K线的信号已处理）")
        print("  3. 预风控拦截（can_open_new = False）")
        print("  4. 其他代码逻辑问题")

if __name__ == "__main__":
    main()
