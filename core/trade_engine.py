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
# ============================================================================
"""
交易引擎入口 - 支持 OKX 适配器
"""
import os
from typing import Dict, Any, Optional
from exchange_adapters.factory import ExchangeAdapterFactory
from .market_data_provider import MarketDataProvider


def get_exchange_adapter(config: Dict[str, Any]) -> Any:
    """
    获取交易所适配器
    
    参数:
    - config: 交易所配置，包含 exchange_type, api_key, secret, password, env 等
    
    返回:
    - 交易所适配器实例
    """
    return ExchangeAdapterFactory.get_exchange_adapter(config)


def initialize_exchange(config: Dict[str, Any]) -> Any:
    """
    初始化交易所连接
    
    参数:
    - config: 交易所配置，包含 exchange_type, api_key, secret, password, env 等
    
    返回:
    - 交易所适配器实例
    """
    adapter = get_exchange_adapter(config)
    adapter.initialize()
    return adapter


def initialize_market_data_provider(exchange: Any, timeframe: str, ohlcv_limit: int = 100) -> MarketDataProvider:
    """
    初始化市场数据提供者
    
    参数:
    - exchange: 交易所适配器实例
    - timeframe: 默认时间周期
    - ohlcv_limit: 默认K线数量
    
    返回:
    - MarketDataProvider实例
    """
    return MarketDataProvider(
        exchange_adapter=exchange,
        timeframe=timeframe,
        ohlcv_limit=ohlcv_limit
    )


def fetch_ohlcv(provider: MarketDataProvider, symbol: str, timeframe: str, limit: int = 100) -> Any:
    """
    获取 K 线数据
    
    参数:
    - provider: MarketDataProvider实例
    - symbol: 交易对，例如 'BTC/USDT:USDT'
    - timeframe: 时间周期，例如 '1m', '5m', '1h'
    - limit: 数量限制
    
    返回:
    - K 线数据
    """
    return provider.get_ohlcv(symbol, timeframe, limit)


def fetch_ticker(provider: MarketDataProvider, symbol: str) -> Any:
    """
    获取实时价格
    
    参数:
    - provider: MarketDataProvider实例
    - symbol: 交易对
    
    返回:
    - 实时价格数据
    """
    return provider.get_ticker(symbol)


def fetch_orderbook(adapter: Any, symbol: str) -> Any:
    """
    获取市场深度
    
    参数:
    - adapter: 交易所适配器实例
    - symbol: 交易对
    
    返回:
    - 市场深度数据
    """
    return adapter.fetch_orderbook(symbol)


def fetch_balance(provider: MarketDataProvider) -> Any:
    """
    获取账户余额
    
    参数:
    - provider: MarketDataProvider实例
    
    返回:
    - 账户余额数据
    """
    return provider.get_balance()


def fetch_positions(provider: MarketDataProvider, symbols: Optional[list] = None) -> Any:
    """
    获取持仓信息
    
    参数:
    - provider: MarketDataProvider实例
    - symbols: 可选，指定交易对列表
    
    返回:
    - 持仓数据
    """
    return provider.get_positions(symbols)


def create_order(adapter: Any, provider: MarketDataProvider, symbol: str, side: str, amount: float, order_type: str = 'market', params: Optional[Dict] = None) -> Any:
    """
    下单
    
    参数:
    - adapter: 交易所适配器实例
    - provider: MarketDataProvider实例
    - symbol: 交易对
    - side: 方向，'buy' 或 'sell'
    - amount: 数量
    - order_type: 订单类型，默认 'market'
    - params: 可选参数
    
    返回:
    - 订单数据
    """
    order_result = adapter.create_order(symbol, side, amount, order_type, params)
    
    # 订单执行成功后，使相关缓存失效
    provider.invalidate_positions()
    provider.invalidate_balance()
    provider.invalidate_ohlcv(symbol)
    provider.invalidate_ticker(symbol)
    
    return order_result


def cancel_order(adapter: Any, provider: MarketDataProvider, order_id: str, symbol: str) -> Any:
    """
    撤单
    
    参数:
    - adapter: 交易所适配器实例
    - provider: MarketDataProvider实例
    - order_id: 订单 ID
    - symbol: 交易对
    
    返回:
    - 撤单结果
    """
    cancel_result = adapter.cancel_order(order_id, symbol)
    
    # 撤单成功后，使相关缓存失效
    provider.invalidate_positions()
    provider.invalidate_balance()
    provider.invalidate_ohlcv(symbol)
    provider.invalidate_ticker(symbol)
    
    return cancel_result


def close(adapter: Any) -> None:
    """
    关闭连接
    
    参数:
    - adapter: 交易所适配器实例
    """
    adapter.close()