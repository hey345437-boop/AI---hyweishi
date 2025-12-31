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
#   Copyright (c) 2024-2025 HeWeiShi. All Rights Reserved.
#   License: Apache License 2.0
#
# ============================================================================
# exchange_adapters/factory.py
# 交易所适配器工厂

from typing import Dict, Any
from .base import ExchangeAdapter
from .okx_adapter import OKXAdapter


class ExchangeAdapterFactory:
    """
    交易所适配器工厂，用于创建适配器实例
    """
    
    @staticmethod
    def get_exchange_adapter(config: Dict[str, Any]) -> ExchangeAdapter:
        """
        根据配置创建交易所适配器
        
        参数:
        - config: 交易所配置，包含 exchange_type, api_key, secret, password, env 等
        
        返回:
        - 交易所适配器实例
        """
        exchange_type = config.get('exchange_type', 'okx')
        
        if exchange_type == 'okx':
            return OKXAdapter(config)
        else:
            raise ValueError(f"不支持的交易所类型: {exchange_type}")