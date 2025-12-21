"""
诊断资金曲线数据问题
"""
import sys
sys.path.insert(0, '.')

from ai_db_manager import get_ai_db_manager

def diagnose():
    db = get_ai_db_manager()
    
    # 获取所有 AI 的统计
    all_stats = db.get_all_stats()
    print("=" * 60)
    print("AI 统计数据")
    print("=" * 60)
    for stat in all_stats:
        print(f"{stat.agent_name}: total_pnl={stat.total_pnl:.2f}, trades={stat.total_trades}, win_rate={stat.win_rate:.2%}")
    
    # 检查每个 AI 的已平仓交易
    print("\n" + "=" * 60)
    print("已平仓交易详情")
    print("=" * 60)
    
    for stat in all_stats:
        agent = stat.agent_name
        positions = db.get_closed_positions(agent, limit=20)
        
        if positions:
            print(f"\n{agent} 的已平仓交易 ({len(positions)} 笔):")
            total_pnl = 0
            for pos in positions:
                pnl = pos.get('pnl', 0) or 0
                total_pnl += pnl
                symbol = pos.get('symbol', '?')
                side = pos.get('side', '?')
                qty = pos.get('qty', 0)
                entry = pos.get('entry_price', 0)
                exit_p = pos.get('exit_price', 0)
                leverage = pos.get('leverage', 1)
                
                # 重新计算 pnl 验证
                if entry > 0:
                    price_change_pct = (exit_p - entry) / entry
                    if side == 'long':
                        calc_pnl = price_change_pct * qty * leverage
                    else:
                        calc_pnl = -price_change_pct * qty * leverage
                else:
                    calc_pnl = 0
                
                match = "✓" if abs(pnl - calc_pnl) < 0.01 else f"✗ (应为 {calc_pnl:.2f})"
                
                print(f"  {symbol} {side} | qty=${qty:.0f} | entry={entry:.2f} | exit={exit_p:.2f} | lev={leverage}x | pnl={pnl:.2f} {match}")
            
            print(f"  累计 PnL: {total_pnl:.2f}")
        else:
            print(f"\n{agent}: 无已平仓交易")

if __name__ == "__main__":
    diagnose()
