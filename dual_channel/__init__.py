# -*- coding: utf-8 -*-
"""
双通道信号系统模块

包含双通道引擎、追踪器、日志、OHLCV 处理等
"""

from .dual_channel_engine import (
    DualChannelSignalEngine,
    ScanResult,
    ExecutionConfig
)
from .dual_channel_tracker import (
    Signal,
    IntrabarSignalTracker,
    ConfirmedSignalTracker
)
from .dual_channel_logger import DualChannelLogger
from .dual_channel_ohlcv import (
    DualChannelOHLCV,
    IncrementalFetcher,
    InsufficientDataError
)
from .dual_channel_integration import DualChannelIntegration

__all__ = [
    # dual_channel_engine
    'DualChannelSignalEngine', 'ScanResult', 'ExecutionConfig',
    # dual_channel_tracker
    'Signal', 'IntrabarSignalTracker', 'ConfirmedSignalTracker',
    # dual_channel_logger
    'DualChannelLogger',
    # dual_channel_ohlcv
    'DualChannelOHLCV', 'IncrementalFetcher', 'InsufficientDataError',
    # dual_channel_integration
    'DualChannelIntegration'
]
