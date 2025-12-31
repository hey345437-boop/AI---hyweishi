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
风控模块 - 订单金额检查和单日损失限制
"""
import os
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """验证结果"""
    is_valid: bool
    error_message: Optional[str] = None
    error_code: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


@dataclass
class RiskControlConfig:
    """风控配置"""
    max_order_size: float = 1000.0  # 最大单笔订单金额 (USDT)
    daily_loss_limit_pct: float = 0.10  # 单日损失限制 (占权益百分比)
    enable_order_validation: bool = True
    enable_daily_loss_limit: bool = True
    leverage: int = 50  # 默认杠杆倍数


class OrderValidator:
    """
    订单验证器
    
    验证订单金额是否在允许范围内，防止误下大单造成巨额亏损。
    """
    
    DEFAULT_MAX_ORDER_SIZE = 1000.0  # 默认最大订单金额 (USDT)
    
    def __init__(self, max_order_size: Optional[float] = None):
        """
        初始化订单验证器
        
        Args:
            max_order_size: 最大订单金额，如果为 None 则使用默认值
        """
        self.max_order_size = max_order_size or self.DEFAULT_MAX_ORDER_SIZE
        logger.debug(f"OrderValidator 初始化，最大订单金额: ${self.max_order_size}")
    
    def validate(self, amount: float, symbol: str) -> ValidationResult:
        """
        验证订单金额
        
        Args:
            amount: 订单金额 (USDT)
            symbol: 交易对
        
        Returns:
            ValidationResult: 验证结果
        """
        if amount <= 0:
            return ValidationResult(
                is_valid=False,
                error_message=f"订单金额必须大于0，当前: {amount}",
                error_code="INVALID_AMOUNT",
                details={"amount": amount, "symbol": symbol}
            )
        
        if amount > self.max_order_size:
            error_msg = (
                f"订单金额 ${amount:.2f} 超过最大限制 ${self.max_order_size:.2f}"
            )
            logger.warning(f"🚫 风控拒绝: {error_msg} | 交易对: {symbol}")
            return ValidationResult(
                is_valid=False,
                error_message=error_msg,
                error_code="ORDER_SIZE_EXCEEDED",
                details={
                    "amount": amount,
                    "max_allowed": self.max_order_size,
                    "symbol": symbol,
                    "exceeded_by": amount - self.max_order_size
                }
            )
        
        return ValidationResult(
            is_valid=True,
            details={"amount": amount, "symbol": symbol}
        )


class DailyLossTracker:
    """
    单日损失追踪器
    
    追踪当日累计亏损，超过限制时暂停交易。
    """
    
    DEFAULT_LOSS_LIMIT_PCT = 0.10  # 默认10%权益
    
    def __init__(self, loss_limit_pct: Optional[float] = None):
        """
        初始化损失追踪器
        
        Args:
            loss_limit_pct: 损失限制百分比，如果为 None 则使用默认值
        """
        self.loss_limit_pct = loss_limit_pct or self.DEFAULT_LOSS_LIMIT_PCT
        self.daily_loss: float = 0.0
        self.last_reset_date: str = self._get_utc_date()
        logger.debug(f"DailyLossTracker 初始化，损失限制: {self.loss_limit_pct*100}%")
    
    def _get_utc_date(self) -> str:
        """获取当前 UTC 日期字符串"""
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")
    
    def reset_if_new_day(self) -> bool:
        """
        如果是新的一天则重置计数器
        
        Returns:
            bool: 是否进行了重置
        """
        current_date = self._get_utc_date()
        if current_date != self.last_reset_date:
            old_loss = self.daily_loss
            self.daily_loss = 0.0
            self.last_reset_date = current_date
            logger.info(f"📅 新交易日开始，重置日损失计数器 (昨日损失: ${old_loss:.2f})")
            return True
        return False
    
    def record_loss(self, pnl: float) -> None:
        """
        记录盈亏（负数为亏损）
        
        Args:
            pnl: 盈亏金额，负数表示亏损
        """
        self.reset_if_new_day()
        
        if pnl < 0:
            self.daily_loss += abs(pnl)
            logger.info(f"📉 记录亏损: ${abs(pnl):.2f}，当日累计亏损: ${self.daily_loss:.2f}")
    
    def is_limit_exceeded(self, equity: float) -> bool:
        """
        检查是否超过损失限制
        
        Args:
            equity: 当前账户权益
        
        Returns:
            bool: 是否超过限制
        """
        self.reset_if_new_day()
        
        if equity <= 0:
            return True
        
        max_loss = equity * self.loss_limit_pct
        exceeded = self.daily_loss >= max_loss
        
        if exceeded:
            logger.warning(
                f"🚨 单日损失限制触发！"
                f"当日亏损: ${self.daily_loss:.2f} >= 限额: ${max_loss:.2f} "
                f"({self.loss_limit_pct*100}% of ${equity:.2f})"
            )
        
        return exceeded
    
    def get_remaining_loss_allowance(self, equity: float) -> float:
        """
        获取剩余可亏损额度
        
        Args:
            equity: 当前账户权益
        
        Returns:
            float: 剩余可亏损金额
        """
        self.reset_if_new_day()
        max_loss = equity * self.loss_limit_pct
        return max(0, max_loss - self.daily_loss)


class RiskControlModule:
    """
    风控模块 - 统一管理订单验证和损失限制
    
    整合 OrderValidator 和 DailyLossTracker，提供统一的风控接口。
    """
    
    def __init__(self, config: Optional[RiskControlConfig] = None):
        """
        初始化风控模块
        
        Args:
            config: 风控配置，如果为 None 则使用默认配置
        """
        self.config = config or RiskControlConfig()
        self.order_validator = OrderValidator(self.config.max_order_size)
        self.daily_loss_tracker = DailyLossTracker(self.config.daily_loss_limit_pct)
        logger.debug("RiskControlModule 初始化完成")
    
    def validate_order(self, amount: float, symbol: str) -> ValidationResult:
        """
        验证订单
        
        Args:
            amount: 订单金额
            symbol: 交易对
        
        Returns:
            ValidationResult: 验证结果
        """
        if not self.config.enable_order_validation:
            return ValidationResult(is_valid=True)
        
        return self.order_validator.validate(amount, symbol)
    
    def record_trade_pnl(self, pnl: float) -> None:
        """
        记录交易盈亏
        
        Args:
            pnl: 盈亏金额
        """
        self.daily_loss_tracker.record_loss(pnl)
    
    def check_daily_loss_limit(self, equity: float) -> bool:
        """
        检查是否超过单日损失限制
        
        Args:
            equity: 当前账户权益
        
        Returns:
            bool: 是否超过限制（True 表示超过，应暂停交易）
        """
        if not self.config.enable_daily_loss_limit:
            return False
        
        return self.daily_loss_tracker.is_limit_exceeded(equity)
    
    def can_trade(self, equity: float) -> Tuple[bool, str]:
        """
        检查是否可以继续交易
        
        Args:
            equity: 当前账户权益
        
        Returns:
            Tuple[bool, str]: (是否可以交易, 原因说明)
        """
        if self.check_daily_loss_limit(equity):
            return False, "单日损失限制已触发，交易暂停"
        return True, "风控检查通过"


# 便捷函数：创建默认风控模块
def create_risk_control(
    max_order_size: Optional[float] = None,
    daily_loss_limit_pct: Optional[float] = None
) -> RiskControlModule:
    """
    创建风控模块
    
    Args:
        max_order_size: 最大订单金额
        daily_loss_limit_pct: 单日损失限制百分比
    
    Returns:
        RiskControlModule: 风控模块实例
    """
    config = RiskControlConfig(
        max_order_size=max_order_size or RiskControlConfig.max_order_size,
        daily_loss_limit_pct=daily_loss_limit_pct or RiskControlConfig.daily_loss_limit_pct
    )
    return RiskControlModule(config)


# 需要导入 Tuple
from typing import Tuple
