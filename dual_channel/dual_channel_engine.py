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
# dual_channel_engine.py
# 双通道信号计算引擎 - 盘中执行通道 + 收线对标通道
# 核心设计：
# - 盘中执行信号 (intrabar): 使用 forming_candle 计算，用于59秒抢跑下单
# - 收线确认信号 (confirmed): 使用 last_closed_candle 计算，用于对标TradingView
# - 支持三种执行模式: intrabar / confirmed / both

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
import pandas as pd
import time
import logging

from .dual_channel_ohlcv import DualChannelOHLCV, InsufficientDataError
from .dual_channel_tracker import (
    Signal, 
    IntrabarSignalTracker, 
    ConfirmedSignalTracker,
    get_intrabar_tracker,
    get_confirmed_tracker
)

logger = logging.getLogger(__name__)


@dataclass
class ScanResult:
    """
    扫描结果数据模型
    
    Attributes:
        timeframe: 时间周期
        scan_time: 扫描时间 HH:MM:SS 格式
        forming_ts: forming_candle 时间戳
        closed_ts: last_closed_candle 时间戳
        intrabar_signals: 盘中信号列表
        confirmed_signals: 收线确认信号列表
        intrabar_fired_count: 本次触发的盘中信号数量
        confirmed_new_count: 本次新增的收线信号数量
        orders_executed: 已执行的订单列表
    """
    timeframe: str
    scan_time: str
    forming_ts: int
    closed_ts: int
    intrabar_signals: List[Signal] = field(default_factory=list)
    confirmed_signals: List[Signal] = field(default_factory=list)
    intrabar_fired_count: int = 0
    confirmed_new_count: int = 0
    orders_executed: List[Dict] = field(default_factory=list)


@dataclass
class ExecutionConfig:
    """
    执行配置数据模型
    
    Attributes:
        execution_mode: 执行模式 "intrabar" | "confirmed" | "both"
    """
    execution_mode: str = "intrabar"
    
    def should_execute_intrabar(self) -> bool:
        """是否使用盘中信号执行订单"""
        return self.execution_mode in ("intrabar", "both")
    
    def should_execute_confirmed(self) -> bool:
        """是否使用收线信号执行订单"""
        return self.execution_mode == "confirmed"
    
    def should_calculate_both(self) -> bool:
        """是否计算两种信号"""
        return self.execution_mode == "both"
    
    def should_calculate_intrabar(self) -> bool:
        """是否计算盘中信号"""
        return self.execution_mode in ("intrabar", "both")
    
    def should_calculate_confirmed(self) -> bool:
        """是否计算收线信号"""
        return self.execution_mode in ("confirmed", "both")


