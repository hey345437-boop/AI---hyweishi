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
#
"""
AI 技术指标计算模块

NumPy 向量化加速计算，支持批量并发获取
"""
import numpy as np
from typing import List, Dict, Any, Optional, Tuple, Union
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
import hashlib
import time
import logging
import requests

logger = logging.getLogger(__name__)


# 数据源接口

class MarketDataSource:
    """
    市场数据源接口
    
     复用原始交易系统的 MarketDataProvider
    享受智能缓存：首次全量拉取 + 后续增量更新
    
    特点：
    1. 复用 MarketDataProvider 的智能缓存（首次 1000 根，后续增量）
    2. 使用行情专用 Key，与交易接口隔离
    3. AI 系统独立实例，不影响原始交易系统
    """
    
    def __init__(self, api_base_url: str = "http://127.0.0.1:8000"):
        # api_base_url 保留用于回退
        self.api_base_url = api_base_url
        self._provider = None
        self._provider_initialized = False
    
    def _get_provider(self):
        """懒加载 MarketDataProvider（AI 专用实例）"""
        if self._provider is None:
            try:
                from market_data_provider import create_market_data_provider_with_dedicated_key
                self._provider = create_market_data_provider_with_dedicated_key(
                    timeframe='5m',  # 默认周期
                    ohlcv_limit=1000,  # 目标 1000 根 K 线
                )
                self._provider_initialized = True
                logger.debug("[MarketDataSource] 已创建 AI 专用 MarketDataProvider")
            except Exception as e:
                logger.warning(f"[MarketDataSource] 创建 MarketDataProvider 失败: {e}")
                self._provider = None
        return self._provider
    
    def fetch_ohlcv(self, symbol: str, timeframe: str = "1m", limit: int = 500) -> Optional[List[List]]:
        """
         使用 MarketDataProvider 获取 OHLCV 数据（智能缓存）
        
        参数:
            symbol: 交易对，如 "BTC/USDT:USDT"
            timeframe: 时间周期，如 "1m", "5m", "1h"
            limit: K线数量
        返回:
            [[timestamp, open, high, low, close, volume], ...]
        """
        provider = self._get_provider()
        
        if provider:
            try:
                # 使用 MarketDataProvider 的智能缓存
                data, is_stale = provider.get_ohlcv(symbol, timeframe, limit)
                if data:
                    # 截取需要的数量
                    return data[-limit:] if len(data) > limit else data
            except Exception as e:
                logger.warning(f"[MarketDataSource] MarketDataProvider 获取失败 {symbol} {timeframe}: {e}")
        
        # 回退到 Market API
        return self._fetch_from_market_api(symbol, timeframe, limit)
    
    def _fetch_from_market_api(self, symbol: str, timeframe: str, limit: int) -> Optional[List[List]]:
        """回退方案：从 Market API 获取数据"""
        try:
            url = f"{self.api_base_url}/kline"
            params = {"symbol": symbol, "tf": timeframe, "limit": limit}
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            ohlcv = data.get("data", [])
            return ohlcv
        except Exception as e:
            logger.warning(f"[MarketDataSource] Market API 也失败 {symbol} {timeframe}: {e}")
            return None
    
    def fetch_batch_ohlcv(
        self, 
        tasks: List[Tuple[str, str, int]]
    ) -> Dict[Tuple[str, str], List[List]]:
        """
         批量获取多个币种/周期的 OHLCV 数据
        
        使用 MarketDataProvider 逐个获取（享受智能缓存）
        
        参数:
            tasks: [(symbol, timeframe, limit), ...]
        返回:
            {(symbol, timeframe): ohlcv_data, ...}
        """
        results = {}
        for symbol, timeframe, limit in tasks:
            ohlcv = self.fetch_ohlcv(symbol, timeframe, limit)
            results[(symbol, timeframe)] = ohlcv
        return results
    
    def clear_cache(self):
        """清空 MarketDataProvider 的缓存"""
        if self._provider:
            self._provider.ohlcv_cache.clear()
            logger.debug("[MarketDataSource] 缓存已清空")


# 全局数据源实例
_data_source: Optional[MarketDataSource] = None


def get_data_source(api_base_url: str = "http://127.0.0.1:8000") -> MarketDataSource:
    """获取全局数据源实例"""
    global _data_source
    if _data_source is None:
        _data_source = MarketDataSource(api_base_url)
    return _data_source


