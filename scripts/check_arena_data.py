"""检查竞技场数据"""
import sys
sys.path.insert(0, '.')

from ai_db_manager import get_ai_db_manager

db = get_ai_db_manager()

# 检查决策
decisions = db.get_latest_decisions(limit=20)
print(f"决策数量: {len(decisions)}")
for d in decisions[:10]:
    print(f"  {d.agent_name}: {d.signal} ({d.confidence:.0f}%) @ {d.created_at}")

print()

# 检查持仓
positions = db.get_open_positions()
print(f"持仓数量: {len(positions)}")
for p in positions:
    print(f"  {p['agent_name']}: {p['symbol']} {p['side']} ${p['qty']}")