class DualChannelSignalEngine:
    """
    双通道信号计算引擎
    
    功能：
    1. 计算盘中执行信号 (intrabar): 使用 forming_candle
    2. 计算收线确认信号 (confirmed): 使用 last_closed_candle
    3. 根据 execution_mode 决定使用哪种信号执行订单
    4. 信号去重：同一根K线只触发一次
    """
    
    def __init__(
        self,
        strategy: Any,
        execution_mode: str = "intrabar"
    ):
        """
        初始化双通道信号引擎
        
        Args:
            strategy: 策略引擎实例（需要有 calculate_indicators 和 check_signals 方法）
            execution_mode: 执行模式 "intrabar" | "confirmed" | "both"
        """
        self.strategy = strategy
        self.config = ExecutionConfig(execution_mode=execution_mode)
        self.intrabar_tracker = get_intrabar_tracker()
        self.confirmed_tracker = get_confirmed_tracker()
    
    def set_execution_mode(self, mode: str) -> None:
        """
        设置执行模式
        
        Args:
            mode: "intrabar" | "confirmed" | "both"
        """
        if mode not in ("intrabar", "confirmed", "both"):
            logger.warning(f"Invalid execution mode: {mode}, using 'intrabar'")
            mode = "intrabar"
        
        self.config.execution_mode = mode
        logger.info(f"Execution mode set to: {mode}")
    
    def calculate_intrabar_signal(
        self,
        data: DualChannelOHLCV
    ) -> Optional[Signal]:
        """
        计算盘中执行信号（使用 forming_candle）
        
        Args:
            data: DualChannelOHLCV 数据
        
        Returns:
            Signal 对象，如果无信号则返回 None
        """
        try:
            # 使用包含 forming_candle 的所有K线
            candles = data.get_candles_with_forming()
            
            if len(candles) < 200:
                logger.debug(
                    f"Insufficient data for intrabar signal: "
                    f"{data.symbol}/{data.timeframe} ({len(candles)} candles)"
                )
                return None
            
            # 转换为 DataFrame
            df = pd.DataFrame(
                candles,
                columns=['ts', 'open', 'high', 'low', 'close', 'volume']
            )
            
            # 计算指标
            df = self.strategy.calculate_indicators(df)
            
            # 检查信号
            signal_result = self.strategy.check_signals(df, data.timeframe)
            
            if signal_result.get('action') in ('LONG', 'SHORT'):
                action = 'BUY' if signal_result['action'] == 'LONG' else 'SELL'
                
                # 检查去重
                if not self.intrabar_tracker.should_fire(
                    data.symbol, data.timeframe, action, data.forming_ts
                ):
                    return None
                
                # 创建信号
                signal = Signal(
                    symbol=data.symbol,
                    timeframe=data.timeframe,
                    action=action,
                    signal_type="intrabar",
                    candle_ts=data.forming_ts,
                    price=float(data.forming_candle[4]),  # close price
                    reason=signal_result.get('reason', ''),
                    timestamp=int(time.time() * 1000)
                )
                
                # 记录已触发
                self.intrabar_tracker.record_fired(
                    data.symbol, data.timeframe, action, data.forming_ts
                )
                
                return signal
            
            return None
            
        except Exception as e:
            logger.error(
                f"Error calculating intrabar signal for "
                f"{data.symbol}/{data.timeframe}: {e}"
            )
            return None
    
    def calculate_confirmed_signal(
        self,
        data: DualChannelOHLCV
    ) -> Optional[Signal]:
        """
        计算收线确认信号（使用 last_closed_candle，不含 forming_candle）
        
        Args:
            data: DualChannelOHLCV 数据
        
        Returns:
            Signal 对象，如果无信号则返回 None
        """
        try:
            # 检查去重（是否有新的收线K线）
            if not self.confirmed_tracker.should_calculate(
                data.symbol, data.timeframe, data.closed_ts
            ):
                return None
            
            # 使用不含 forming_candle 的已收线K线
            candles = data.get_closed_candles()
            
            if len(candles) < 200:
                logger.debug(
                    f"Insufficient data for confirmed signal: "
                    f"{data.symbol}/{data.timeframe} ({len(candles)} candles)"
                )
                return None
            
            # 转换为 DataFrame
            df = pd.DataFrame(
                candles,
                columns=['ts', 'open', 'high', 'low', 'close', 'volume']
            )
            
            # 计算指标
            df = self.strategy.calculate_indicators(df)
            
            # 检查信号
            signal_result = self.strategy.check_signals(df, data.timeframe)
            
            # 记录已计算（无论是否有信号）
            self.confirmed_tracker.record_calculated(
                data.symbol, data.timeframe, data.closed_ts
            )
            
            if signal_result.get('action') in ('LONG', 'SHORT'):
                action = 'BUY' if signal_result['action'] == 'LONG' else 'SELL'
                
                # 创建信号
                signal = Signal(
                    symbol=data.symbol,
                    timeframe=data.timeframe,
                    action=action,
                    signal_type="confirmed",
                    candle_ts=data.closed_ts,
                    price=float(data.last_closed_candle[4]),  # close price
                    reason=signal_result.get('reason', ''),
                    timestamp=int(time.time() * 1000)
                )
                
                return signal
            
            return None
            
        except Exception as e:
            logger.error(
                f"Error calculating confirmed signal for "
                f"{data.symbol}/{data.timeframe}: {e}"
            )
            return None
    
    def process_scan(
        self,
        data: DualChannelOHLCV,
        scan_time: str = None
    ) -> ScanResult:
        """
        处理一次扫描，返回双通道信号结果
        
        Args:
            data: DualChannelOHLCV 数据
            scan_time: 扫描时间字符串 (HH:MM:SS)，默认为当前时间
        
        Returns:
            ScanResult 包含双通道信号结果
        """
        if scan_time is None:
            from datetime import datetime
            scan_time = datetime.now().strftime('%H:%M:%S')
        
        result = ScanResult(
            timeframe=data.timeframe,
            scan_time=scan_time,
            forming_ts=data.forming_ts,
            closed_ts=data.closed_ts
        )
        
        # 计算盘中信号
        if self.config.should_calculate_intrabar():
            intrabar_signal = self.calculate_intrabar_signal(data)
            if intrabar_signal:
                result.intrabar_signals.append(intrabar_signal)
                result.intrabar_fired_count += 1
        
        # 计算收线信号
        if self.config.should_calculate_confirmed():
            confirmed_signal = self.calculate_confirmed_signal(data)
            if confirmed_signal:
                result.confirmed_signals.append(confirmed_signal)
                result.confirmed_new_count += 1
        
        return result
    
    def get_execution_signal(self, result: ScanResult) -> Optional[Signal]:
        """
        根据执行模式获取用于下单的信号
        
        Args:
            result: ScanResult 扫描结果
        
        Returns:
            用于执行的 Signal，如果无信号则返回 None
        """
        if self.config.should_execute_intrabar():
            # 使用盘中信号
            if result.intrabar_signals:
                return result.intrabar_signals[0]
        elif self.config.should_execute_confirmed():
            # 使用收线信号
            if result.confirmed_signals:
                return result.confirmed_signals[0]
        
        return None
    
    def clear_trackers(
        self,
        symbol: str = None,
        timeframe: str = None
    ) -> None:
        """
        清除追踪器记录
        
        Args:
            symbol: 指定交易对，None 表示全部
            timeframe: 指定时间周期，None 表示全部
        """
        self.intrabar_tracker.clear(symbol, timeframe)
        self.confirmed_tracker.clear(symbol, timeframe)


# 全局单例
_dual_channel_engine: Optional[DualChannelSignalEngine] = None


def get_dual_channel_engine(
    strategy: Any = None,
    execution_mode: str = "intrabar"
) -> DualChannelSignalEngine:
    """
    获取全局 DualChannelSignalEngine 实例
    
    Args:
        strategy: 策略引擎实例（首次调用时必须提供）
        execution_mode: 执行模式
    
    Returns:
        DualChannelSignalEngine 实例
    """
    global _dual_channel_engine
    
    if _dual_channel_engine is None:
        if strategy is None:
            raise ValueError("Strategy must be provided for first initialization")
        _dual_channel_engine = DualChannelSignalEngine(strategy, execution_mode)
    elif strategy is not None:
        # 更新策略
        _dual_channel_engine.strategy = strategy
    
    return _dual_channel_engine