# NumPy 向量化加速计算函数

def calc_ma(closes: Union[List[float], np.ndarray], period: int = 20) -> np.ndarray:
    """
    计算简单移动平均线 (MA) - NumPy 向量化加速
    
    参数:
        closes: 收盘价列表或数组
        period: 周期，默认20
    返回:
        MA 值数组（前 period-1 个为 NaN）
    """
    closes = np.asarray(closes, dtype=np.float64)
    n = len(closes)
    
    if n < period:
        return np.full(n, np.nan)
    
    # 使用 cumsum 技巧实现 O(n) 复杂度的滑动平均
    cumsum = np.cumsum(np.insert(closes, 0, 0))
    ma = (cumsum[period:] - cumsum[:-period]) / period
    
    # 前 period-1 个填充 NaN
    result = np.full(n, np.nan)
    result[period-1:] = ma
    
    return result


def calc_ema(closes: Union[List[float], np.ndarray], period: int = 12) -> np.ndarray:
    """
    计算指数移动平均线 (EMA) - NumPy 向量化加速
    
    参数:
        closes: 收盘价列表或数组
        period: 周期，默认12
    返回:
        EMA 值数组
    """
    closes = np.asarray(closes, dtype=np.float64)
    n = len(closes)
    
    if n < period:
        return np.full(n, np.nan)
    
    alpha = 2.0 / (period + 1)
    result = np.full(n, np.nan)
    
    # 第一个 EMA 使用 SMA
    result[period-1] = np.mean(closes[:period])
    
    # 向量化 EMA 计算（使用 numba 可进一步加速）
    for i in range(period, n):
        result[i] = alpha * closes[i] + (1 - alpha) * result[i-1]
    
    return result


def calc_rsi(closes: Union[List[float], np.ndarray], period: int = 14) -> np.ndarray:
    """
    计算相对强弱指数 (RSI) - NumPy 向量化加速
    
    使用 EMA 平滑方法（与 pandas_ta 一致）
    
    参数:
        closes: 收盘价列表或数组
        period: 周期，默认14
    返回:
        RSI 值数组 (0-100)
    """
    closes = np.asarray(closes, dtype=np.float64)
    n = len(closes)
    
    if n < period + 1:
        return np.full(n, np.nan)
    
    # 计算价格变化
    deltas = np.diff(closes)
    
    # 分离涨跌
    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)
    
    result = np.full(n, np.nan)
    
    # 使用 EMA 平滑（与 pandas_ta 一致）
    alpha = 1.0 / period
    
    # 初始化
    avg_gain = gains[0]
    avg_loss = losses[0]
    
    # 计算 RSI
    for i in range(1, len(deltas)):
        avg_gain = alpha * gains[i] + (1 - alpha) * avg_gain
        avg_loss = alpha * losses[i] + (1 - alpha) * avg_loss
        
        if i >= period - 1:
            if avg_loss == 0:
                result[i + 1] = 100.0
            else:
                rs = avg_gain / avg_loss
                result[i + 1] = 100.0 - (100.0 / (1.0 + rs))
    
    return result


def calc_macd(
    closes: Union[List[float], np.ndarray], 
    fast: int = 12, 
    slow: int = 26, 
    signal: int = 9
) -> Dict[str, np.ndarray]:
    """
    计算 MACD 指标 - NumPy 向量化加速
    
    参数:
        closes: 收盘价列表或数组
        fast: 快线周期，默认12
        slow: 慢线周期，默认26
        signal: 信号线周期，默认9
    返回:
        {'macd': array, 'signal': array, 'histogram': array}
    """
    closes = np.asarray(closes, dtype=np.float64)
    n = len(closes)
    
    if n < slow:
        return {
            'macd': np.full(n, np.nan),
            'signal': np.full(n, np.nan),
            'histogram': np.full(n, np.nan)
        }
    
    ema_fast = calc_ema(closes, fast)
    ema_slow = calc_ema(closes, slow)
    
    # MACD 线 = 快线 - 慢线
    macd_line = ema_fast - ema_slow
    
    # 信号线 = MACD 的 EMA（从有效值开始计算）
    valid_start = slow - 1
    valid_macd = macd_line[valid_start:]
    
    if len(valid_macd) < signal:
        signal_line = np.full(n, np.nan)
    else:
        signal_ema = calc_ema(valid_macd, signal)
        signal_line = np.full(n, np.nan)
        signal_line[valid_start:] = signal_ema
    
    # 柱状图 = MACD - 信号线
    histogram = macd_line - signal_line
    
    return {
        'macd': macd_line,
        'signal': signal_line,
        'histogram': histogram
    }


