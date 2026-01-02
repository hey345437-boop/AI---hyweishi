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
# exchange_adapters/base.py
# 交易所适配器基类

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional


class ExchangeAdapter(ABC):
    """
    交易所适配器基类，定义统一接口
    """
    
    @abstractmethod
    def __init__(self, config: Dict[str, Any]):
        """
        初始化适配器
        
        参数:
        - config: 交易所配置，包含 api_key, secret, password, env 等
        """
        self.config = config
        self.env = config.get('env', 'demo')
        self.exchange = None
        
    @abstractmethod
    def initialize(self):
        """
        初始化交易所连接
        """
        pass
        
    @abstractmethod
    def fetch_ohlcv(self, symbol: str, timeframe: str, limit: int = 100) -> Any:
        """
        获取 K 线数据
        
        参数:
        - symbol: 交易对，例如 'BTC/USDT:USDT'
        - timeframe: 时间周期，例如 '1m', '5m', '1h'
        - limit: 数量限制
        
        返回:
        - K 线数据
        """
        pass
        
    @abstractmethod
    def fetch_ticker(self, symbol: str) -> Any:
        """
        获取实时价格
        
        参数:
        - symbol: 交易对
        
        返回:
        - 实时价格数据
        """
        pass
        
    @abstractmethod
    def fetch_orderbook(self, symbol: str) -> Any:
        """
        获取市场深度
        
        参数:
        - symbol: 交易对
        
        返回:
        - 市场深度数据
        """
        pass
        
    @abstractmethod
    def fetch_balance(self, params: Optional[Dict] = None) -> Any:
        """
        获取账户余额
        
        参数:
        - params: 可选参数
        
        返回:
        - 账户余额数据
        """
        pass
        
    @abstractmethod
    def fetch_positions(self, symbols: Optional[list] = None) -> Any:
        """
        获取持仓信息
        
        参数:
        - symbols: 可选，指定交易对列表
        
        返回:
        - 持仓数据
        """
        pass
        
    @abstractmethod
    def create_order(self, symbol: str, side: str, amount: float, order_type: str = 'market', params: Optional[Dict] = None) -> Any:
        """
        下单
        
        参数:
        - symbol: 交易对
        - side: 方向，'buy' 或 'sell'
        - amount: 数量
        - order_type: 订单类型，默认 'market'
        - params: 可选参数
        
        返回:
        - 订单数据
        """
        pass
        
    @abstractmethod
    def cancel_order(self, order_id: str, symbol: str) -> Any:
        """
        撤单
        
        参数:
        - order_id: 订单 ID
        - symbol: 交易对
        
        返回:
        - 撤单结果
        """
        pass
        
    @abstractmethod
    def set_margin_mode(self, margin_mode: str, symbol: str) -> Any:
        """
        设置保证金模式
        
        参数:
        - margin_mode: 保证金模式，'crossed' 或 'isolated'
        - symbol: 交易对
        
        返回:
        - 设置结果
        """
        pass
        
    @abstractmethod
    def set_leverage(self, leverage: int, symbol: str) -> Any:
        """
        设置杠杆
        
        参数:
        - leverage: 杠杆倍数
        - symbol: 交易对
        
        返回:
        - 设置结果
        """
        pass
        
    @abstractmethod
    def create_market_order(self, symbol: str, side: str, amount: float, params: Optional[Dict] = None) -> Any:
        """
        创建市价单
        
        参数:
        - symbol: 交易对
        - side: 方向，'buy' 或 'sell'
        - amount: 数量
        - params: 可选参数
        
        返回:
        - 订单数据
        """
        pass
        
    @abstractmethod
    def close(self) -> None:
        """
        关闭连接
        """
        pass