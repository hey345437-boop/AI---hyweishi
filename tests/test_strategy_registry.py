# -*- coding: utf-8 -*-
"""
策略注册表测试
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from strategies.strategy_registry import (
    StrategyRegistry,
    get_strategy_registry,
    list_all_strategies,
    get_strategy_display_name,
    is_custom_strategy,
    get_strategy_type,
    validate_and_fallback_strategy,
    BUILTIN_STRATEGIES,
)


class TestStrategyRegistry:
    """策略注册表测试"""

    def test_singleton(self):
        """测试单例模式"""
        registry1 = get_strategy_registry()
        registry2 = get_strategy_registry()
        assert registry1 is registry2

    def test_builtin_strategies_registered(self):
        """测试内置策略已注册"""
        registry = get_strategy_registry()
        strategies = registry.list_strategies()
        
        strategy_ids = [s['strategy_id'] for s in strategies]
        assert 'strategy_v1' in strategy_ids
        assert 'strategy_v2' in strategy_ids

    def test_get_strategy_meta(self):
        """测试获取策略元数据"""
        registry = get_strategy_registry()
        
        meta = registry.get_strategy_meta('strategy_v2')
        assert meta is not None
        assert meta['strategy_id'] == 'strategy_v2'
        assert 'display_name' in meta
        assert 'class_name' in meta

    def test_get_nonexistent_strategy(self):
        """测试获取不存在的策略"""
        registry = get_strategy_registry()
        
        meta = registry.get_strategy_meta('nonexistent_strategy')
        assert meta is None

    def test_validate_strategy_id(self):
        """测试策略 ID 验证"""
        registry = get_strategy_registry()
        
        assert registry.validate_strategy_id('strategy_v1') is True
        assert registry.validate_strategy_id('strategy_v2') is True
        assert registry.validate_strategy_id('invalid') is False


class TestStrategyHelpers:
    """策略辅助函数测试"""

    def test_list_all_strategies(self):
        """测试列出所有策略"""
        strategies = list_all_strategies()
        
        assert len(strategies) >= 2
        assert all(isinstance(s, tuple) and len(s) == 2 for s in strategies)
        
        # 检查格式 (display_name, strategy_id)
        for display_name, strategy_id in strategies:
            assert isinstance(display_name, str)
            assert isinstance(strategy_id, str)

    def test_get_strategy_display_name(self):
        """测试获取显示名称"""
        name = get_strategy_display_name('strategy_v2')
        assert '趋势策略' in name or 'v2' in name.lower()
        
        # 不存在的策略返回原 ID
        name = get_strategy_display_name('unknown')
        assert name == 'unknown'

    def test_is_custom_strategy(self):
        """测试判断自定义策略"""
        assert is_custom_strategy('strategy_v1') is False
        assert is_custom_strategy('strategy_v2') is False
        assert is_custom_strategy('my_custom_strategy') is True

    def test_get_strategy_type(self):
        """测试获取策略类型"""
        assert get_strategy_type('strategy_v1') == 'builtin'
        assert get_strategy_type('strategy_v2') == 'builtin'
        assert get_strategy_type('custom_strategy') == 'custom'

    def test_validate_and_fallback(self):
        """测试验证并回退"""
        # 有效策略
        result = validate_and_fallback_strategy('strategy_v2')
        assert result == 'strategy_v2'
        
        # None 返回默认
        result = validate_and_fallback_strategy(None)
        assert result == 'strategy_v2'  # 默认策略
        
        # 无效策略抛出异常
        with pytest.raises(ValueError):
            validate_and_fallback_strategy('invalid_strategy')