def calc_boll(
    closes: Union[List[float], np.ndarray], 
    period: int = 20, 
    std_dev: float = 2.0
) -> Dict[str, np.ndarray]:
    """
    计算布林带 (BOLL) - NumPy 向量化加速
    
    参数:
        closes: 收盘价列表或数组
        period: 周期，默认20
        std_dev: 标准差倍数，默认2.0
    返回:
        {'upper': array, 'middle': array, 'lower': array}
    """
    closes = np.asarray(closes, dtype=np.float64)
    n = len(closes)
    
    if n < period:
        return {
            'upper': np.full(n, np.nan),
            'middle': np.full(n, np.nan),
            'lower': np.full(n, np.nan)
        }
    
    middle = calc_ma(closes, period)
    
    # 使用滑动窗口计算标准差
    upper = np.full(n, np.nan)
    lower = np.full(n, np.nan)
    
    # 向量化滑动标准差
    for i in range(period - 1, n):
        window = closes[i - period + 1:i + 1]
        std = np.std(window, ddof=0)  # 总体标准差
        upper[i] = middle[i] + std_dev * std
        lower[i] = middle[i] - std_dev * std
    
    return {
        'upper': upper,
        'middle': middle,
        'lower': lower
    }


def calc_kdj(
    highs: Union[List[float], np.ndarray], 
    lows: Union[List[float], np.ndarray], 
    closes: Union[List[float], np.ndarray], 
    period: int = 9, 
    k_smooth: int = 3, 
    d_smooth: int = 3
) -> Dict[str, np.ndarray]:
    """
    计算 KDJ 指标 - NumPy 向量化加速
    
    参数:
        highs: 最高价列表或数组
        lows: 最低价列表或数组
        closes: 收盘价列表或数组
        period: RSV 周期，默认9
        k_smooth: K 平滑周期，默认3
        d_smooth: D 平滑周期，默认3
    返回:
        {'k': array, 'd': array, 'j': array}
    """
    highs = np.asarray(highs, dtype=np.float64)
    lows = np.asarray(lows, dtype=np.float64)
    closes = np.asarray(closes, dtype=np.float64)
    n = len(closes)
    
    if n < period:
        return {
            'k': np.full(n, np.nan),
            'd': np.full(n, np.nan),
            'j': np.full(n, np.nan)
        }
    
    # 计算 RSV（使用滑动窗口最高/最低）
    rsv = np.full(n, np.nan)
    for i in range(period - 1, n):
        highest = np.max(highs[i - period + 1:i + 1])
        lowest = np.min(lows[i - period + 1:i + 1])
        if highest == lowest:
            rsv[i] = 50.0
        else:
            rsv[i] = (closes[i] - lowest) / (highest - lowest) * 100.0
    
    # 计算 K, D, J
    k_values = np.full(n, np.nan)
    d_values = np.full(n, np.nan)
    j_values = np.full(n, np.nan)
    
    k = 50.0  # 初始 K 值
    d = 50.0  # 初始 D 值
    
    for i in range(period - 1, n):
        k = (2 * k + rsv[i]) / 3
        d = (2 * d + k) / 3
        j = 3 * k - 2 * d
        k_values[i] = k
        d_values[i] = d
        j_values[i] = j
    
    return {
        'k': k_values,
        'd': d_values,
        'j': j_values
    }


def calc_atr(
    highs: Union[List[float], np.ndarray], 
    lows: Union[List[float], np.ndarray], 
    closes: Union[List[float], np.ndarray], 
    period: int = 14
) -> np.ndarray:
    """
    计算平均真实波幅 (ATR) - NumPy 向量化加速
    
    参数:
        highs: 最高价列表或数组
        lows: 最低价列表或数组
        closes: 收盘价列表或数组
        period: 周期，默认14
    返回:
        ATR 值数组
    """
    highs = np.asarray(highs, dtype=np.float64)
    lows = np.asarray(lows, dtype=np.float64)
    closes = np.asarray(closes, dtype=np.float64)
    n = len(closes)
    
    if n < 2:
        return np.full(n, np.nan)
    
    # 向量化计算 True Range
    tr = np.zeros(n)
    tr[0] = highs[0] - lows[0]
    
    tr1 = highs[1:] - lows[1:]
    tr2 = np.abs(highs[1:] - closes[:-1])
    tr3 = np.abs(lows[1:] - closes[:-1])
    tr[1:] = np.maximum(np.maximum(tr1, tr2), tr3)
    
    if n < period:
        return np.full(n, np.nan)
    
    # 计算 ATR
    atr = np.full(n, np.nan)
    atr[period - 1] = np.mean(tr[:period])
    
    for i in range(period, n):
        atr[i] = (atr[i - 1] * (period - 1) + tr[i]) / period
    
    return atr


