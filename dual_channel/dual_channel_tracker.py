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
# dual_channel_tracker.py
# 双通道信号追踪器 - 盘中信号去重 + 收线信号去重
# 核心设计：
# - IntrabarSignalTracker: 盘中执行信号去重（基于 forming_ts）
# - ConfirmedSignalTracker: 收线确认信号去重（基于 closed_ts）

from dataclasses import dataclass
from typing import Dict, Tuple, Optional, List
import logging
import time

logger = logging.getLogger(__name__)


@dataclass
class Signal:
    """
    信号数据模型
    
    Attributes:
        symbol: 交易对
        timeframe: 时间周期
        action: 信号动作 "BUY" | "SELL" | "HOLD"
        signal_type: 信号类型 "intrabar" | "confirmed"
        candle_ts: 信号对应的K线时间戳 (UTC ms)
        price: 信号触发时的价格
        reason: 信号原因
        timestamp: 信号生成时间 (UTC ms)
        label: UI展示标签
        color: 标记颜色
    """
    symbol: str
    timeframe: str
    action: str
    signal_type: str
    candle_ts: int
    price: float
    reason: str
    timestamp: int
    label: str = ""
    color: str = ""
    
    def __post_init__(self):
        # 根据 signal_type 设置默认 label 和 color
        if not self.label:
            if self.signal_type == "intrabar":
                self.label = "抢跑/未确认"
            elif self.signal_type == "confirmed":
                self.label = "收线确认/对标TV"
        
        if not self.color:
            if self.signal_type == "intrabar":
                self.color = "#FFA500"  # 橙色
            elif self.signal_type == "confirmed":
                self.color = "#00FF00"  # 绿色


class IntrabarSignalTracker:
    """
    盘中信号去重追踪器
    
    功能：
    1. 追踪每个 (symbol, timeframe, action) 的最后触发 forming_ts
    2. 防止同一根 forming_candle 重复触发信号
    3. 新的 forming_ts 允许重新触发
    
    去重逻辑：
    - 同一根 forming_candle (相同 forming_ts) 只允许触发一次
    - 不同 forming_ts 可以重新触发
    """
    
    # 保留最近 N 条记录
    MAX_HISTORY = 100
    
    def __init__(self):
        # {(symbol, timeframe, action): forming_ts}
        self._fired_intrabar_ts: Dict[Tuple[str, str, str], int] = {}
    
    def should_fire(
        self,
        symbol: str,
        timeframe: str,
        action: str,
        forming_ts: int
    ) -> bool:
        """
        检查是否应该触发盘中信号（去重）
        
        Args:
            symbol: 交易对
            timeframe: 时间周期
            action: 信号动作 (BUY/SELL)
            forming_ts: forming_candle 的时间戳
        
        Returns:
            True 如果应该触发（未重复），False 如果已触发过
        """
        key = (symbol, timeframe, action)
        last_ts = self._fired_intrabar_ts.get(key, 0)
        
        # 如果 forming_ts 与上次相同，说明是同一根K线，不应重复触发
        if forming_ts == last_ts:
            logger.debug(
                f"Intrabar signal blocked (duplicate): "
                f"{symbol}/{timeframe} {action} forming_ts={forming_ts}"
            )
            return False
        
        return True
    
    def record_fired(
        self,
        symbol: str,
        timeframe: str,
        action: str,
        forming_ts: int
    ) -> None:
        """
        记录已触发的盘中信号
        
        Args:
            symbol: 交易对
            timeframe: 时间周期
            action: 信号动作
            forming_ts: forming_candle 的时间戳
        """
        key = (symbol, timeframe, action)
        self._fired_intrabar_ts[key] = forming_ts
        
        logger.debug(
            f"Intrabar signal recorded: "
            f"{symbol}/{timeframe} {action} forming_ts={forming_ts}"
        )
        
        # 清理过期记录
        self._cleanup_old_records()
    
    def _cleanup_old_records(self) -> None:
        """清理过期的记录"""
        if len(self._fired_intrabar_ts) > self.MAX_HISTORY:
            # 按时间戳排序，删除最旧的记录
            sorted_items = sorted(
                self._fired_intrabar_ts.items(),
                key=lambda x: x[1]
            )
            
            # 保留最新的 MAX_HISTORY 条记录
            items_to_keep = sorted_items[-self.MAX_HISTORY:]
            self._fired_intrabar_ts = dict(items_to_keep)
            
            logger.debug(
                f"Cleaned up intrabar tracker, "
                f"kept {len(self._fired_intrabar_ts)} records"
            )
    
    def get_last_fired_ts(
        self,
        symbol: str,
        timeframe: str,
        action: str
    ) -> int:
        """获取最后触发的 forming_ts"""
        key = (symbol, timeframe, action)
        return self._fired_intrabar_ts.get(key, 0)
    
    def clear(self, symbol: str = None, timeframe: str = None) -> None:
        """
        清除记录
        
        Args:
            symbol: 指定交易对，None 表示全部
            timeframe: 指定时间周期，None 表示全部
        """
        if symbol is None and timeframe is None:
            self._fired_intrabar_ts.clear()
            logger.info("Cleared all intrabar signal records")
        else:
            keys_to_remove = [
                k for k in self._fired_intrabar_ts
                if (symbol is None or k[0] == symbol) and
                   (timeframe is None or k[1] == timeframe)
            ]
            for k in keys_to_remove:
                del self._fired_intrabar_ts[k]
            logger.info(
                f"Cleared intrabar signals for "
                f"symbol={symbol}, timeframe={timeframe}"
            )
    
    def get_fired_count(self) -> int:
        """获取已触发信号的数量"""
        return len(self._fired_intrabar_ts)


