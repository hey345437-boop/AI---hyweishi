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
# dual_channel_logger.py
# 双通道极简日志器 - 每次扫描只输出必要的日志
# 日志格式：
# - 扫描摘要: [scan] tf=1m at=19:47:59 forming_ts=... closed_ts=... intrabar_fired=0 confirmed_new=1
# - 盘中交易: [trade] intrabar BUY symbol=BTC/USDT price=50000.00 forming_ts=...
# - 收线信号: [signal] confirmed BUY symbol=BTC/USDT closed_ts=...

import logging
from typing import Optional
from utils.beijing_time_converter import BeijingTimeConverter

logger = logging.getLogger(__name__)


class DualChannelLogger:
    """
    双通道极简日志器
    
    功能：
    1. 每次59秒扫描输出一行摘要
    2. 触发盘中下单时输出一行交易日志
    3. 产生收线信号时输出一行信号日志
    
    设计原则：
    - 极简：每次扫描最多输出 1 行摘要 + N 行触发日志
    - 信息足够：包含关键时间戳和计数
    - 双时间戳：同时显示 UTC ms 和北京时间
    """
    
    def __init__(self, use_print: bool = True):
        """
        初始化日志器
        
        Args:
            use_print: 是否使用 print 输出（用于控制台），否则使用 logger
        """
        self.use_print = use_print
    
    def _output(self, message: str, level: str = "info") -> None:
        """输出日志"""
        if self.use_print:
            print(message)
        else:
            if level == "info":
                logger.info(message)
            elif level == "warning":
                logger.warning(message)
            elif level == "error":
                logger.error(message)
    
    def log_scan_summary(
        self,
        tf: str,
        scan_time: str,
        forming_ts: int,
        closed_ts: int,
        intrabar_fired: int,
        confirmed_new: int
    ) -> str:
        """
        输出扫描摘要行
        
        格式: [scan] tf=1m at=19:47:59 forming_ts=1702800000000(20:00:00) closed_ts=1702799940000(19:59:00) intrabar_fired=0 confirmed_new=1
        
        Args:
            tf: 时间周期
            scan_time: 扫描时间 HH:MM:SS
            forming_ts: forming_candle 时间戳 (UTC ms)
            closed_ts: last_closed_candle 时间戳 (UTC ms)
            intrabar_fired: 本次触发的盘中信号数量
            confirmed_new: 本次新增的收线信号数量
        
        Returns:
            格式化的日志字符串
        """
        # 转换为北京时间
        forming_bj = BeijingTimeConverter.to_beijing_str(forming_ts, '%H:%M:%S')
        closed_bj = BeijingTimeConverter.to_beijing_str(closed_ts, '%H:%M:%S')
        
        message = (
            f"[scan] tf={tf} at={scan_time} "
            f"forming_ts={forming_ts}({forming_bj}) "
            f"closed_ts={closed_ts}({closed_bj}) "
            f"intrabar_fired={intrabar_fired} confirmed_new={confirmed_new}"
        )
        
        self._output(message)
        return message
    
    def log_intrabar_trade(
        self,
        action: str,
        symbol: str,
        price: float,
        forming_ts: int
    ) -> str:
        """
        输出盘中交易行
        
        格式: [trade] intrabar BUY symbol=BTC/USDT price=50000.00 forming_ts=1702800000000(20:00:00)
        
        Args:
            action: 交易动作 BUY/SELL
            symbol: 交易对
            price: 成交价格
            forming_ts: forming_candle 时间戳 (UTC ms)
        
        Returns:
            格式化的日志字符串
        """
        # 转换为北京时间
        forming_bj = BeijingTimeConverter.to_beijing_str(forming_ts, '%H:%M:%S')
        
        message = (
            f"[trade] intrabar {action} symbol={symbol} "
            f"price={price:.2f} forming_ts={forming_ts}({forming_bj})"
        )
        
        self._output(message)
        return message
    
    def log_confirmed_signal(
        self,
        action: str,
        symbol: str,
        closed_ts: int
    ) -> str:
        """
        输出收线信号行
        
        格式: [signal] confirmed BUY symbol=BTC/USDT closed_ts=1702799940000(19:59:00)
        
        Args:
            action: 信号动作 BUY/SELL
            symbol: 交易对
            closed_ts: last_closed_candle 时间戳 (UTC ms)
        
        Returns:
            格式化的日志字符串
        """
        # 转换为北京时间
        closed_bj = BeijingTimeConverter.to_beijing_str(closed_ts, '%H:%M:%S')
        
        message = (
            f"[signal] confirmed {action} symbol={symbol} "
            f"closed_ts={closed_ts}({closed_bj})"
        )
        
        self._output(message)
        return message
    
    def log_scan_result(self, result) -> None:
        """
        输出完整的扫描结果
        
        Args:
            result: ScanResult 对象
        """
        # 输出摘要
        self.log_scan_summary(
            tf=result.timeframe,
            scan_time=result.scan_time,
            forming_ts=result.forming_ts,
            closed_ts=result.closed_ts,
            intrabar_fired=result.intrabar_fired_count,
            confirmed_new=result.confirmed_new_count
        )
        
        # 输出盘中交易
        for signal in result.intrabar_signals:
            self.log_intrabar_trade(
                action=signal.action,
                symbol=signal.symbol,
                price=signal.price,
                forming_ts=signal.candle_ts
            )
        
        # 输出收线信号（仅当没有对应的盘中交易时）
        for signal in result.confirmed_signals:
            # 检查是否已有对应的盘中交易
            has_intrabar = any(
                s.symbol == signal.symbol and s.action == signal.action
                for s in result.intrabar_signals
            )
            if not has_intrabar:
                self.log_confirmed_signal(
                    action=signal.action,
                    symbol=signal.symbol,
                    closed_ts=signal.candle_ts
                )


