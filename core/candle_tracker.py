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
# candle_tracker.py
# K线收线追踪器 - 确保信号只基于已收线K线

import logging
from typing import Dict, List, Tuple, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class CandleClosureTracker:
    """
    K线收线追踪器
    
    功能:
    1. 判断K线是否已收线
    2. 筛选已收线K线
    3. 追踪最后收线时间戳，避免重复信号
    """
    
    # 时间周期到毫秒的映射
    TIMEFRAME_MS: Dict[str, int] = {
        '1m': 60 * 1000,
        '3m': 3 * 60 * 1000,
        '5m': 5 * 60 * 1000,
        '15m': 15 * 60 * 1000,
        '30m': 30 * 60 * 1000,
        '1h': 60 * 60 * 1000,
        '2h': 2 * 60 * 60 * 1000,
        '4h': 4 * 60 * 60 * 1000,
        '6h': 6 * 60 * 60 * 1000,
        '12h': 12 * 60 * 60 * 1000,
        '1d': 24 * 60 * 60 * 1000,      # 使用 UTC 边界
        '1D': 24 * 60 * 60 * 1000,      # 别名
        '1Dutc': 24 * 60 * 60 * 1000,   # 显式 UTC 边界（与 TradingView 对齐）
        '1w': 7 * 24 * 60 * 60 * 1000,
        '1W': 7 * 24 * 60 * 60 * 1000,
    }
    
    # OKX 日线周期映射（确保使用 UTC 边界）
    OKX_DAILY_TIMEFRAME = '1Dutc'
    
    def __init__(self):
        """初始化追踪器"""
        # {(symbol, timeframe): last_closed_candle_ts}
        self._last_closed: Dict[Tuple[str, str], int] = {}
    
    def get_timeframe_ms(self, timeframe: str) -> int:
        """
        获取时间周期的毫秒数
        
        Args:
            timeframe: 时间周期字符串
        
        Returns:
            毫秒数
        """
        return self.TIMEFRAME_MS.get(timeframe, 60 * 1000)
    
    def normalize_timeframe(self, timeframe: str) -> str:
        """
        规范化时间周期
        
        对于日线，统一使用 UTC 边界
        
        Args:
            timeframe: 原始时间周期
        
        Returns:
            规范化后的时间周期
        """
        if timeframe in ('1d', '1D'):
            return self.OKX_DAILY_TIMEFRAME
        return timeframe
    
    def is_candle_closed(
        self,
        candle_ts: int,
        timeframe: str,
        server_time: int
    ) -> bool:
        """
        判断K线是否已收线
        
        K线收线条件: server_time >= candle_ts + timeframe_duration
        
        Args:
            candle_ts: K线开始时间戳 (UTC ms)
            timeframe: 时间周期
            server_time: 服务器当前时间 (UTC ms)
        
        Returns:
            True 如果K线已收线
        """
        duration_ms = self.get_timeframe_ms(timeframe)
        candle_close_time = candle_ts + duration_ms
        return server_time >= candle_close_time
    
    def get_closed_candles(
        self,
        ohlcv: List[List],
        timeframe: str,
        server_time: int
    ) -> List[List]:
        """
        从 OHLCV 数据中筛选已收线K线
        
        Args:
            ohlcv: OHLCV 数据列表 [[ts, o, h, l, c, v], ...]
            timeframe: 时间周期
            server_time: 服务器当前时间 (UTC ms)
        
        Returns:
            只包含已收线K线的列表
        """
        if not ohlcv:
            return []
        
        closed = []
        for candle in ohlcv:
            candle_ts = candle[0]
            if self.is_candle_closed(candle_ts, timeframe, server_time):
                closed.append(candle)
        
        return closed
    
    def get_latest_closed_candle(
        self,
        ohlcv: List[List],
        timeframe: str,
        server_time: int
    ) -> Optional[List]:
        """
        获取最新的已收线K线
        
        Args:
            ohlcv: OHLCV 数据列表
            timeframe: 时间周期
            server_time: 服务器当前时间 (UTC ms)
        
        Returns:
            最新的已收线K线，或 None
        """
        closed = self.get_closed_candles(ohlcv, timeframe, server_time)
        if closed:
            return closed[-1]
        return None
    
    def has_new_closed_candle(
        self,
        symbol: str,
        timeframe: str,
        latest_closed_ts: int
    ) -> bool:
        """
        检查是否有新的收线K线
        
        Args:
            symbol: 交易对
            timeframe: 时间周期
            latest_closed_ts: 最新收线K线的时间戳
        
        Returns:
            True 如果 latest_closed_ts > last_closed_ts
        """
        key = (symbol, timeframe)
        last_ts = self._last_closed.get(key, 0)
        return latest_closed_ts > last_ts
    
    def update_last_closed(
        self,
        symbol: str,
        timeframe: str,
        closed_ts: int
    ) -> None:
        """
        更新最后收线时间戳
        
        Args:
            symbol: 交易对
            timeframe: 时间周期
            closed_ts: 收线K线的时间戳
        """
        key = (symbol, timeframe)
        self._last_closed[key] = closed_ts
        logger.debug(f"Updated last_closed for {symbol}/{timeframe}: {closed_ts}")
    
    def get_last_closed_ts(
        self,
        symbol: str,
        timeframe: str
    ) -> int:
        """
        获取最后收线时间戳
        
        Args:
            symbol: 交易对
            timeframe: 时间周期
        
        Returns:
            最后收线时间戳，如果没有记录则返回 0
        """
        key = (symbol, timeframe)
        return self._last_closed.get(key, 0)
    
    def should_calculate_signal(
        self,
        symbol: str,
        timeframe: str,
        ohlcv: List[List],
        server_time: int
    ) -> Tuple[bool, Optional[List], str]:
        """
        判断是否应该计算信号
        
        综合判断：
        1. 是否有已收线K线
        2. 是否有新的收线K线（避免重复计算）
        
        Args:
            symbol: 交易对
            timeframe: 时间周期
            ohlcv: OHLCV 数据
            server_time: 服务器时间
        
        Returns:
            (should_calculate, latest_closed_candle, reason)
        """
        # 获取已收线K线
        closed_candles = self.get_closed_candles(ohlcv, timeframe, server_time)
        
        if not closed_candles:
            return False, None, "no_closed_candles"
        
        latest_closed = closed_candles[-1]
        latest_closed_ts = latest_closed[0]
        
        # 检查是否有新的收线K线
        if not self.has_new_closed_candle(symbol, timeframe, latest_closed_ts):
            return False, latest_closed, "no_new_candle"
        
        return True, latest_closed, "new_candle"
    
    def clear(self, symbol: str = None, timeframe: str = None) -> None:
        """
        清除追踪记录
        
        Args:
            symbol: 指定交易对，None 表示全部
            timeframe: 指定时间周期，None 表示全部
        """
        if symbol is None and timeframe is None:
            self._last_closed.clear()
            logger.info("Cleared all candle tracking records")
        else:
            keys_to_remove = [
                k for k in self._last_closed
                if (symbol is None or k[0] == symbol) and
                   (timeframe is None or k[1] == timeframe)
            ]
            for k in keys_to_remove:
                del self._last_closed[k]
            logger.info(f"Cleared candle tracking for symbol={symbol}, timeframe={timeframe}")