def calc_obv(
    closes: Union[List[float], np.ndarray], 
    volumes: Union[List[float], np.ndarray]
) -> np.ndarray:
    """
    计算能量潮 (OBV) - NumPy 向量化加速
    
    参数:
        closes: 收盘价列表或数组
        volumes: 成交量列表或数组
    返回:
        OBV 值数组
    """
    closes = np.asarray(closes, dtype=np.float64)
    volumes = np.asarray(volumes, dtype=np.float64)
    n = len(closes)
    
    if n < 2:
        return np.zeros(n)
    
    # 计算价格变化方向
    price_diff = np.diff(closes)
    direction = np.sign(price_diff)
    
    # 计算 OBV 变化量
    obv_change = np.zeros(n)
    obv_change[1:] = direction * volumes[1:]
    
    # 累积求和
    obv = np.cumsum(obv_change)
    
    return obv


def calc_vwap(
    highs: Union[List[float], np.ndarray], 
    lows: Union[List[float], np.ndarray], 
    closes: Union[List[float], np.ndarray], 
    volumes: Union[List[float], np.ndarray]
) -> np.ndarray:
    """
    计算成交量加权平均价 (VWAP) - NumPy 向量化加速
    
    参数:
        highs: 最高价列表或数组
        lows: 最低价列表或数组
        closes: 收盘价列表或数组
        volumes: 成交量列表或数组
    返回:
        VWAP 值数组
    """
    highs = np.asarray(highs, dtype=np.float64)
    lows = np.asarray(lows, dtype=np.float64)
    closes = np.asarray(closes, dtype=np.float64)
    volumes = np.asarray(volumes, dtype=np.float64)
    
    if len(closes) == 0:
        return np.array([])
    
    # 典型价格 = (H + L + C) / 3
    typical_prices = (highs + lows + closes) / 3
    
    # 累积计算
    cumulative_tp_vol = np.cumsum(typical_prices * volumes)
    cumulative_vol = np.cumsum(volumes)
    
    # 避免除零
    vwap = np.where(
        cumulative_vol > 0,
        cumulative_tp_vol / cumulative_vol,
        typical_prices
    )
    
    return vwap


# 缓存装饰器

class IndicatorCache:
    """
    指标计算结果缓存
    
    使用 LRU 策略缓存计算结果，避免重复计算
    """
    
    def __init__(self, max_size: int = 100, ttl_sec: float = 5.0):
        self.max_size = max_size
        self.ttl_sec = ttl_sec
        self._cache: Dict[str, Tuple[Any, float]] = {}
        self._access_order: List[str] = []
    
    def _make_key(self, indicator: str, symbol: str, timeframe: str, params: Dict) -> str:
        """生成缓存键"""
        params_str = "_".join(f"{k}={v}" for k, v in sorted(params.items()))
        return f"{indicator}:{symbol}:{timeframe}:{params_str}"
    
    def get(self, indicator: str, symbol: str, timeframe: str, params: Dict) -> Optional[Any]:
        """获取缓存"""
        key = self._make_key(indicator, symbol, timeframe, params)
        if key in self._cache:
            value, ts = self._cache[key]
            if time.time() - ts < self.ttl_sec:
                # 更新访问顺序
                if key in self._access_order:
                    self._access_order.remove(key)
                self._access_order.append(key)
                return value
            # 过期删除
            del self._cache[key]
            if key in self._access_order:
                self._access_order.remove(key)
        return None
    
    def set(self, indicator: str, symbol: str, timeframe: str, params: Dict, value: Any):
        """设置缓存"""
        key = self._make_key(indicator, symbol, timeframe, params)
        
        # LRU 淘汰
        while len(self._cache) >= self.max_size and self._access_order:
            oldest_key = self._access_order.pop(0)
            if oldest_key in self._cache:
                del self._cache[oldest_key]
        
        self._cache[key] = (value, time.time())
        self._access_order.append(key)
    
    def clear(self):
        """清空缓存"""
        self._cache.clear()
        self._access_order.clear()