# 全局单例
_dual_channel_logger: Optional[DualChannelLogger] = None


def get_dual_channel_logger(use_print: bool = True) -> DualChannelLogger:
    """获取全局 DualChannelLogger 实例"""
    global _dual_channel_logger
    if _dual_channel_logger is None:
        _dual_channel_logger = DualChannelLogger(use_print=use_print)
    return _dual_channel_logger


def format_scan_summary_line(
    tf: str,
    scan_time: str,
    forming_ts: int,
    closed_ts: int,
    intrabar_fired: int,
    confirmed_new: int
) -> str:
    """
    格式化扫描摘要行（不输出，仅返回字符串）
    
    用于需要自定义输出的场景
    """
    forming_bj = BeijingTimeConverter.to_beijing_str(forming_ts, '%H:%M:%S')
    closed_bj = BeijingTimeConverter.to_beijing_str(closed_ts, '%H:%M:%S')
    
    return (
        f"[scan] tf={tf} at={scan_time} "
        f"forming_ts={forming_ts}({forming_bj}) "
        f"closed_ts={closed_ts}({closed_bj}) "
        f"intrabar_fired={intrabar_fired} confirmed_new={confirmed_new}"
    )


def format_intrabar_trade_line(
    action: str,
    symbol: str,
    price: float,
    forming_ts: int
) -> str:
    """格式化盘中交易行（不输出，仅返回字符串）"""
    forming_bj = BeijingTimeConverter.to_beijing_str(forming_ts, '%H:%M:%S')
    
    return (
        f"[trade] intrabar {action} symbol={symbol} "
        f"price={price:.2f} forming_ts={forming_ts}({forming_bj})"
    )


def format_confirmed_signal_line(
    action: str,
    symbol: str,
    closed_ts: int
) -> str:
    """格式化收线信号行（不输出，仅返回字符串）"""
    closed_bj = BeijingTimeConverter.to_beijing_str(closed_ts, '%H:%M:%S')
    
    return (
        f"[signal] confirmed {action} symbol={symbol} "
        f"closed_ts={closed_ts}({closed_bj})"
    )
