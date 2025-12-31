# -*- coding: utf-8 -*-
"""
策略模块

包含策略注册、生成、验证等功能
"""

from .strategy_registry import (
    StrategyRegistry,
    get_strategy_registry,
    list_all_strategies,
    get_strategy_display_name,
    is_custom_strategy,
    get_strategy_type,
    get_strategy_default_params,
    validate_and_fallback_strategy,
    save_new_strategy,
    delete_strategy,
    list_user_strategies,
    is_advanced_strategy,
    get_strategy_risk_config,
    BUILTIN_STRATEGIES,
    DEFAULT_STRATEGY_ID
)
from .strategy_generator import StrategyGenerator
from .strategy_validator import StrategyValidator

__all__ = [
    # strategy_registry
    'StrategyRegistry', 'get_strategy_registry', 'list_all_strategies',
    'get_strategy_display_name', 'is_custom_strategy', 'get_strategy_type',
    'get_strategy_default_params', 'validate_and_fallback_strategy',
    'save_new_strategy', 'delete_strategy', 'list_user_strategies',
    'is_advanced_strategy', 'get_strategy_risk_config',
    'BUILTIN_STRATEGIES', 'DEFAULT_STRATEGY_ID',
    # strategy_generator
    'StrategyGenerator',
    # strategy_validator
    'StrategyValidator'
]
