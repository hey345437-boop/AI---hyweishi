# -*- coding: utf-8 -*-
"""
核心引擎模块

包含交易引擎、回测引擎、市场数据提供者等核心组件
"""

from .trade_engine import (
    get_exchange_adapter,
    initialize_exchange,
    initialize_market_data_provider,
    fetch_ohlcv,
    fetch_ticker,
    fetch_orderbook,
    fetch_balance,
    fetch_positions,
    create_order,
    cancel_order,
    close
)

__all__ = [
    'get_exchange_adapter',
    'initialize_exchange',
    'initialize_market_data_provider',
    'fetch_ohlcv',
    'fetch_ticker',
    'fetch_orderbook',
    'fetch_balance',
    'fetch_positions',
    'create_order',
    'cancel_order',
    'close'
]
