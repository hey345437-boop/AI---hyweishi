# tests/test_order_size_calculator.py
# 订单数量计算器属性测试

import pytest
import math
from hypothesis import given, strategies as st, settings
from unittest.mock import Mock, MagicMock

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from order_size_calculator import OrderSizeCalculator, InstrumentInfo, OrderSizeResult


class MockExchangeAdapter:
    """模拟交易所适配器"""
    
    def __init__(self, ct_val: float = 0.01, lot_sz: float = 1.0, min_sz: float = 1.0):
        self.ct_val = ct_val
        self.lot_sz = lot_sz
        self.min_sz = min_sz
        self.exchange = MagicMock()
        self.exchange.markets = {
            'BTC/USDT:USDT': {
                'contractSize': ct_val,
                'precision': {'amount': lot_sz, 'price': 0.1},
                'limits': {'amount': {'min': min_sz}},
                'contractMultiplier': 1.0
            },
            'ETH/USDT:USDT': {
                'contractSize': 0.1,
                'precision': {'amount': 1.0, 'price': 0.01},
                'limits': {'amount': {'min': 1.0}},
                'contractMultiplier': 1.0
            }
        }
    
    def normalize_symbol(self, symbol: str) -> str:
        if ':' in symbol:
            return symbol
        base = symbol.split('/')[0] if '/' in symbol else symbol
        return f"{base}/USDT:USDT"
    
    def initialize(self):
        pass


