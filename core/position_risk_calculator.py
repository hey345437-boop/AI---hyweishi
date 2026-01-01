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
# position_risk_calculator.py
# 持仓风控计算器
# 核心修复：使用名义价值 (Notional Value) 而非保证金 (Margin) 进行风控判断
# 公式：
# - 名义价值 = 持仓数量 × 当前价格 × 合约面值
# - 保证金 = 名义价值 / 杠杆
# 风控规则：
# - 总持仓名义价值 <= 权益 × 最大持仓比例 (默认 10%)

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
from core.run_mode import RunMode, get_run_mode

logger = logging.getLogger(__name__)


@dataclass
class PositionInfo:
    """持仓信息"""
    symbol: str
    side: str  # 'long' or 'short'
    qty: float  # 持仓数量（币数量或合约张数）
    entry_price: float  # 入场价格
    current_price: float  # 当前价格
    contract_value: float = 1.0  # 合约面值（SWAP 合约用）
    leverage: int = 1  # 杠杆倍数
    
    @property
    def notional_value(self) -> float:
        """
        计算名义价值 (Notional Value)
        
        公式: qty × current_price × contract_value
        
        这是持仓的实际市场价值，用于风控判断
        """
        return abs(self.qty) * self.current_price * self.contract_value
    
    @property
    def margin_used(self) -> float:
        """
        计算占用保证金 (Used Margin)
        
        公式: notional_value / leverage
        
        注意：这个值不应该用于风控判断！
        """
        if self.leverage <= 0:
            return self.notional_value
        return self.notional_value / self.leverage
    
    @property
    def unrealized_pnl(self) -> float:
        """计算未实现盈亏"""
        if self.side == 'long':
            return (self.current_price - self.entry_price) * abs(self.qty) * self.contract_value
        else:  # short
            return (self.entry_price - self.current_price) * abs(self.qty) * self.contract_value


@dataclass
class RiskCheckResult:
    """风控检查结果"""
    can_trade: bool
    total_notional: float  # 当前总持仓名义价值
    max_notional: float  # 最大允许名义价值
    remaining_notional: float  # 剩余可用名义价值
    equity: float  # 账户权益
    margin_used: float  # 已用保证金（仅供参考，不用于风控）
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    
    def __str__(self) -> str:
        status = " 可开仓" if self.can_trade else "🚨 已超限"
        return (
            f"风控检查 | 权益: ${self.equity:.2f} | "
            f"持仓名义价值: ${self.total_notional:.2f} | "
            f"限额: ${self.max_notional:.2f} | "
            f"剩余: ${self.remaining_notional:.2f} | "
            f"状态: {status}"
        )