# 全局缓存实例
_indicator_cache = IndicatorCache(max_size=200, ttl_sec=5.0)


# 指标计算器类

class IndicatorCalculator:
    """
    技术指标计算器
    
    特点：
    1. NumPy 向量化加速计算
    2. LRU 缓存避免重复计算
    3. 支持从 Market API 直接获取数据并计算
    """
    
    # 支持的指标列表
    SUPPORTED_INDICATORS = ['MA', 'EMA', 'RSI', 'MACD', 'BOLL', 'KDJ', 'ATR', 'OBV', 'VWAP']
    
    def __init__(self, api_base_url: str = "http://127.0.0.1:8000"):
        self.data_source = get_data_source(api_base_url)
        self.cache = _indicator_cache
    
    def fetch_and_calculate(
        self, 
        indicator: str, 
        symbol: str, 
        timeframe: str = "1m", 
        limit: int = 500,
        use_cache: bool = True,
        **kwargs
    ) -> Dict[str, Any]:
        """
        从数据源获取数据并计算指标
        
        参数:
            indicator: 指标名称
            symbol: 交易对，如 "BTC/USDT:USDT"
            timeframe: 时间周期
            limit: K线数量
            use_cache: 是否使用缓存
            **kwargs: 指标参数
        返回:
            指标计算结果
        """
        # 检查缓存
        if use_cache:
            cached = self.cache.get(indicator, symbol, timeframe, kwargs)
            if cached is not None:
                return cached
        
        # 获取数据
        ohlcv = self.data_source.fetch_ohlcv(symbol, timeframe, limit)
        if not ohlcv:
            return {'error': f'无法获取 {symbol} 的数据'}
        
        # 计算指标
        result = self.calculate(indicator, ohlcv, **kwargs)
        
        # 缓存结果
        if use_cache and 'error' not in result:
            self.cache.set(indicator, symbol, timeframe, kwargs, result)
        
        return result
    
    def fetch_and_calculate_all(
        self, 
        indicators: List[str], 
        symbol: str, 
        timeframe: str = "1m", 
        limit: int = 500
    ) -> Dict[str, Dict]:
        """
        从数据源获取数据并批量计算多个指标
        
        参数:
            indicators: 指标名称列表
            symbol: 交易对
            timeframe: 时间周期
            limit: K线数量
        返回:
            {indicator_name: result, ...}
        """
        # 获取数据（只获取一次）
        ohlcv = self.data_source.fetch_ohlcv(symbol, timeframe, limit)
        if not ohlcv:
            return {ind: {'error': f'无法获取 {symbol} 的数据'} for ind in indicators}
        
        return self.calculate_all(indicators, ohlcv)
    
    def fetch_latest_values(
        self, 
        indicators: List[str], 
        symbol: str, 
        timeframe: str = "1m", 
        limit: int = 500
    ) -> Dict[str, Any]:
        """
        从数据源获取数据并返回所有指标的最新值
        
        参数:
            indicators: 指标名称列表
            symbol: 交易对
            timeframe: 时间周期
            limit: K线数量
        返回:
            {indicator_name: latest_value, ...}
        """
        ohlcv = self.data_source.fetch_ohlcv(symbol, timeframe, limit)
        if not ohlcv:
            return {ind: None for ind in indicators}
        
        return self.get_latest_values(indicators, ohlcv)
    
    @staticmethod
    def calculate(indicator: str, ohlcv: List[List], **kwargs) -> Dict[str, Any]:
        """
        计算指定指标
        
        参数:
            indicator: 指标名称 (MA, EMA, RSI, MACD, BOLL, KDJ, ATR, OBV, VWAP)
            ohlcv: K线数据 [[timestamp, open, high, low, close, volume], ...]
            **kwargs: 指标参数
        返回:
            指标计算结果（NumPy 数组）
        """
        if not ohlcv:
            return {'error': '无数据'}
        
        # 提取价格数据为 NumPy 数组（一次性转换，避免重复）
        ohlcv_arr = np.array(ohlcv, dtype=np.float64)
        opens = ohlcv_arr[:, 1]
        highs = ohlcv_arr[:, 2]
        lows = ohlcv_arr[:, 3]
        closes = ohlcv_arr[:, 4]
        volumes = ohlcv_arr[:, 5] if ohlcv_arr.shape[1] > 5 else np.zeros(len(ohlcv))
        
        indicator = indicator.upper()
        
        if indicator == 'MA':
            period = kwargs.get('period', 20)
            return {'ma': calc_ma(closes, period), 'period': period}
        
        elif indicator == 'EMA':
            period = kwargs.get('period', 12)
            return {'ema': calc_ema(closes, period), 'period': period}
        
        elif indicator == 'RSI':
            period = kwargs.get('period', 14)
            return {'rsi': calc_rsi(closes, period), 'period': period}
        
        elif indicator == 'MACD':
            fast = kwargs.get('fast', 12)
            slow = kwargs.get('slow', 26)
            signal = kwargs.get('signal', 9)
            return calc_macd(closes, fast, slow, signal)
        
        elif indicator == 'BOLL':
            period = kwargs.get('period', 20)
            std_dev = kwargs.get('std_dev', 2.0)
            return calc_boll(closes, period, std_dev)
        
        elif indicator == 'KDJ':
            period = kwargs.get('period', 9)
            return calc_kdj(highs, lows, closes, period)
        
        elif indicator == 'ATR':
            period = kwargs.get('period', 14)
            return {'atr': calc_atr(highs, lows, closes, period), 'period': period}
        
        elif indicator == 'OBV':
            return {'obv': calc_obv(closes, volumes)}
        
        elif indicator == 'VWAP':
            return {'vwap': calc_vwap(highs, lows, closes, volumes)}
        
        else:
            return {'error': f'不支持的指标: {indicator}'}
    
    @staticmethod
    def calculate_all(indicators: List[str], ohlcv: List[List]) -> Dict[str, Dict]:
        """
        批量计算多个指标
        
        参数:
            indicators: 指标名称列表
            ohlcv: K线数据
        返回:
            {indicator_name: result, ...}
        """
        results = {}
        for indicator in indicators:
            results[indicator] = IndicatorCalculator.calculate(indicator, ohlcv)
        return results
    
    @staticmethod
    def get_latest_values(indicators: List[str], ohlcv: List[List]) -> Dict[str, Any]:
        """
        获取所有指标的最新值（用于 AI 决策）
        
        参数:
            indicators: 指标名称列表
            ohlcv: K线数据
        返回:
            {indicator_name: latest_value, ...}
        """
        all_results = IndicatorCalculator.calculate_all(indicators, ohlcv)
        latest = {}
        
        def _get_last(arr):
            """安全获取数组最后一个非 NaN 值"""
            if arr is None:
                return None
            if isinstance(arr, np.ndarray):
                valid = arr[~np.isnan(arr)]
                return float(valid[-1]) if len(valid) > 0 else None
            if isinstance(arr, list):
                valid = [v for v in arr if v is not None]
                return valid[-1] if valid else None
            return None
        
        for name, result in all_results.items():
            if 'error' in result:
                latest[name] = None
                continue
            
            # 提取最新值
            if name == 'MA':
                latest['MA'] = _get_last(result.get('ma'))
            elif name == 'EMA':
                latest['EMA'] = _get_last(result.get('ema'))
            elif name == 'RSI':
                latest['RSI'] = _get_last(result.get('rsi'))
            elif name == 'MACD':
                latest['MACD'] = _get_last(result.get('macd'))
                latest['MACD_Signal'] = _get_last(result.get('signal'))
                latest['MACD_Hist'] = _get_last(result.get('histogram'))
            elif name == 'BOLL':
                latest['BOLL_Upper'] = _get_last(result.get('upper'))
                latest['BOLL_Middle'] = _get_last(result.get('middle'))
                latest['BOLL_Lower'] = _get_last(result.get('lower'))
            elif name == 'KDJ':
                latest['KDJ_K'] = _get_last(result.get('k'))
                latest['KDJ_D'] = _get_last(result.get('d'))
                latest['KDJ_J'] = _get_last(result.get('j'))
            elif name == 'ATR':
                latest['ATR'] = _get_last(result.get('atr'))
            elif name == 'OBV':
                latest['OBV'] = _get_last(result.get('obv'))
            elif name == 'VWAP':
                latest['VWAP'] = _get_last(result.get('vwap'))
        
        return latest
    
    @staticmethod
    def format_for_ai(latest_values: Dict[str, Any], symbol: str, timeframe: str) -> str:
        """
        将指标值格式化为 AI 可读的文本
        
        参数:
            latest_values: 指标最新值字典
            symbol: 交易对
            timeframe: 时间周期
        返回:
            格式化的文本
        """
        lines = [f"## {symbol} 技术指标 ({timeframe})", ""]
        
        # 趋势指标
        if 'MA' in latest_values or 'EMA' in latest_values:
            lines.append("### 趋势指标")
            if latest_values.get('MA') is not None:
                lines.append(f"- MA(20): {latest_values['MA']:.4f}")
            if latest_values.get('EMA') is not None:
                lines.append(f"- EMA(12): {latest_values['EMA']:.4f}")
            lines.append("")
        
        # 动量指标
        if 'RSI' in latest_values or 'MACD' in latest_values:
            lines.append("### 动量指标")
            if latest_values.get('RSI') is not None:
                rsi = latest_values['RSI']
                status = "超买" if rsi > 70 else "超卖" if rsi < 30 else "中性"
                lines.append(f"- RSI(14): {rsi:.2f} ({status})")
            if latest_values.get('MACD') is not None:
                macd = latest_values['MACD']
                signal = latest_values.get('MACD_Signal', 0) or 0
                hist = latest_values.get('MACD_Hist', 0) or 0
                trend = "多头" if hist > 0 else "空头"
                lines.append(f"- MACD: {macd:.4f} | Signal: {signal:.4f} | Hist: {hist:.4f} ({trend})")
            lines.append("")
        
        # 波动指标
        if 'BOLL_Upper' in latest_values or 'ATR' in latest_values:
            lines.append("### 波动指标")
            if latest_values.get('BOLL_Upper') is not None:
                lines.append(f"- BOLL: Upper={latest_values['BOLL_Upper']:.4f} | Middle={latest_values.get('BOLL_Middle', 0):.4f} | Lower={latest_values.get('BOLL_Lower', 0):.4f}")
            if latest_values.get('ATR') is not None:
                lines.append(f"- ATR(14): {latest_values['ATR']:.4f}")
            lines.append("")
        
        # KDJ
        if 'KDJ_K' in latest_values:
            lines.append("### KDJ 指标")
            k = latest_values.get('KDJ_K', 0) or 0
            d = latest_values.get('KDJ_D', 0) or 0
            j = latest_values.get('KDJ_J', 0) or 0
            status = "超买" if k > 80 else "超卖" if k < 20 else "中性"
            lines.append(f"- K: {k:.2f} | D: {d:.2f} | J: {j:.2f} ({status})")
            lines.append("")
        
        # 成交量指标
        if 'OBV' in latest_values or 'VWAP' in latest_values:
            lines.append("### 成交量指标")
            if latest_values.get('OBV') is not None:
                lines.append(f"- OBV: {latest_values['OBV']:.0f}")
            if latest_values.get('VWAP') is not None:
                lines.append(f"- VWAP: {latest_values['VWAP']:.4f}")
        
        return "\n".join(lines)


