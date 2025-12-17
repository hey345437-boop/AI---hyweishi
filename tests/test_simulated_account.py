# tests/test_simulated_account.py
# 模拟账户测试

import pytest
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from simulated_account import (
    SimulatedAccount,
    SimulatedPosition,
    AccountState,
    create_simulated_account,
    calc_required_margin
)


class TestSimulatedPosition:
    """测试模拟持仓"""
    
    def test_notional_value(self):
        """测试名义价值计算"""
        pos = SimulatedPosition(
            symbol="BTC/USDT:USDT",
            side="long",
            qty=0.001,
            entry_price=50000,
            leverage=50
        )
        
        # 名义价值 = 0.001 * 50000 = 50
        assert pos.notional_value == 50.0
    
    def test_margin(self):
        """测试保证金计算"""
        pos = SimulatedPosition(
            symbol="BTC/USDT:USDT",
            side="long",
            qty=0.001,
            entry_price=50000,
            leverage=50
        )
        
        # 保证金 = 50 / 50 = 1
        assert pos.margin == 1.0
    
    def test_unrealized_pnl_long_profit(self):
        """测试多头盈利"""
        pos = SimulatedPosition(
            symbol="BTC/USDT:USDT",
            side="long",
            qty=0.001,
            entry_price=50000,
            leverage=50
        )
        
        # 价格上涨到 51000
        upnl = pos.calc_unrealized_pnl(51000)
        # (51000 - 50000) * 0.001 = 1
        assert upnl == 1.0
    
    def test_unrealized_pnl_short_profit(self):
        """测试空头盈利"""
        pos = SimulatedPosition(
            symbol="BTC/USDT:USDT",
            side="short",
            qty=0.001,
            entry_price=50000,
            leverage=50
        )
        
        # 价格下跌到 49000
        upnl = pos.calc_unrealized_pnl(49000)
        # (50000 - 49000) * 0.001 = 1
        assert upnl == 1.0


class TestAccountState:
    """测试账户状态"""
    
    def test_equity_calculation(self):
        """测试权益计算"""
        state = AccountState(
            wallet_balance=200.0,
            unrealized_pnl=10.0,
            used_margin=5.0
        )
        
        # equity = 200 + 10 = 210
        assert state.equity == 210.0
    
    def test_free_margin_calculation(self):
        """测试可用保证金计算"""
        state = AccountState(
            wallet_balance=200.0,
            unrealized_pnl=10.0,
            used_margin=5.0
        )
        
        # free_margin = 210 - 5 = 205
        assert state.free_margin == 205.0


