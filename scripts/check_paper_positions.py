#!/usr/bin/env python3
"""诊断脚本：检查 paper_positions 表中的数据"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db_bridge import get_paper_positions, get_paper_balance, get_hedge_positions

def main():
    print("=" * 60)
    print("📊 Paper Trading 数据诊断")
    print("=" * 60)
    
    # 检查余额
    print("\n💰 Paper Balance:")
    balance = get_paper_balance()
    if balance:
        for key, value in balance.items():
            print(f"   {key}: {value}")
    else:
        print("   ❌ 无余额数据")
    
    # 检查主仓位
    print("\n📈 Paper Positions (主仓):")
    positions = get_paper_positions()
    if positions:
        for pos_key, pos in positions.items():
            print(f"\n   [{pos_key}]")
            for key, value in pos.items():
                print(f"      {key}: {value}")
    else:
        print("   ❌ 无主仓位")
    
    # 检查对冲仓位
    print("\n🔄 Hedge Positions (对冲仓):")
    hedge_positions = get_hedge_positions()
    if hedge_positions:
        for i, pos in enumerate(hedge_positions):
            print(f"\n   [对冲仓 {i+1}]")
            for key, value in pos.items():
                print(f"      {key}: {value}")
    else:
        print("   ❌ 无对冲仓位")
    
    print("\n" + "=" * 60)

if __name__ == "__main__":
    main()