class TestOrderSizeCalculatorProperties:
    """订单数量计算器属性测试"""
    
    @given(
        equity=st.floats(min_value=100, max_value=100000, allow_nan=False, allow_infinity=False),
        risk_pct=st.floats(min_value=0.01, max_value=0.1, allow_nan=False, allow_infinity=False),
        leverage=st.integers(min_value=1, max_value=100)
    )
    @settings(max_examples=100)
    def test_order_size_formula_notional(self, equity, risk_pct, leverage):
        """
        **Feature: trading-bot-v2-fixes, Property 3: Order Size Calculation Formula**
        
        For any order size calculation with equity, risk_pct, leverage, and price,
        the resulting notional SHALL equal equity * risk_pct * leverage.
        
        **Validates: Requirements 4.1**
        """
        # Arrange
        adapter = MockExchangeAdapter(ct_val=0.01, lot_sz=1.0, min_sz=1.0)
        calculator = OrderSizeCalculator(adapter)
        price = 50000.0  # 固定价格简化测试
        
        # Act
        result = calculator.calculate("BTC/USDT:USDT", equity, risk_pct, leverage, price)
        
        # Assert
        expected_notional = equity * risk_pct * leverage
        assert abs(result.notional - expected_notional) < 0.01, \
            f"Notional mismatch: expected {expected_notional}, got {result.notional}"
    
    @given(
        equity=st.floats(min_value=100, max_value=100000, allow_nan=False, allow_infinity=False),
        risk_pct=st.floats(min_value=0.01, max_value=0.1, allow_nan=False, allow_infinity=False),
        leverage=st.integers(min_value=1, max_value=100)
    )
    @settings(max_examples=100)
    def test_order_size_formula_margin(self, equity, risk_pct, leverage):
        """
        **Feature: trading-bot-v2-fixes, Property 3: Order Size Calculation Formula**
        
        For any order size calculation, margin SHALL equal equity * risk_pct.
        
        **Validates: Requirements 4.1**
        """
        # Arrange
        adapter = MockExchangeAdapter(ct_val=0.01, lot_sz=1.0, min_sz=1.0)
        calculator = OrderSizeCalculator(adapter)
        price = 50000.0
        
        # Act
        result = calculator.calculate("BTC/USDT:USDT", equity, risk_pct, leverage, price)
        
        # Assert
        expected_margin = equity * risk_pct
        assert abs(result.margin - expected_margin) < 0.01, \
            f"Margin mismatch: expected {expected_margin}, got {result.margin}"
    
    @given(
        lot_sz=st.sampled_from([1.0, 0.1, 0.01, 10.0]),
        contracts_raw=st.floats(min_value=0.1, max_value=1000, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=100)
    def test_contract_count_rounding(self, lot_sz, contracts_raw):
        """
        **Feature: trading-bot-v2-fixes, Property 4: Contract Count Rounding**
        
        For any contract count calculation, the result SHALL be rounded down
        to the nearest lotSz multiple.
        
        **Validates: Requirements 4.4**
        """
        # Arrange
        adapter = MockExchangeAdapter(ct_val=0.01, lot_sz=lot_sz, min_sz=0.01)
        calculator = OrderSizeCalculator(adapter)
        
        # 计算需要的 equity 来产生 contracts_raw
        price = 50000.0
        ct_val = 0.01
        # contracts_raw = notional / (price * ct_val)
        # notional = contracts_raw * price * ct_val
        notional = contracts_raw * price * ct_val
        # notional = margin * leverage = equity * risk_pct * leverage
        # 假设 risk_pct=0.03, leverage=20
        risk_pct = 0.03
        leverage = 20
        equity = notional / (risk_pct * leverage)
        
        if equity < 1:
            return  # 跳过太小的值
        
        # Act
        result = calculator.calculate("BTC/USDT:USDT", equity, risk_pct, leverage, price)
        
        # Assert
        # 结果应该是 lot_sz 的整数倍
        if result.contracts > 0:
            remainder = result.contracts % lot_sz
            assert remainder < 1e-9 or abs(remainder - lot_sz) < 1e-9, \
                f"Contracts {result.contracts} is not a multiple of lotSz {lot_sz}"
            
            # 结果应该 <= contracts_raw（向下取整）
            expected_contracts = math.floor(contracts_raw / lot_sz) * lot_sz
            assert abs(result.contracts - expected_contracts) < lot_sz, \
                f"Expected ~{expected_contracts}, got {result.contracts}"


class TestOrderSizeCalculatorEdgeCases:
    """边界情况测试"""
    
    def test_price_zero_rejected(self):
        """价格为零应该被拒绝"""
        adapter = MockExchangeAdapter()
        calculator = OrderSizeCalculator(adapter)
        
        result = calculator.calculate("BTC/USDT:USDT", 200, 0.03, 20, 0)
        
        assert not result.is_valid
        assert "价格" in result.error or "price" in result.error.lower()
    
    def test_equity_zero_rejected(self):
        """净值为零应该被拒绝"""
        adapter = MockExchangeAdapter()
        calculator = OrderSizeCalculator(adapter)
        
        result = calculator.calculate("BTC/USDT:USDT", 0, 0.03, 20, 50000)
        
        assert not result.is_valid
        assert "净值" in result.error or "equity" in result.error.lower()
    
    def test_sz_below_min_rejected(self):
        """计算张数小于最小张数应该被拒绝"""
        # 设置很大的 min_sz
        adapter = MockExchangeAdapter(ct_val=0.01, lot_sz=1.0, min_sz=1000)
        calculator = OrderSizeCalculator(adapter)
        
        # 小额订单
        result = calculator.calculate("BTC/USDT:USDT", 100, 0.01, 1, 50000)
        
        assert not result.is_valid
        assert "minSz" in result.log_line or "最小" in result.error
    
    def test_example_200u_3pct_20x(self):
        """
        验证示例：equity=200u, risk_pct=0.03, leverage=20
        预期：margin=6u, notional=120u
        
        OKX BTC-USDT-SWAP 合约面值 ctVal=0.01 BTC
        当 BTC 价格=50000 时，每张合约价值 = 0.01 * 50000 = 500 USD
        notional=120 USD，contracts = 120 / 500 = 0.24 张
        向下取整到 lotSz=0.01 -> 0.24 张
        
        但 minSz=0.01，所以 0.24 >= 0.01，应该有效
        """
        # OKX BTC-USDT-SWAP: ctVal=0.01 BTC, lotSz=0.01, minSz=0.01
        adapter = MockExchangeAdapter(ct_val=0.01, lot_sz=0.01, min_sz=0.01)
        calculator = OrderSizeCalculator(adapter)
        
        result = calculator.calculate("BTC/USDT:USDT", 200, 0.03, 20, 50000)
        
        assert result.is_valid, f"Expected valid, got error: {result.error}"
        assert abs(result.margin - 6.0) < 0.01, f"Expected margin=6, got {result.margin}"
        assert abs(result.notional - 120.0) < 0.01, f"Expected notional=120, got {result.notional}"
        
        # contracts = 120 / (50000 * 0.01) = 120 / 500 = 0.24
        # 向下取整到 0.01 -> 0.24
        expected_contracts = 0.24
        assert abs(result.contracts - expected_contracts) < 0.01, \
            f"Expected contracts={expected_contracts}, got {result.contracts}"
        
        # 验证日志行包含关键信息
        assert "equity=200" in result.log_line
        assert "margin=6" in result.log_line
        assert "notional=120" in result.log_line
    
    def test_log_line_format(self):
        """验证日志行格式"""
        adapter = MockExchangeAdapter(ct_val=0.01, lot_sz=1.0, min_sz=1.0)
        calculator = OrderSizeCalculator(adapter)
        
        result = calculator.calculate("BTC/USDT:USDT", 200, 0.03, 20, 50000)
        
        # 日志行应该包含所有关键字段
        assert "[size]" in result.log_line
        assert "equity=" in result.log_line
        assert "risk=" in result.log_line
        assert "lev=" in result.log_line
        assert "margin=" in result.log_line
        assert "notional=" in result.log_line
        assert "price=" in result.log_line
        assert "ctVal=" in result.log_line
        assert "lot=" in result.log_line
        assert "sz=" in result.log_line
        assert "contracts" in result.log_line
        assert "base=" in result.log_line


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
