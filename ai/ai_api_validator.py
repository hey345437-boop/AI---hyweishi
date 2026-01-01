# -*- coding: utf-8 -*-
# ============================================================================
#
#    _   _  __   __ __        __  _____ ___  ____   _   _  ___ 
#   | | | | \ \ / / \ \      / / | ____||_ _|/ ___| | | | ||_ _|
#   | |_| |  \ V /   \ \ /\ / /  |  _|   | | \___ \ | |_| | | | 
#   |  _  |   | |     \ V  V /   | |___  | |  ___) ||  _  | | | 
#   |_| |_|   |_|      \_/\_/    |_____||___||____/ |_| |_||___|
#
#                         何 以 为 势
#                  Quantitative Trading System
#
#   Copyright (c) 2024-2025 HyWeiShi. All Rights Reserved.
#   License: AGPL-3.0
#
# ============================================================================
"""
AI API Key 验证模块

此模块是 ai_providers.py 验证功能的简单封装，
保持向后兼容性。所有实际验证逻辑在 ai_providers.py 中实现。
"""

from typing import Tuple

# 从 ai_providers 导入验证函数
from .ai_providers import (
    verify_api_key as _verify_api_key,
    verify_api_key_sync,
    quick_validate_key_format,
    AI_PROVIDERS,
    PROVIDER_ALIASES,
)


# 向后兼容的异步验证函数
async def verify_api_key(ai_id: str, api_key: str) -> Tuple[bool, str]:
    """验证 API Key（异步）"""
    return await _verify_api_key(ai_id, api_key)


# 向后兼容的同步验证函数（已从 ai_providers 导入）
# verify_api_key_sync 和 quick_validate_key_format 直接使用导入的版本


# API Key 格式提示（从 ai_providers 动态生成）
def _build_api_key_patterns():
    """从 ai_providers 构建 API Key 格式提示"""
    patterns = {}
    for provider_id, provider in AI_PROVIDERS.items():
        prefix = provider.key_prefix or ""
        hint = f"{provider.name} Key 应以 {prefix} 开头" if prefix else f"{provider.name} API Key 无固定前缀"
        patterns[provider_id] = (prefix, hint)
    
    # 添加别名
    for alias, target in PROVIDER_ALIASES.items():
        if target in patterns:
            patterns[alias] = patterns[target]
    
    return patterns

API_KEY_PATTERNS = _build_api_key_patterns()