class PositionRiskCalculator:
    """
    持仓风控计算器
    
    核心功能：
    1. 计算所有持仓的名义价值总和
    2. 检查是否超过风控限制
    3. 支持 PAPER 和 LIVE 两种模式
    
    重要：使用名义价值而非保证金进行风控判断！
    """
    
    DEFAULT_MAX_POSITION_PCT = 0.10  # 默认最大持仓比例 10%
    
    def __init__(
        self,
        max_position_pct: float = DEFAULT_MAX_POSITION_PCT,
        run_mode: Optional[RunMode] = None
    ):
        """
        初始化风控计算器
        
        Args:
            max_position_pct: 最大持仓比例（相对于权益）
            run_mode: 运行模式
        """
        self.max_position_pct = max_position_pct
        self.run_mode = run_mode or get_run_mode()
        
        logger.info(
            f"PositionRiskCalculator 初始化 | "
            f"最大持仓比例: {max_position_pct*100:.1f}% | "
            f"运行模式: {self.run_mode}"
        )
    
    def calculate_total_notional(
        self,
        positions: List[PositionInfo]
    ) -> Tuple[float, float]:
        """
        计算所有持仓的名义价值总和
        
        Args:
            positions: 持仓列表
        
        Returns:
            (total_notional, total_margin) 元组
        """
        total_notional = 0.0
        total_margin = 0.0
        
        for pos in positions:
            notional = pos.notional_value
            margin = pos.margin_used
            
            total_notional += notional
            total_margin += margin
            
            logger.debug(
                f"持仓 {pos.symbol} {pos.side}: "
                f"qty={pos.qty:.6f} price={pos.current_price:.2f} "
                f"notional=${notional:.2f} margin=${margin:.2f}"
            )
        
        return total_notional, total_margin
    
    def check_risk(
        self,
        equity: float,
        positions: List[PositionInfo],
        proposed_notional: float = 0.0
    ) -> RiskCheckResult:
        """
        执行风控检查
        
        Args:
            equity: 账户权益
            positions: 当前持仓列表
            proposed_notional: 拟开仓的名义价值（可选）
        
        Returns:
            RiskCheckResult 风控检查结果
        """
        if equity <= 0:
            return RiskCheckResult(
                can_trade=False,
                total_notional=0,
                max_notional=0,
                remaining_notional=0,
                equity=equity,
                margin_used=0,
                message="权益为零或负数"
            )
        
        # 计算当前持仓的名义价值
        total_notional, total_margin = self.calculate_total_notional(positions)
        
        # 计算最大允许的名义价值
        max_notional = equity * self.max_position_pct
        
        # 计算剩余可用名义价值
        remaining_notional = max(0, max_notional - total_notional)
        
        # 检查是否可以开仓
        new_total = total_notional + proposed_notional
        can_trade = new_total <= max_notional
        
        # 生成消息
        if can_trade:
            if proposed_notional > 0:
                message = f"风控通过，可开仓 ${proposed_notional:.2f}"
            else:
                message = "风控通过"
        else:
            message = (
                f"风控拒绝: 持仓名义价值 ${total_notional:.2f} "
                f"+ 拟开仓 ${proposed_notional:.2f} = ${new_total:.2f} "
                f"> 限额 ${max_notional:.2f}"
            )
        
        result = RiskCheckResult(
            can_trade=can_trade,
            total_notional=total_notional,
            max_notional=max_notional,
            remaining_notional=remaining_notional,
            equity=equity,
            margin_used=total_margin,
            message=message,
            details={
                "position_count": len(positions),
                "max_position_pct": self.max_position_pct,
                "proposed_notional": proposed_notional,
                "run_mode": str(self.run_mode)
            }
        )
        
        # 记录日志
        log_level = logging.INFO if can_trade else logging.WARNING
        logger.log(log_level, str(result))
        
        return result
    
    def check_can_open_position(
        self,
        equity: float,
        positions: List[PositionInfo],
        proposed_notional: float
    ) -> Tuple[bool, str]:
        """
        检查是否可以开新仓位
        
        Args:
            equity: 账户权益
            positions: 当前持仓列表
            proposed_notional: 拟开仓的名义价值
        
        Returns:
            (can_open, reason) 元组
        """
        result = self.check_risk(equity, positions, proposed_notional)
        return result.can_trade, result.message


def create_position_info_from_paper(
    paper_position: Dict[str, Any],
    current_price: float,
    leverage: int = 1,
    contract_value: float = 1.0
) -> PositionInfo:
    """
    从模拟持仓数据创建 PositionInfo
    
    Args:
        paper_position: 模拟持仓字典
        current_price: 当前价格
        leverage: 杠杆倍数
        contract_value: 合约面值
    
    Returns:
        PositionInfo 实例
    """
    return PositionInfo(
        symbol=paper_position.get('symbol', ''),
        side=paper_position.get('side', 'long'),
        qty=float(paper_position.get('qty', 0) or 0),
        entry_price=float(paper_position.get('entry_price', 0) or 0),
        current_price=current_price,
        contract_value=contract_value,
        leverage=leverage
    )


def create_position_info_from_exchange(
    exchange_position: Dict[str, Any],
    leverage: int = 1
) -> PositionInfo:
    """
    从交易所持仓数据创建 PositionInfo
    
    Args:
        exchange_position: 交易所持仓字典（ccxt 格式）
        leverage: 杠杆倍数
    
    Returns:
        PositionInfo 实例
    """
    # 提取合约数量
    contracts = float(
        exchange_position.get('contracts', 0) or
        exchange_position.get('positionAmt', 0) or
        0
    )
    
    # 提取价格
    entry_price = float(
        exchange_position.get('entryPrice', 0) or
        exchange_position.get('avgPrice', 0) or
        0
    )
    current_price = float(
        exchange_position.get('markPrice', 0) or
        exchange_position.get('lastPrice', 0) or
        entry_price
    )
    
    # 提取合约面值
    contract_value = float(
        exchange_position.get('contractSize', 1) or
        exchange_position.get('contractValue', 1) or
        1
    )
    
    # 提取方向
    side = exchange_position.get('side', '')
    if not side:
        side = 'long' if contracts > 0 else 'short'
    
    # 提取杠杆
    pos_leverage = int(exchange_position.get('leverage', leverage) or leverage)
    
    return PositionInfo(
        symbol=exchange_position.get('symbol', ''),
        side=side.lower(),
        qty=abs(contracts),
        entry_price=entry_price,
        current_price=current_price,
        contract_value=contract_value,
        leverage=pos_leverage
    )
