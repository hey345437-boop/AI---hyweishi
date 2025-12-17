#!/usr/bin/env python3
"""检查数据库中的交易参数和持仓数据"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db_bridge import get_trading_params, get_paper_balance, get_paper_positions, get_hedge_positions

def main():
    print("=" * 60)
    print("📊 交易参数检查")
    print("=" * 60)
    
    # 1. 交易参数
    params = get_trading_params()
    print(f"\n🔧 交易参数:")
    print(f"   杠杆: {params.get('leverage')}x")
    print(f"   主仓比例: {params.get('main_position_pct') * 100:.2f}%")
    print(f"   次仓比例: {params.get('sub_position_pct') * 100:.2f}%")
    print(f"   硬止盈: {params.get('hard_tp_pct') * 100:.2f}%")
    print(f"   对冲止盈: {params.get('hedge_tp_pct') * 100:.3f}%")
    
    # 2. 账户余额
    balance = get_paper_balance()
    print(f"\n💰 模拟账户:")
    print(f"   钱包余额: ${balance.get('wallet_balance', 0):.2f}")
    print(f"   未实现盈亏: ${balance.get('unrealized_pnl', 0):.2f}")
    print(f"   权益: ${balance.get('equity', 0):.2f}")
    print(f"   已用保证金: ${balance.get('used_margin', 0):.2f}")
    print(f"   可用保证金: ${balance.get('available', 0):.2f}")
    
    equity = balance.get('equity', 0)
    leverage = params.get('leverage', 20)
    main_pct = params.get('main_position_pct', 0.03)
    
    # 3. 预期下单金额
    print(f"\n📐 预期下单金额 (基于当前参数):")
    expected_margin = equity * main_pct
    expected_notional = expected_margin * leverage
    print(f"   主仓保证金 = {equity:.2f} × {main_pct*100:.2f}% = ${expected_margin:.2f}")
    print(f"   主仓名义价值 = {expected_margin:.2f} × {leverage} = ${expected_notional:.2f}")
    
    # 4. 持仓数据
    positions = get_paper_positions()
    print(f"\n📋 主仓持仓 ({len(positions) if positions else 0} 个):")
    
    total_notional = 0
    total_margin = 0
    
    if positions:
        for key, pos in positions.items():
            qty = float(pos.get('qty', 0) or 0)
            entry_price = float(pos.get('entry_price', 0) or 0)
            notional = qty * entry_price
            margin = notional / leverage
            total_notional += notional
            total_margin += margin
            
            print(f"   {key}:")
            print(f"      数量: {qty:.8f}")
            print(f"      入场价: ${entry_price:.4f}")
            print(f"      名义价值: ${notional:.2f}")
            print(f"      保证金: ${margin:.2f}")
            
            # 反推下单时的参数
            if equity > 0:
                implied_pct = margin / equity * 100
                print(f"      反推比例: {implied_pct:.2f}% (预期 {main_pct*100:.2f}%)")
    
    # 5. 对冲仓位
    hedge_positions = get_hedge_positions()
    print(f"\n🛡️ 对冲仓位 ({len(hedge_positions) if hedge_positions else 0} 个):")
    
    if hedge_positions:
        for pos in hedge_positions:
            qty = float(pos.get('qty', 0) or 0)
            entry_price = float(pos.get('entry_price', 0) or 0)
            notional = qty * entry_price
            margin = notional / leverage
            total_notional += notional
            total_margin += margin
            
            print(f"   {pos.get('symbol', '?')} {pos.get('pos_side', '?')}:")
            print(f"      数量: {qty:.8f}")
            print(f"      入场价: ${entry_price:.4f}")
            print(f"      名义价值: ${notional:.2f}")
            print(f"      保证金: ${margin:.2f}")
    
    # 6. 汇总
    print(f"\n📊 汇总:")
    print(f"   总名义价值: ${total_notional:.2f}")
    print(f"   总保证金: ${total_margin:.2f}")
    print(f"   保证金占权益: {total_margin/equity*100:.2f}%" if equity > 0 else "   保证金占权益: N/A")
    
    print("\n" + "=" * 60)

if __name__ == "__main__":
    main()
