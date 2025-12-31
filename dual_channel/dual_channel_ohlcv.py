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
# dual_channel_ohlcv.py
# 双通道K线数据容器 - 明确区分 forming_candle 和 last_closed_candle
# 核心设计：
# - forming_candle = candles[-1] (未收线K线，用于盘中执行信号)
# - last_closed_candle = candles[-2] (已收线K线，用于收线确认信号)

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Tuple
import time
import logging

logger = logging.getLogger(__name__)


class InsufficientDataError(Exception):
    """K线数据不足异常"""
    pass


@dataclass
class DualChannelOHLCV:
    """
    双通道K线数据容器
    
    明确区分：
    - forming_candle: 当前未收线K线 (candles[-1])
    - last_closed_candle: 最近已收线K线 (candles[-2])
    
    Attributes:
        symbol: 交易对，如 'BTC/USDT:USDT'
        timeframe: 时间周期，如 '1m', '5m', '1h'
        candles: 原始OHLCV数据 [[ts, o, h, l, c, v], ...]
        forming_candle: 未收线K线 (candles[-1])
        last_closed_candle: 已收线K线 (candles[-2])
        forming_ts: forming_candle 的时间戳 (UTC ms)
        closed_ts: last_closed_candle 的时间戳 (UTC ms)
        fetch_time: 数据获取时间 (UTC ms)
    """
    symbol: str
    timeframe: str
    candles: List[List]
    forming_candle: List
    last_closed_candle: List
    forming_ts: int
    closed_ts: int
    fetch_time: int
    
    @classmethod
    def from_candles(
        cls,
        symbol: str,
        timeframe: str,
        candles: List[List],
        fetch_time: Optional[int] = None
    ) -> 'DualChannelOHLCV':
        """
        从原始K线数据创建 DualChannelOHLCV 实例
        
        Args:
            symbol: 交易对
            timeframe: 时间周期
            candles: 原始OHLCV数据 [[ts, o, h, l, c, v], ...]
            fetch_time: 数据获取时间 (UTC ms)，默认为当前时间
        
        Returns:
            DualChannelOHLCV 实例
        
        Raises:
            InsufficientDataError: 当 candles 长度 < 2 时
        """
        if not candles or len(candles) < 2:
            raise InsufficientDataError(
                f"K线数据不足: 需要至少2根K线，实际 {len(candles) if candles else 0} 根"
            )
        
        # 提取 forming_candle 和 last_closed_candle
        forming_candle = candles[-1]
        last_closed_candle = candles[-2]
        
        # 提取时间戳
        forming_ts = forming_candle[0]
        closed_ts = last_closed_candle[0]
        
        # 验证时间戳格式（UTC毫秒）
        if not cls._is_valid_timestamp(forming_ts):
            logger.warning(f"forming_ts 格式异常: {forming_ts}")
        if not cls._is_valid_timestamp(closed_ts):
            logger.warning(f"closed_ts 格式异常: {closed_ts}")
        
        # 默认 fetch_time 为当前时间
        if fetch_time is None:
            fetch_time = int(time.time() * 1000)
        
        return cls(
            symbol=symbol,
            timeframe=timeframe,
            candles=candles,
            forming_candle=forming_candle,
            last_closed_candle=last_closed_candle,
            forming_ts=forming_ts,
            closed_ts=closed_ts,
            fetch_time=fetch_time
        )
    
    @staticmethod
    def _is_valid_timestamp(ts: int) -> bool:
        """
        验证时间戳是否为有效的UTC毫秒格式
        
        有效范围: 2001-09-09 到 2286-11-20 (1000000000000 到 9999999999999)
        """
        return isinstance(ts, int) and 1000000000000 <= ts <= 9999999999999
    
    def get_closed_candles(self) -> List[List]:
        """
        获取所有已收线K线（不含 forming_candle）
        
        Returns:
            已收线K线列表 (candles[:-1])
        """
        return self.candles[:-1] if len(self.candles) > 1 else []
    
    def get_candles_with_forming(self) -> List[List]:
        """
        获取包含 forming_candle 的所有K线
        
        Returns:
            所有K线列表
        """
        return self.candles
    
    def get_recent_closed(self, n: int) -> List[List]:
        """
        获取最近 n 根已收线K线
        
        Args:
            n: 需要的K线数量
        
        Returns:
            最近 n 根已收线K线
        """
        closed = self.get_closed_candles()
        return closed[-n:] if len(closed) >= n else closed
    
    def __repr__(self) -> str:
        return (
            f"DualChannelOHLCV("
            f"symbol={self.symbol}, "
            f"timeframe={self.timeframe}, "
            f"forming_ts={self.forming_ts}, "
            f"closed_ts={self.closed_ts}, "
            f"candles_count={len(self.candles)})"
        )


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