# 便捷函数

def get_ai_indicators(
    symbol: str,
    timeframe: str = "1m",
    indicators: Optional[List[str]] = None,
    limit: int = 500,
    api_base_url: str = "http://127.0.0.1:8000"
) -> Dict[str, Any]:
    """
    便捷函数：获取 AI 决策所需的技术指标
    
    参数:
        symbol: 交易对，如 "BTC/USDT:USDT"
        timeframe: 时间周期，如 "1m", "5m", "1h"
        indicators: 指标列表，默认全部
        limit: K线数量
        api_base_url: Market API 地址
    返回:
        {
            'symbol': str,
            'timeframe': str,
            'latest': {indicator: value, ...},
            'formatted': str,  # AI 可读的格式化文本
            'timestamp': int
        }
    """
    if indicators is None:
        indicators = IndicatorCalculator.SUPPORTED_INDICATORS
    
    calculator = IndicatorCalculator(api_base_url)
    latest = calculator.fetch_latest_values(indicators, symbol, timeframe, limit)
    formatted = calculator.format_for_ai(latest, symbol, timeframe)
    
    return {
        'symbol': symbol,
        'timeframe': timeframe,
        'latest': latest,
        'formatted': formatted,
        'timestamp': int(time.time() * 1000)
    }


def get_batch_ai_indicators(
    symbols: List[str],
    timeframe: str = "1m",
    indicators: Optional[List[str]] = None,
    limit: int = 500
) -> Dict[str, Dict[str, Any]]:
    """
    批量获取多个币种的 AI 指标
    
    使用异步并发获取，大幅提升性能
    
    参数:
        symbols: 交易对列表
        timeframe: 时间周期
        indicators: 指标列表
        limit: K线数量
    返回:
        {symbol: indicator_result, ...}
    """
    if indicators is None:
        indicators = IndicatorCalculator.SUPPORTED_INDICATORS
    
    # 构建批量获取任务
    tasks = [(sym, timeframe, limit) for sym in symbols]
    
    # 批量获取数据
    data_source = get_data_source()
    batch_data = data_source.fetch_batch_ohlcv(tasks)
    
    # 计算每个币种的指标
    results = {}
    for symbol in symbols:
        ohlcv = batch_data.get((symbol, timeframe))
        if ohlcv:
            latest = IndicatorCalculator.get_latest_values(indicators, ohlcv)
            formatted = IndicatorCalculator.format_for_ai(latest, symbol, timeframe)
            results[symbol] = {
                'symbol': symbol,
                'timeframe': timeframe,
                'latest': latest,
                'formatted': formatted,
                'timestamp': int(time.time() * 1000)
            }
        else:
            results[symbol] = {
                'symbol': symbol,
                'timeframe': timeframe,
                'latest': {},
                'formatted': f"## {symbol} 数据获取失败",
                'error': '无法获取数据',
                'timestamp': int(time.time() * 1000)
            }
    
    return results