class CandleSignalTracker:
    """
    K线信号追踪器
    
    功能:
    1. 追踪每根 K 线是否已触发过信号
    2. 防止同一根 K 线重复触发信号
    3. 在 59 秒扫描时使用当前未收盘的 K 线
    
    核心逻辑（59秒扫描场景）：
    - 系统在每分钟第 59 秒触发扫描
    - 此时使用当前未收盘的 K 线（即将在 00 秒收盘）来判断入场条件
    - 策略意图：在 K 线即将收盘时提前判断信号，实现更快的入场
    """
    
    # 时间周期到毫秒的映射
    TIMEFRAME_MS: Dict[str, int] = {
        '1m': 60 * 1000,
        '3m': 3 * 60 * 1000,
        '5m': 5 * 60 * 1000,
        '15m': 15 * 60 * 1000,
        '30m': 30 * 60 * 1000,
        '1h': 60 * 60 * 1000,
        '2h': 2 * 60 * 60 * 1000,
        '4h': 4 * 60 * 60 * 1000,
        '6h': 6 * 60 * 60 * 1000,
        '12h': 12 * 60 * 60 * 1000,
        '1d': 24 * 60 * 60 * 1000,
        '1D': 24 * 60 * 60 * 1000,
        '1Dutc': 24 * 60 * 60 * 1000,
        '1w': 7 * 24 * 60 * 60 * 1000,
        '1W': 7 * 24 * 60 * 60 * 1000,
    }
    
    # 保留最近 N 根 K 线的信号记录
    MAX_SIGNAL_HISTORY = 100
    
    def __init__(self):
        """初始化信号追踪器"""
        # {(symbol, timeframe, candle_open_ts): True}
        self._triggered_signals: Dict[Tuple[str, str, int], bool] = {}
    
    def get_timeframe_ms(self, timeframe: str) -> int:
        """获取时间周期的毫秒数"""
        return self.TIMEFRAME_MS.get(timeframe, 60 * 1000)
    
    def has_signal_triggered(
        self,
        symbol: str,
        timeframe: str,
        candle_open_ts: int
    ) -> bool:
        """
        检查该 K 线是否已触发过信号
        
        Args:
            symbol: 交易对
            timeframe: 时间周期
            candle_open_ts: K 线开盘时间戳 (UTC ms)
        
        Returns:
            True 如果该 K 线已触发过信号
        """
        key = (symbol, timeframe, candle_open_ts)
        return key in self._triggered_signals
    
    def record_signal(
        self,
        symbol: str,
        timeframe: str,
        candle_open_ts: int
    ) -> None:
        """
        记录信号触发
        
        Args:
            symbol: 交易对
            timeframe: 时间周期
            candle_open_ts: K 线开盘时间戳 (UTC ms)
        """
        key = (symbol, timeframe, candle_open_ts)
        self._triggered_signals[key] = True
        logger.debug(f"Recorded signal for {symbol}/{timeframe} at {candle_open_ts}")
        
        # 清理过期记录
        self._cleanup_old_signals()
    
    def get_current_candle_ts(
        self,
        candles: List[List],
        timeframe: str,
        current_time: int
    ) -> Optional[int]:
        """
        获取当前未收盘 K 线的开盘时间戳
        
        识别当前 K 线：candle_open_ts <= current_time < candle_close_time
        
        Args:
            candles: OHLCV 数据列表 [[ts, o, h, l, c, v], ...]
            timeframe: 时间周期
            current_time: 当前时间 (UTC ms)
        
        Returns:
            当前 K 线的开盘时间戳，如果没有找到则返回 None
        """
        if not candles:
            return None
        
        duration_ms = self.get_timeframe_ms(timeframe)
        
        for candle in reversed(candles):  # 从最新的开始查找
            candle_open_ts = candle[0]
            candle_close_time = candle_open_ts + duration_ms
            
            # 当前 K 线：candle_open_ts <= current_time < candle_close_time
            if candle_open_ts <= current_time < candle_close_time:
                return candle_open_ts
        
        # 如果没有找到，返回最新的 K 线
        return candles[-1][0] if candles else None
    
    def get_current_candle(
        self,
        candles: List[List],
        timeframe: str,
        current_time: int
    ) -> Optional[List]:
        """
        获取当前未收盘的 K 线
        
        Args:
            candles: OHLCV 数据列表
            timeframe: 时间周期
            current_time: 当前时间 (UTC ms)
        
        Returns:
            当前 K 线数据，如果没有找到则返回 None
        """
        if not candles:
            return None
        
        duration_ms = self.get_timeframe_ms(timeframe)
        
        for candle in reversed(candles):
            candle_open_ts = candle[0]
            candle_close_time = candle_open_ts + duration_ms
            
            if candle_open_ts <= current_time < candle_close_time:
                return candle
        
        # 如果没有找到，返回最新的 K 线
        return candles[-1] if candles else None
    
    def should_trigger_signal(
        self,
        symbol: str,
        timeframe: str,
        candles: List[List],
        current_time: int,
        signal_detected: bool
    ) -> Tuple[bool, Optional[int], str]:
        """
        判断是否应该触发信号
        
        综合判断：
        1. 是否检测到信号
        2. 该 K 线是否已触发过信号（防止重复）
        
        Args:
            symbol: 交易对
            timeframe: 时间周期
            candles: OHLCV 数据
            current_time: 当前时间 (UTC ms)
            signal_detected: 策略是否检测到信号
        
        Returns:
            (should_trigger, candle_open_ts, reason)
        """
        if not signal_detected:
            return False, None, "no_signal"
        
        # 获取当前 K 线
        current_candle_ts = self.get_current_candle_ts(candles, timeframe, current_time)
        
        if current_candle_ts is None:
            return False, None, "no_current_candle"
        
        # 检查是否已触发过
        if self.has_signal_triggered(symbol, timeframe, current_candle_ts):
            return False, current_candle_ts, "already_triggered"
        
        return True, current_candle_ts, "new_signal"
    
    def _cleanup_old_signals(self) -> None:
        """清理过期的信号记录"""
        if len(self._triggered_signals) > self.MAX_SIGNAL_HISTORY:
            # 按时间戳排序，删除最旧的记录
            sorted_keys = sorted(
                self._triggered_signals.keys(),
                key=lambda k: k[2]  # 按 candle_open_ts 排序
            )
            
            # 保留最新的 MAX_SIGNAL_HISTORY 条记录
            keys_to_remove = sorted_keys[:-self.MAX_SIGNAL_HISTORY]
            for key in keys_to_remove:
                del self._triggered_signals[key]
            
            logger.debug(f"Cleaned up {len(keys_to_remove)} old signal records")
    
    def clear(self, symbol: str = None, timeframe: str = None) -> None:
        """
        清除信号记录
        
        Args:
            symbol: 指定交易对，None 表示全部
            timeframe: 指定时间周期，None 表示全部
        """
        if symbol is None and timeframe is None:
            self._triggered_signals.clear()
            logger.info("Cleared all signal tracking records")
        else:
            keys_to_remove = [
                k for k in self._triggered_signals
                if (symbol is None or k[0] == symbol) and
                   (timeframe is None or k[1] == timeframe)
            ]
            for k in keys_to_remove:
                del self._triggered_signals[k]
            logger.info(f"Cleared signal tracking for symbol={symbol}, timeframe={timeframe}")
    
    def get_triggered_count(self) -> int:
        """获取已触发信号的数量"""
        return len(self._triggered_signals)


# 全局单例
_candle_tracker: Optional[CandleClosureTracker] = None
_signal_tracker: Optional[CandleSignalTracker] = None


def get_candle_tracker() -> CandleClosureTracker:
    """获取全局 CandleClosureTracker 实例"""
    global _candle_tracker
    if _candle_tracker is None:
        _candle_tracker = CandleClosureTracker()
    return _candle_tracker


def get_signal_tracker() -> CandleSignalTracker:
    """获取全局 CandleSignalTracker 实例"""
    global _signal_tracker
    if _signal_tracker is None:
        _signal_tracker = CandleSignalTracker()
    return _signal_tracker


def format_timestamp_beijing(ts_ms: int) -> str:
    """
    将 UTC 毫秒时间戳转换为北京时间字符串
    
    Args:
        ts_ms: UTC 毫秒时间戳
    
    Returns:
        北京时间字符串 (Asia/Shanghai)
    """
    from datetime import timezone, timedelta
    
    # UTC 时间
    utc_dt = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc)
    
    # 转换为北京时间 (UTC+8)
    beijing_tz = timezone(timedelta(hours=8))
    beijing_dt = utc_dt.astimezone(beijing_tz)
    
    return beijing_dt.strftime('%Y-%m-%d %H:%M:%S')