def get_timeframe_ms(timeframe: str) -> int:
    """获取时间周期的毫秒数"""
    return TIMEFRAME_MS.get(timeframe, 60 * 1000)


class IncrementalFetcher:
    """
    增量K线拉取管理器
    
    维护每个 (symbol, timeframe) 的 since_ts，用于增量拉取K线数据
    避免重复拉取旧数据
    
    计算公式: since_ts = max(0, last_seen_ts - 2 * tf_ms)
    """
    
    def __init__(self):
        # {(symbol, timeframe): since_ts}
        self._since_ts: Dict[Tuple[str, str], int] = {}
    
    def get_since_ts(self, symbol: str, timeframe: str) -> int:
        """
        获取增量拉取起始时间戳
        
        Args:
            symbol: 交易对
            timeframe: 时间周期
        
        Returns:
            since_ts，如果是新的 symbol+timeframe 则返回 0
        """
        key = (symbol, timeframe)
        return self._since_ts.get(key, 0)
    
    def update_since_ts(self, symbol: str, timeframe: str, latest_ts: int) -> None:
        """
        更新最后看到的时间戳
        
        Args:
            symbol: 交易对
            timeframe: 时间周期
            latest_ts: 最新K线的时间戳
        """
        key = (symbol, timeframe)
        tf_ms = get_timeframe_ms(timeframe)
        
        # 计算新的 since_ts
        new_since = self.calculate_since(latest_ts, tf_ms)
        self._since_ts[key] = new_since
        
        logger.debug(
            f"Updated since_ts for {symbol}/{timeframe}: "
            f"latest_ts={latest_ts}, new_since={new_since}"
        )
    
    @staticmethod
    def calculate_since(last_seen_ts: int, tf_ms: int) -> int:
        """
        计算 since_ts
        
        公式: since_ts = max(0, last_seen_ts - 2 * tf_ms)
        
        Args:
            last_seen_ts: 最后看到的K线时间戳
            tf_ms: 时间周期毫秒数
        
        Returns:
            计算后的 since_ts
        """
        return max(0, last_seen_ts - 2 * tf_ms)
    
    def clear(self, symbol: str = None, timeframe: str = None) -> None:
        """
        清除 since_ts 记录
        
        Args:
            symbol: 指定交易对，None 表示全部
            timeframe: 指定时间周期，None 表示全部
        """
        if symbol is None and timeframe is None:
            self._since_ts.clear()
            logger.info("Cleared all since_ts records")
        else:
            keys_to_remove = [
                k for k in self._since_ts
                if (symbol is None or k[0] == symbol) and
                   (timeframe is None or k[1] == timeframe)
            ]
            for k in keys_to_remove:
                del self._since_ts[k]
            logger.info(f"Cleared since_ts for symbol={symbol}, timeframe={timeframe}")
    
    def get_all_since_ts(self) -> Dict[Tuple[str, str], int]:
        """获取所有 since_ts 记录"""
        return self._since_ts.copy()


# 全局单例
_incremental_fetcher: Optional[IncrementalFetcher] = None


def get_incremental_fetcher() -> IncrementalFetcher:
    """获取全局 IncrementalFetcher 实例"""
    global _incremental_fetcher
    if _incremental_fetcher is None:
        _incremental_fetcher = IncrementalFetcher()
    return _incremental_fetcher