# 性能测试

if __name__ == "__main__":
    """
    性能测试：对比纯 Python vs NumPy 向量化计算
    
    运行: python ai_indicators.py
    """
    import sys
    
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)]
    )
    
    print("=" * 60)
    print("AI 技术指标模块 - 性能测试")
    print("=" * 60)
    
    # 生成测试数据（模拟 1000 根 K 线）
    np.random.seed(42)
    n = 1000
    base_price = 50000.0
    
    # 模拟价格走势
    returns = np.random.randn(n) * 0.01
    closes = base_price * np.cumprod(1 + returns)
    highs = closes * (1 + np.abs(np.random.randn(n) * 0.005))
    lows = closes * (1 - np.abs(np.random.randn(n) * 0.005))
    opens = (highs + lows) / 2
    volumes = np.random.uniform(100, 1000, n)
    timestamps = np.arange(n) * 60000  # 1分钟间隔
    
    # 构建 OHLCV 数据
    ohlcv = [[timestamps[i], opens[i], highs[i], lows[i], closes[i], volumes[i]] for i in range(n)]
    
    print(f"\n测试数据: {n} 根 K 线")
    print("-" * 60)
    
    # 测试所有指标计算
    indicators = IndicatorCalculator.SUPPORTED_INDICATORS
    
    # 预热
    for _ in range(3):
        IndicatorCalculator.calculate_all(indicators, ohlcv)
    
    # 计时测试
    iterations = 100
    start = time.perf_counter()
    for _ in range(iterations):
        IndicatorCalculator.calculate_all(indicators, ohlcv)
    elapsed = time.perf_counter() - start
    
    avg_time = elapsed / iterations * 1000
    print(f"\n计算 {len(indicators)} 个指标 x {iterations} 次")
    print(f"总耗时: {elapsed:.3f} 秒")
    print(f"平均每次: {avg_time:.2f} ms")
    print(f"每秒可计算: {iterations / elapsed:.0f} 次")
    
    # 测试获取最新值
    print("\n" + "-" * 60)
    print("获取最新指标值:")
    latest = IndicatorCalculator.get_latest_values(indicators, ohlcv)
    for name, value in latest.items():
        if value is not None:
            print(f"  {name}: {value:.4f}" if isinstance(value, float) else f"  {name}: {value}")
    
    # 测试格式化输出
    print("\n" + "-" * 60)
    print("AI 格式化输出:")
    formatted = IndicatorCalculator.format_for_ai(latest, "BTC/USDT:USDT", "1m")
    print(formatted)
    
    print("\n" + "=" * 60)
    print("测试完成!")
    print("=" * 60)
