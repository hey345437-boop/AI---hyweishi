# tests/test_position_risk_calculator.py
# 持仓风控计算器测试
#
# 验证核心修复：使用名义价值 (Notional Value) 而非保证金 (Margin) 进行风控

import pytest
from hypothesis import given, settings
import hypothesis.strategies as st

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from position_risk_calculator import (
    PositionInfo,
    RiskCheckResult,
    PositionRiskCalculator,
    create_position_info_from_paper,
    create_position_info_from_exchange
)
from run_mode import RunMode


class TestPositionInfo:
    """测试 PositionInfo 数据类"""
    
    def test_notional_value_calculation(self):
        """测试名义价值计算"""
        pos = PositionInfo(
            symbol="BTC/USDT:USDT",
            side="long",
            qty=0.001,  # 0.001 BTC
            entry_price=50000,
            current_price=50000,
            contract_value=1.0,
            leverage=50
        )
        
        # 名义价值 = 0.001 * 50000 * 1.0 = 50 USD
        assert pos.notional_value == 50.0
        
        # 保证金 = 50 / 50 = 1 USD
        assert pos.margin_used == 1.0
    
    def test_notional_value_with_contract_value(self):
        """测试带合约面值的名义价值计算"""
        pos = PositionInfo(
            symbol="BTC/USDT:USDT",
            side="long",
            qty=10,  # 10 张合约
            entry_price=50000,
            current_price=50000,
            contract_value=0.01,  # 每张合约 0.01 BTC
            leverage=50
        )
        
        # 名义价值 = 10 * 50000 * 0.01 = 5000 USD
        assert pos.notional_value == 5000.0
        
        # 保证金 = 5000 / 50 = 100 USD
        assert pos.margin_used == 100.0
    
    @given(
        qty=st.floats(min_value=0.0001, max_value=100),
        price=st.floats(min_value=100, max_value=100000),
        leverage=st.integers(min_value=1, max_value=125)
    )
    @settings(max_examples=100)
    def test_notional_always_greater_than_margin(self, qty, price, leverage):
        """属性测试：名义价值始终 >= 保证金"""
        pos = PositionInfo(
            symbol="TEST",
            side="long",
            qty=qty,
            entry_price=price,
            current_price=price,
            contract_value=1.0,
            leverage=leverage
        )
        
        assert pos.notional_value >= pos.margin_used


class TestPositionRiskCalculator:
    """测试持仓风控计算器"""
    
    def test_risk_check_with_notional_value(self):
        """
        核心测试：验证风控使用名义价值而非保证金
        
        场景：
        - 权益 $193
        - 最大持仓比例 10% -> 最大允许名义价值 $19.3
        - 当前持仓名义价值 $35 -> 应该触发风控
        """
        calculator = PositionRiskCalculator(max_position_pct=0.10)
        
        # 模拟持仓：$35 名义价值
        positions = [
            PositionInfo(
                symbol="BTC/USDT:USDT",
                side="long",
                qty=0.00046,  # 约 $23 @ 50000
                entry_price=50000,
                current_price=50000,
                contract_value=1.0,
                leverage=50
            ),
            PositionInfo(
                symbol="ETH/USDT:USDT",
                side="long",
                qty=0.004,  # 约 $12 @ 3000
                entry_price=3000,
                current_price=3000,
                contract_value=1.0,
                leverage=50
            )
        ]
        
        # 权益 $193，最大允许 $19.3
        result = calculator.check_risk(equity=193, positions=positions)
        
        # 总名义价值约 $35，超过限额 $19.3
        assert result.total_notional > 19.3
        assert not result.can_trade, "应该触发风控，禁止开仓"
        
        # 保证金约 $0.7，但不应该用于风控判断
        assert result.margin_used < 2.0
    
    def test_risk_check_passes_when_under_limit(self):
        """测试：持仓名义价值低于限额时应该通过"""
        calculator = PositionRiskCalculator(max_position_pct=0.10)
        
        # 小仓位：$10 名义价值
        positions = [
            PositionInfo(
                symbol="BTC/USDT:USDT",
                side="long",
                qty=0.0002,  # $10 @ 50000
                entry_price=50000,
                current_price=50000,
                contract_value=1.0,
                leverage=50
            )
        ]
        
        # 权益 $193，最大允许 $19.3
        result = calculator.check_risk(equity=193, positions=positions)
        
        # 总名义价值 $10，低于限额 $19.3
        assert result.total_notional == 10.0
        assert result.can_trade, "应该允许开仓"
        assert result.remaining_notional > 0
    
    def test_proposed_notional_check(self):
        """测试：检查拟开仓的名义价值"""
        calculator = PositionRiskCalculator(max_position_pct=0.10)
        
        # 当前持仓 $10
        positions = [
            PositionInfo(
                symbol="BTC/USDT:USDT",
                side="long",
                qty=0.0002,
                entry_price=50000,
                current_price=50000,
                contract_value=1.0,
                leverage=50
            )
        ]
        
        # 权益 $193，最大允许 $19.3
        # 当前 $10，拟开仓 $15 -> 总计 $25 > $19.3
        result = calculator.check_risk(
            equity=193, 
            positions=positions, 
            proposed_notional=15.0
        )
        
        assert not result.can_trade, "拟开仓后超限，应该拒绝"
    
    @given(
        equity=st.floats(min_value=100, max_value=10000),
        position_notional=st.floats(min_value=0, max_value=1000),
        max_pct=st.floats(min_value=0.01, max_value=0.50)
    )
    @settings(max_examples=100)
    def test_risk_check_consistency(self, equity, position_notional, max_pct):
        """属性测试：风控判断一致性"""
        calculator = PositionRiskCalculator(max_position_pct=max_pct)
        
        # 创建一个持仓
        if position_notional > 0:
            positions = [
                PositionInfo(
                    symbol="TEST",
                    side="long",
                    qty=position_notional / 50000,  # 假设价格 50000
                    entry_price=50000,
                    current_price=50000,
                    contract_value=1.0,
                    leverage=50
                )
            ]
        else:
            positions = []
        
        result = calculator.check_risk(equity=equity, positions=positions)
        
        # 验证一致性
        max_allowed = equity * max_pct
        if result.total_notional <= max_allowed:
            assert result.can_trade
        else:
            assert not result.can_trade