class ConfirmedSignalTracker:
    """
    收线确认信号去重追踪器
    
    功能：
    1. 追踪每个 (symbol, timeframe) 的最后计算 closed_ts
    2. 防止同一根 closed_candle 重复计算信号
    3. 新的 closed_ts 允许重新计算
    
    去重逻辑：
    - 同一根 closed_candle (相同 closed_ts) 只计算一次
    - 不同 closed_ts 可以重新计算
    """
    
    def __init__(self):
        # {(symbol, timeframe): closed_ts}
        self._last_confirmed_ts: Dict[Tuple[str, str], int] = {}
    
    def should_calculate(
        self,
        symbol: str,
        timeframe: str,
        closed_ts: int
    ) -> bool:
        """
        检查是否应该计算收线信号（去重）
        
        Args:
            symbol: 交易对
            timeframe: 时间周期
            closed_ts: last_closed_candle 的时间戳
        
        Returns:
            True 如果应该计算（新K线），False 如果已计算过
        """
        key = (symbol, timeframe)
        last_ts = self._last_confirmed_ts.get(key, 0)
        
        # 如果 closed_ts 与上次相同，说明没有新的收线K线
        if closed_ts == last_ts:
            logger.debug(
                f"Confirmed signal blocked (no new candle): "
                f"{symbol}/{timeframe} closed_ts={closed_ts}"
            )
            return False
        
        # 如果 closed_ts 小于上次，说明数据异常
        if closed_ts < last_ts:
            logger.warning(
                f"Confirmed signal blocked (older candle): "
                f"{symbol}/{timeframe} closed_ts={closed_ts} < last={last_ts}"
            )
            return False
        
        return True
    
    def record_calculated(
        self,
        symbol: str,
        timeframe: str,
        closed_ts: int
    ) -> None:
        """
        记录已计算的收线信号
        
        Args:
            symbol: 交易对
            timeframe: 时间周期
            closed_ts: last_closed_candle 的时间戳
        """
        key = (symbol, timeframe)
        self._last_confirmed_ts[key] = closed_ts
        
        logger.debug(
            f"Confirmed signal recorded: "
            f"{symbol}/{timeframe} closed_ts={closed_ts}"
        )
    
    def get_last_confirmed_ts(
        self,
        symbol: str,
        timeframe: str
    ) -> int:
        """获取最后计算的 closed_ts"""
        key = (symbol, timeframe)
        return self._last_confirmed_ts.get(key, 0)
    
    def clear(self, symbol: str = None, timeframe: str = None) -> None:
        """
        清除记录
        
        Args:
            symbol: 指定交易对，None 表示全部
            timeframe: 指定时间周期，None 表示全部
        """
        if symbol is None and timeframe is None:
            self._last_confirmed_ts.clear()
            logger.info("Cleared all confirmed signal records")
        else:
            keys_to_remove = [
                k for k in self._last_confirmed_ts
                if (symbol is None or k[0] == symbol) and
                   (timeframe is None or k[1] == timeframe)
            ]
            for k in keys_to_remove:
                del self._last_confirmed_ts[k]
            logger.info(
                f"Cleared confirmed signals for "
                f"symbol={symbol}, timeframe={timeframe}"
            )
    
    def get_calculated_count(self) -> int:
        """获取已计算信号的数量"""
        return len(self._last_confirmed_ts)


# 全局单例
_intrabar_tracker: Optional[IntrabarSignalTracker] = None
_confirmed_tracker: Optional[ConfirmedSignalTracker] = None


def get_intrabar_tracker() -> IntrabarSignalTracker:
    """获取全局 IntrabarSignalTracker 实例"""
    global _intrabar_tracker
    if _intrabar_tracker is None:
        _intrabar_tracker = IntrabarSignalTracker()
    return _intrabar_tracker


def get_confirmed_tracker() -> ConfirmedSignalTracker:
    """获取全局 ConfirmedSignalTracker 实例"""
    global _confirmed_tracker
    if _confirmed_tracker is None:
        _confirmed_tracker = ConfirmedSignalTracker()
    return _confirmed_tracker
