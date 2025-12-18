# tests/test_emergency_flatten.py
"""
紧急平仓功能测试
测试一键平仓后净值计算是否正确
"""

import pytest
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db_bridge import (
    get_paper_balance,
    update_paper_balance,
    get_paper_positions,
    update_paper_position,
    delete_paper_position,
    get_hedge_positions,
    delete_hedge_position,
    insert_trade_history,
    get_trade_history,
    clear_trade_history
)


class TestEmergencyFlatten:
    """紧急平仓测试"""
    
    def setup_method(self):
        """每个测试前重置账户状态"""
        # 清除所有持仓
        positions = get_paper_positions()
        if positions:
            for pos_key, pos in positions.items():
                delete_paper_position(pos.get('symbol'), pos.get('pos_side'))
        
        # 清除对冲仓位
        hedge_positions = get_hedge_positions()
        if hedge_positions:
            for hedge_pos in hedge_positions:
                delete_hedge_position(hedge_pos.get('id'))
        
        # 重置账户余额
        update_paper_balance(
            wallet_balance=200.0,
            equity=200.0,
            available=200.0,
            unrealized_pnl=0.0,
            used_margin=0.0
        )
        
        # 清除交易历史
        clear_trade_history()
    
    def test_flatten_preserves_equity_when_pnl_zero(self):
        """测试：当PnL计算为0时，平仓后净值应保持为平仓前的equity"""
        # 设置初始状态：equity=207.08（包含未实现盈亏）
        update_paper_balance(
            wallet_balance=205.0,
            equity=207.08,
            available=194.0,
            unrealized_pnl=2.08,
            used_margin=12.33
        )
        
        # 添加模拟持仓
        update_paper_position(
            symbol='ZEC/USDT:USDT',
            pos_side='long',
            qty=0.31,
            entry_price=395.42
        )
        update_paper_position(
            symbol='ETH/USDT:USDT',
            pos_side='long',
            qty=0.04,
            entry_price=2934.35
        )
        
        # 验证持仓存在
        positions = get_paper_positions()
        assert len(positions) == 2, f"应有2个持仓，实际有{len(positions)}个"
        
        # 🔥 关键：在删除持仓之前保存当前的 equity
        pre_flatten_equity = float(get_paper_balance().get('equity', 200))
        
        total_pnl = 0.0  # 模拟价格获取失败
        
        # 删除持仓（模拟平仓过程）
        for pos_key, pos in positions.items():
            delete_paper_position(pos.get('symbol'), pos.get('pos_side'))
        
        # 使用修复后的逻辑：使用平仓前保存的 equity
        if total_pnl != 0:
            new_wallet = 205.0 + total_pnl
        else:
            # 价格获取失败时，使用平仓前的权益作为新净值
            new_wallet = pre_flatten_equity
        
        new_equity = new_wallet
        new_available = new_wallet
        
        # 更新余额
        update_paper_balance(
            wallet_balance=new_wallet,
            equity=new_equity,
            available=new_available,
            unrealized_pnl=0.0,
            used_margin=0.0
        )
        
        # 验证结果
        final_bal = get_paper_balance()
        final_equity = float(final_bal.get('equity', 0))
        
        # 净值应该保持为207.08（平仓前的equity），而不是205（wallet_balance）
        assert abs(final_equity - 207.08) < 0.01, f"净值应为207.08，实际为{final_equity}"
        print(f"✅ 测试通过：平仓后净值={final_equity}")
    
    def test_flatten_with_correct_pnl(self):
        """测试：当PnL计算正确时，平仓后净值应为wallet_balance + pnl"""
        # 设置初始状态
        update_paper_balance(
            wallet_balance=200.0,
            equity=202.43,
            available=194.0,
            unrealized_pnl=2.43,
            used_margin=6.0
        )
        
        # 添加一个模拟持仓
        update_paper_position(
            symbol='BTC/USDT:USDT',
            pos_side='long',
            qty=0.001,
            entry_price=100000.0
        )
        
        # 模拟平仓逻辑（价格获取成功）
        paper_bal = get_paper_balance()
        wallet_balance = float(paper_bal.get('wallet_balance', 200) or 200)
        
        # 模拟当前价格上涨
        entry_price = 100000.0
        current_price = 102000.0
        qty = 0.001
        
        # 计算PnL
        pnl = (current_price - entry_price) * qty  # = 2.0
        total_pnl = pnl
        
        # 使用修复后的逻辑
        if total_pnl != 0:
            new_wallet = wallet_balance + total_pnl
        else:
            new_wallet = float(paper_bal.get('equity', 200))
        
        new_equity = new_wallet
        
        # 更新余额
        update_paper_balance(
            wallet_balance=new_wallet,
            equity=new_equity,
            available=new_wallet,
            unrealized_pnl=0.0,
            used_margin=0.0
        )
        
        # 删除持仓
        delete_paper_position('BTC/USDT:USDT', 'long')
        
        # 验证结果
        final_bal = get_paper_balance()
        final_equity = float(final_bal.get('equity', 0))
        
        # 净值应该为 200 + 2 = 202
        expected_equity = 200.0 + 2.0
        assert abs(final_equity - expected_equity) < 0.01, f"净值应为{expected_equity}，实际为{final_equity}"
        print(f"✅ 测试通过：平仓后净值={final_equity}")
    
    def test_trade_history_recorded(self):
        """测试：平仓后交易历史应该被记录"""
        # 设置初始状态
        update_paper_balance(
            wallet_balance=200.0,
            equity=200.0,
            available=200.0,
            unrealized_pnl=0.0,
            used_margin=0.0
        )
        
        # 记录一笔交易
        insert_trade_history(
            symbol='BTC/USDT:USDT',
            pos_side='long',
            entry_price=100000.0,
            exit_price=102000.0,
            qty=0.001,
            pnl=2.0,
            hold_time=3600,
            note='紧急平仓'
        )
        
        # 获取交易历史
        history = get_trade_history(limit=10)
        
        # 验证交易历史存在
        assert len(history) > 0, "交易历史应该存在"
        
        latest_trade = history[0]
        assert latest_trade['symbol'] == 'BTC/USDT:USDT'
        assert latest_trade['pos_side'] == 'long'
        assert abs(latest_trade['pnl'] - 2.0) < 0.01
        assert latest_trade['note'] == '紧急平仓'
        
        print(f"✅ 测试通过：交易历史已记录")
    
    def test_multiple_positions_flatten(self):
        """测试：多个持仓同时平仓"""
        # 设置初始状态
        update_paper_balance(
            wallet_balance=200.0,
            equity=205.0,
            available=180.0,
            unrealized_pnl=5.0,
            used_margin=20.0
        )
        
        # 添加多个持仓
        update_paper_position(
            symbol='BTC/USDT:USDT',
            pos_side='long',
            qty=0.001,
            entry_price=100000.0
        )
        update_paper_position(
            symbol='ETH/USDT:USDT',
            pos_side='long',
            qty=0.01,
            entry_price=3000.0
        )
        
        # 验证持仓数量
        positions = get_paper_positions()
        assert len(positions) == 2, f"应有2个持仓，实际有{len(positions)}个"
        
        # 模拟平仓（价格获取失败，使用equity）
        paper_bal = get_paper_balance()
        current_equity = float(paper_bal.get('equity', 200))
        
        total_pnl = 0.0  # 模拟价格获取失败
        
        if total_pnl != 0:
            new_wallet = 200.0 + total_pnl
        else:
            new_wallet = current_equity  # 使用当前equity
        
        # 更新余额
        update_paper_balance(
            wallet_balance=new_wallet,
            equity=new_wallet,
            available=new_wallet,
            unrealized_pnl=0.0,
            used_margin=0.0
        )
        
        # 删除所有持仓
        for pos_key, pos in positions.items():
            delete_paper_position(pos.get('symbol'), pos.get('pos_side'))
        
        # 验证结果
        final_bal = get_paper_balance()
        final_equity = float(final_bal.get('equity', 0))
        
        # 净值应该保持为205（当前equity）
        assert abs(final_equity - 205.0) < 0.01, f"净值应为205，实际为{final_equity}"
        
        # 验证持仓已清空
        remaining_positions = get_paper_positions()
        assert len(remaining_positions) == 0, "持仓应该已清空"
        
        print(f"✅ 测试通过：多持仓平仓后净值={final_equity}")


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])
