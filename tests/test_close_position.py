# tests/test_close_position.py
# 一键平仓属性测试

import pytest
from hypothesis import given, strategies as st, settings
from unittest.mock import Mock, MagicMock, patch

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from close_position import (
    close_all_positions, ClosePositionResult, CloseAllResult,
    _close_single_position, format_close_result_table
)


class MockAdapter:
    """模拟 OKX 适配器"""
    
    def __init__(self, positions=None, orders=None):
        self.positions = positions or []
        self.orders = orders or []
        self.exchange = MagicMock()
        self.exchange.fetch_open_orders = MagicMock(return_value=self.orders)
        self.exchange.fetch_positions = MagicMock(return_value=self.positions)
        self.exchange.cancel_order = MagicMock(return_value={'id': 'cancelled'})
        self._created_orders = []
    
    def initialize(self):
        pass
    
    def normalize_symbol(self, symbol):
        if ':' in symbol:
            return symbol
        return f"{symbol}:USDT"
    
    def fetch_positions(self, symbols=None):
        return self.positions
    
    def create_order(self, symbol, side, amount, order_type, params=None, reduce_only=False):
        order = {
            'id': f'order_{len(self._created_orders)}',
            'symbol': symbol,
            'side': side,
            'amount': amount,
            'type': order_type,
            'params': params,
            'reduce_only': reduce_only
        }
        self._created_orders.append(order)
        return order


class TestClosePositionProperties:
    """一键平仓属性测试"""
    
    @given(
        pos_side=st.sampled_from(['long', 'short']),
        contracts=st.floats(min_value=0.01, max_value=100, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=100)
    def test_close_order_uses_correct_pos_side(self, pos_side, contracts):
        """
        **Feature: trading-bot-v2-fixes, Property 1: Close Order Uses Correct posSide**
        
        For any close order created for a position, the posSide parameter SHALL
        match the position direction.
        
        **Validates: Requirements 1.3, 1.4**
        """
        # Arrange
        position = {
            'symbol': 'BTC/USDT:USDT',
            'side': pos_side,
            'contracts': contracts,
            'positionAmt': contracts if pos_side == 'long' else -contracts
        }
        adapter = MockAdapter(positions=[position])
        
        # Act
        result = _close_single_position(adapter, position)
        
        # Assert
        assert result.pos_side == pos_side
        
        # 验证创建的订单使用了正确的 posSide
        if adapter._created_orders:
            order = adapter._created_orders[-1]
            assert order['params']['posSide'] == pos_side, \
                f"Expected posSide={pos_side}, got {order['params'].get('posSide')}"
    
    @given(
        pos_side=st.sampled_from(['long', 'short']),
        contracts=st.floats(min_value=0.01, max_value=100, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=100)
    def test_close_order_has_reduce_only_flag(self, pos_side, contracts):
        """
        **Feature: trading-bot-v2-fixes, Property 2: Close Order Has reduceOnly Flag**
        
        For any close order created by close_all_positions, the reduceOnly
        parameter SHALL be True.
        
        **Validates: Requirements 1.3**
        """
        # Arrange
        position = {
            'symbol': 'BTC/USDT:USDT',
            'side': pos_side,
            'contracts': contracts
        }
        adapter = MockAdapter(positions=[position])
        
        # Act
        result = _close_single_position(adapter, position)
        
        # Assert
        if adapter._created_orders:
            order = adapter._created_orders[-1]
            assert order['reduce_only'] == True, \
                "Close order must have reduce_only=True"
            assert order['params'].get('reduceOnly') == True, \
                "Close order params must have reduceOnly=True"


class TestClosePositionEdgeCases:
    """边界情况测试"""
    
    def test_close_long_position_uses_sell(self):
        """long 持仓应该用 sell 平仓"""
        position = {
            'symbol': 'BTC/USDT:USDT',
            'side': 'long',
            'contracts': 1.0
        }
        adapter = MockAdapter()
        
        _close_single_position(adapter, position)
        
        assert len(adapter._created_orders) == 1
        assert adapter._created_orders[0]['side'] == 'sell'
    
    def test_close_short_position_uses_buy(self):
        """short 持仓应该用 buy 平仓"""
        position = {
            'symbol': 'BTC/USDT:USDT',
            'side': 'short',
            'contracts': 1.0
        }
        adapter = MockAdapter()
        
        _close_single_position(adapter, position)
        
        assert len(adapter._created_orders) == 1
        assert adapter._created_orders[0]['side'] == 'buy'
    
    def test_no_position_skipped(self):
        """无持仓应该跳过"""
        position = {
            'symbol': 'BTC/USDT:USDT',
            'side': 'long',
            'contracts': 0
        }
        adapter = MockAdapter()
        
        result = _close_single_position(adapter, position)
        
        assert result.status == "skipped"
        assert len(adapter._created_orders) == 0
    
    def test_close_all_returns_structured_result(self):
        """验证返回结构化结果"""
        positions = [
            {'symbol': 'BTC/USDT:USDT', 'side': 'long', 'contracts': 1.0},
            {'symbol': 'ETH/USDT:USDT', 'side': 'short', 'contracts': 2.0}
        ]
        adapter = MockAdapter(positions=positions)
        
        result = close_all_positions(adapter)
        
        assert isinstance(result, CloseAllResult)
        assert len(result.closed_positions) == 2
        
        # 验证可以转换为字典
        result_dict = result.to_dict()
        assert 'success' in result_dict
        assert 'closed_positions' in result_dict
    
    def test_format_result_table(self):
        """验证结果表格格式化"""
        result = CloseAllResult(
            success=True,
            cancelled_orders=['order1', 'order2'],
            closed_positions=[
                ClosePositionResult(
                    symbol='BTC/USDT:USDT',
                    pos_side='long',
                    before_sz=1.0,
                    after_sz=0.0,
                    order_id='close_order_1',
                    status='success'
                )
            ]
        )
        
        table = format_close_result_table(result)
        
        # 验证表格包含关键信息
        assert 'BTC/USDT:USDT' in table
        assert 'long' in table
        assert 'success' in table or '成功' in table
        assert '撤销委托数' in table


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