class TestRunMode:
    """测试运行模式枚举"""
    
    def test_from_string_live(self):
        """测试 live 模式解析"""
        mode = RunMode.from_string("live")
        assert mode == RunMode.LIVE
        assert mode.is_live()
        assert not mode.is_paper()
    
    def test_from_string_paper(self):
        """测试 paper 模式解析"""
        mode = RunMode.from_string("paper")
        assert mode == RunMode.PAPER
        assert mode.is_paper()
        assert not mode.is_live()
    
    def test_legacy_mode_mapping(self):
        """测试旧模式映射"""
        # sim -> paper
        assert RunMode.from_string("sim") == RunMode.PAPER
        
        # paper_on_real -> paper
        assert RunMode.from_string("paper_on_real") == RunMode.PAPER
        
        # simulation -> paper
        assert RunMode.from_string("simulation") == RunMode.PAPER
    
    def test_forbidden_modes_raise_error(self):
        """测试禁止的模式抛出异常"""
        with pytest.raises(ValueError):
            RunMode.from_string("demo")
        
        with pytest.raises(ValueError):
            RunMode.from_string("sandbox")
        
        with pytest.raises(ValueError):
            RunMode.from_string("test")


class TestCreatePositionInfo:
    """测试持仓信息创建函数"""
    
    def test_create_from_paper_position(self):
        """测试从模拟持仓创建 PositionInfo"""
        paper_pos = {
            'symbol': 'BTC/USDT:USDT',
            'side': 'long',
            'qty': 0.001,
            'entry_price': 50000
        }
        
        pos = create_position_info_from_paper(
            paper_pos, 
            current_price=51000,
            leverage=50,
            contract_value=1.0
        )
        
        assert pos.symbol == 'BTC/USDT:USDT'
        assert pos.side == 'long'
        assert pos.qty == 0.001
        assert pos.entry_price == 50000
        assert pos.current_price == 51000
        assert pos.leverage == 50
        
        # 名义价值 = 0.001 * 51000 = 51
        assert pos.notional_value == 51.0
    
    def test_create_from_exchange_position(self):
        """测试从交易所持仓创建 PositionInfo"""
        exchange_pos = {
            'symbol': 'BTC/USDT:USDT',
            'contracts': 0.001,
            'entryPrice': 50000,
            'markPrice': 51000,
            'side': 'long',
            'leverage': 50,
            'contractSize': 1.0
        }
        
        pos = create_position_info_from_exchange(exchange_pos)
        
        assert pos.symbol == 'BTC/USDT:USDT'
        assert pos.side == 'long'
        assert pos.qty == 0.001
        assert pos.entry_price == 50000
        assert pos.current_price == 51000
        assert pos.leverage == 50


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