class TestSimulatedAccount:
    """测试模拟账户"""
    
    def test_initial_state(self):
        """测试初始状态"""
        account = SimulatedAccount(initial_balance=200.0)
        
        prices = {}
        state = account.get_state(prices)
        
        assert state.wallet_balance == 200.0
        assert state.unrealized_pnl == 0.0
        assert state.equity == 200.0
        assert state.used_margin == 0.0
        assert state.free_margin == 200.0
    
    def test_open_position(self):
        """测试开仓"""
        account = SimulatedAccount(
            initial_balance=200.0,
            max_margin_ratio=0.10,
            default_leverage=50
        )
        
        # 开仓：0.001 BTC @ 50000，保证金 = 50/50 = 1
        success, msg, pos = account.open_position(
            symbol="BTC/USDT:USDT",
            side="long",
            qty=0.001,
            entry_price=50000
        )
        
        assert success
        assert pos is not None
        assert pos.margin == 1.0
        
        # 检查账户状态
        prices = {"BTC/USDT:USDT": 50000}
        state = account.get_state(prices)
        
        assert state.used_margin == 1.0
        assert state.free_margin == 199.0  # 200 - 1
    
    def test_risk_check_blocks_over_limit(self):
        """
        测试风控阻止超限开仓
        
        场景：
        - 权益 $193
        - 最大保证金占比 10% -> 最大允许保证金 $19.3
        - 已用保证金 $1.74
        - 尝试开仓需要保证金 $20 -> 应该被拒绝
        """
        account = SimulatedAccount(
            initial_balance=193.0,
            max_margin_ratio=0.10,
            default_leverage=50
        )
        
        # 先开一个小仓位，保证金 $1.74
        # 名义价值 = 1.74 * 50 = 87
        # qty = 87 / 50000 = 0.00174
        account.open_position(
            symbol="BTC/USDT:USDT",
            side="long",
            qty=0.00174,
            entry_price=50000
        )
        
        prices = {"BTC/USDT:USDT": 50000}
        state = account.get_state(prices)
        
        # 验证已用保证金约 $1.74
        assert abs(state.used_margin - 1.74) < 0.01
        
        # 尝试开仓需要保证金 $20
        # 名义价值 = 20 * 50 = 1000
        # qty = 1000 / 50000 = 0.02
        success, msg, pos = account.open_position(
            symbol="ETH/USDT:USDT",
            side="long",
            qty=0.02,
            entry_price=50000
        )
        
        # 应该被拒绝：1.74 + 20 = 21.74 > 19.3
        assert not success
        assert "超过最大保证金限制" in msg
    
    def test_close_position_updates_wallet(self):
        """测试平仓更新钱包余额"""
        account = SimulatedAccount(
            initial_balance=200.0,
            max_margin_ratio=0.10,
            default_leverage=50
        )
        
        # 开仓
        account.open_position(
            symbol="BTC/USDT:USDT",
            side="long",
            qty=0.001,
            entry_price=50000
        )
        
        # 平仓（盈利）
        success, realized_pnl, msg = account.close_position(
            symbol="BTC/USDT:USDT",
            side="long",
            qty=0.001,
            close_price=51000,  # 价格上涨
            fee=0.1
        )
        
        assert success
        # 盈亏 = (51000 - 50000) * 0.001 - 0.1 = 1 - 0.1 = 0.9
        assert abs(realized_pnl - 0.9) < 0.01
        
        # 钱包余额应该增加
        assert account.wallet_balance == 200.9


class TestRiskControl:
    """测试风控逻辑"""
    
    def test_margin_ratio_check_within_limit(self):
        """测试保证金占比在限制内"""
        account = SimulatedAccount(
            initial_balance=193.0,
            max_margin_ratio=0.10,
            default_leverage=50
        )
        
        # 开仓使保证金占比接近但不超过 10%
        # 最大允许保证金 = 193 * 0.10 = 19.3
        # 开仓保证金 = 15（在限制内）
        # 名义价值 = 15 * 50 = 750
        # qty = 750 / 50000 = 0.015
        success, msg, pos = account.open_position(
            symbol="BTC/USDT:USDT",
            side="long",
            qty=0.015,
            entry_price=50000
        )
        
        assert success, f"开仓应该成功: {msg}"
        
        prices = {"BTC/USDT:USDT": 50000}
        is_ok, ratio, msg = account.check_margin_ratio(prices)
        
        # 保证金 = 750 / 50 = 15
        # 占比 = 15 / 193 = 7.77% < 10%
        assert is_ok
        assert ratio < 0.10
    
    def test_margin_ratio_check_blocks_over_limit(self):
        """测试风控阻止超限开仓"""
        account = SimulatedAccount(
            initial_balance=193.0,
            max_margin_ratio=0.10,
            default_leverage=50
        )
        
        # 尝试开仓使保证金占比超过 10%
        # 需要保证金 = 20 > 19.3
        # 名义价值 = 20 * 50 = 1000
        # qty = 1000 / 50000 = 0.02
        success, msg, pos = account.open_position(
            symbol="BTC/USDT:USDT",
            side="long",
            qty=0.02,
            entry_price=50000
        )
        
        # 应该被风控拒绝
        assert not success
        assert "超过最大保证金限制" in msg


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
