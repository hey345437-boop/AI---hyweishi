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
# ============================================================================
"""
对冲仓位管理模块

实现以下核心逻辑：
1. 差值止盈逃生 - 有对冲仓时，净收益率达标全仓平仓
2. 硬止盈 - 仅主仓时，本金盈利达标平仓
3. 顺势解对冲 - 新信号与主仓同向时，平掉对冲仓
4. 对冲转正 - 主仓不存在但有对冲仓时，对冲仓转为主仓
5. 对冲开仓 - 新信号与主仓相反时，开对冲仓（最多2个）
"""
import time
import logging
from typing import Dict, Any, Optional, Tuple, List

logger = logging.getLogger(__name__)


class HedgeManager:
    """对冲仓位管理器"""
    
    MAX_HEDGE_COUNT = 2  # 单币种最多2个对冲仓
    
    def __init__(self, db_bridge_module, leverage: int = 20, 
                 hard_tp_pct: float = 0.02, hedge_tp_pct: float = 0.005,
                 custom_stop_loss_pct: float = 0.02):
        """
        初始化对冲管理器
        
        Args:
            db_bridge_module: db_bridge 模块引用
            leverage: 杠杆倍数
            hard_tp_pct: 硬止盈比例（仅主仓时）
            hedge_tp_pct: 对冲止盈比例（有对冲仓时）
            custom_stop_loss_pct: 自定义策略止损比例
        """
        self.db = db_bridge_module
        self.leverage = leverage
        self.hard_tp_pct = hard_tp_pct
        self.hedge_tp_pct = hedge_tp_pct
        self.custom_stop_loss_pct = custom_stop_loss_pct
    
    def update_params(self, leverage: int = None, hard_tp_pct: float = None, 
                      hedge_tp_pct: float = None, custom_stop_loss_pct: float = None):
        """更新交易参数"""
        if leverage is not None:
            self.leverage = leverage
        if hard_tp_pct is not None:
            self.hard_tp_pct = hard_tp_pct
        if hedge_tp_pct is not None:
            self.hedge_tp_pct = hedge_tp_pct
        if custom_stop_loss_pct is not None:
            self.custom_stop_loss_pct = custom_stop_loss_pct
    
    def get_main_position(self, symbol: str) -> Optional[Dict[str, Any]]:
        """获取主仓位"""
        # 尝试获取 long 和 short 方向的持仓
        long_pos = self.db.get_paper_position(symbol, 'long')
        short_pos = self.db.get_paper_position(symbol, 'short')
        
        # 返回有持仓的那个
        if long_pos and long_pos.get('qty', 0) > 0:
            return long_pos
        if short_pos and short_pos.get('qty', 0) > 0:
            return short_pos
        return None
    
    def get_hedge_positions(self, symbol: str) -> List[Dict[str, Any]]:
        """获取对冲仓位列表"""
        return self.db.get_hedge_positions(symbol)
    
    def calculate_position_pnl(self, pos: Dict[str, Any], current_price: float) -> float:
        """计算单个仓位的浮动盈亏"""
        entry_price = pos.get('entry_price', 0)
        qty = pos.get('qty', 0)
        pos_side = pos.get('pos_side', 'long')
        
        if entry_price <= 0 or qty <= 0:
            return 0.0
        
        # 计算持仓价值
        position_value = qty * entry_price
        
        if pos_side == 'long':
            pnl = (current_price - entry_price) / entry_price * position_value
        else:  # short
            pnl = (entry_price - current_price) / entry_price * position_value
        
        return pnl
    
    def check_hard_take_profit(self, symbol: str, current_price: float) -> Tuple[bool, float, str]:
        """
        检查硬止盈条件（仅主仓时）
        
        Returns:
            (should_close, pnl, reason)
        """
        main_pos = self.get_main_position(symbol)
        hedge_list = self.get_hedge_positions(symbol)
        
        # 只有主仓且无对冲仓时才检查硬止盈
        if not main_pos or hedge_list:
            return False, 0.0, ""
        
        # 计算主仓浮盈（带杠杆）
        pnl = self.calculate_position_pnl(main_pos, current_price)
        
        # 计算本金收益率（不带杠杆）
        # 修复：硬止盈应该基于本金收益率，而不是杠杆收益率
        # 本金收益率 = (当前价格 - 入场价格) / 入场价格
        entry_price = main_pos.get('entry_price', 0)
        pos_side = main_pos.get('pos_side', 'long')
        
        if entry_price <= 0:
            return False, 0.0, ""
        
        # 计算本金收益率（不带杠杆）
        if pos_side == 'long':
            roi = (current_price - entry_price) / entry_price
        else:  # short
            roi = (entry_price - current_price) / entry_price
        
        # 检查是否达到硬止盈条件（基于本金收益率）
        if roi >= self.hard_tp_pct:
            reason = f"硬止盈触发: ROI={roi*100:.2f}% >= {self.hard_tp_pct*100:.1f}%"
            return True, pnl, reason
        
        return False, 0.0, ""
    
    def check_stop_loss(self, symbol: str, current_price: float) -> Tuple[bool, float, str]:
        """
        检查止损条件（自定义策略使用）
        
        Returns:
            (should_close, pnl, reason)
        """
        main_pos = self.get_main_position(symbol)
        
        # 没有主仓则不检查
        if not main_pos:
            return False, 0.0, ""
        
        # 计算主仓浮盈
        pnl = self.calculate_position_pnl(main_pos, current_price)
        
        # 计算本金收益率
        entry_price = main_pos.get('entry_price', 0)
        pos_side = main_pos.get('pos_side', 'long')
        
        if entry_price <= 0:
            return False, 0.0, ""
        
        # 计算本金收益率（不带杠杆）
        if pos_side == 'long':
            roi = (current_price - entry_price) / entry_price
        else:  # short
            roi = (entry_price - current_price) / entry_price
        
        # 检查是否达到止损条件（亏损超过阈值）
        if roi <= -self.custom_stop_loss_pct:
            reason = f"止损触发: ROI={roi*100:.2f}% <= -{self.custom_stop_loss_pct*100:.1f}%"
            return True, pnl, reason
        
        return False, 0.0, ""
    
    def check_hedge_escape(self, symbol: str, current_price: float) -> Tuple[bool, float, str]:
        """
        检查差值止盈逃生条件（有对冲仓时）
        
        Returns:
            (should_close_all, net_pnl, reason)
        """
        main_pos = self.get_main_position(symbol)
        hedge_list = self.get_hedge_positions(symbol)
        
        # 必须同时有主仓和对冲仓
        if not main_pos or not hedge_list:
            return False, 0.0, ""
        
        # 计算主仓浮盈
        main_pnl = self.calculate_position_pnl(main_pos, current_price)
        
        # 计算所有对冲仓总浮盈
        hedge_pnl = 0.0
        total_hedge_value = 0.0
        for hedge_pos in hedge_list:
            hedge_pnl += self.calculate_position_pnl(hedge_pos, current_price)
            total_hedge_value += hedge_pos.get('qty', 0) * hedge_pos.get('entry_price', 0)
        
        # 计算净浮盈
        net_pnl = main_pnl + hedge_pnl
        
        # 计算总本金（杠杆前）
        main_value = main_pos.get('qty', 0) * main_pos.get('entry_price', 0)
        total_margin = (main_value + total_hedge_value) / self.leverage
        
        if total_margin <= 0:
            return False, 0.0, ""
        
        # 计算净收益率
        net_roi = net_pnl / total_margin
        
        # 检查是否达到对冲止盈条件
        if net_roi >= self.hedge_tp_pct:
            reason = f"对冲逃生触发: Net ROI={net_roi*100:.2f}% >= {self.hedge_tp_pct*100:.2f}%"
            return True, net_pnl, reason
        
        return False, 0.0, ""
    
    def check_smart_unhook(self, symbol: str, signal_action: str) -> Tuple[bool, str]:
        """
        检查顺势解对冲条件
        
        Args:
            symbol: 交易对
            signal_action: 新信号方向 ('LONG' 或 'SHORT')
        
        Returns:
            (should_unhook, reason)
        """
        main_pos = self.get_main_position(symbol)
        hedge_list = self.get_hedge_positions(symbol)
        
        # 必须同时有主仓和对冲仓
        if not main_pos or not hedge_list:
            return False, ""
        
        main_side = main_pos.get('pos_side', 'long').upper()
        
        # 新信号方向 == 主仓方向 -> 解对冲
        if signal_action.upper() == main_side:
            reason = f"顺势解对冲: 新信号{signal_action}与主仓{main_side}同向"
            return True, reason
        
        return False, ""
    
    def check_hedge_inheritance(self, symbol: str, signal_action: str) -> Tuple[bool, Dict[str, Any], str]:
        """
        检查对冲转正条件
        
        Args:
            symbol: 交易对
            signal_action: 新信号方向 ('LONG' 或 'SHORT')
        
        Returns:
            (should_inherit, hedge_pos_to_inherit, reason)
        """
        main_pos = self.get_main_position(symbol)
        hedge_list = self.get_hedge_positions(symbol)
        
        # 主仓不存在但有对冲仓
        if main_pos or not hedge_list:
            return False, {}, ""
        
        # 查找与新信号同向的对冲仓
        for hedge_pos in hedge_list:
            hedge_side = hedge_pos.get('pos_side', 'long').upper()
            if signal_action.upper() == hedge_side:
                reason = f"对冲转正: 遗留对冲仓{hedge_side}与新信号{signal_action}同向"
                return True, hedge_pos, reason
        
        return False, {}, ""
    
    def can_open_hedge(self, symbol: str) -> Tuple[bool, str]:
        """
        检查是否可以开对冲仓
        
        Returns:
            (can_open, reason)
        """
        hedge_count = self.db.count_hedge_positions(symbol)
        
        if hedge_count >= self.MAX_HEDGE_COUNT:
            return False, f"对冲熔断: {symbol}已有{hedge_count}个对冲仓，达到上限{self.MAX_HEDGE_COUNT}"
        
        return True, ""
    
    def execute_close_all(self, symbol: str, current_price: float, 
                          exchange=None, run_mode: str = 'paper') -> Tuple[bool, float, str]:
        """
        执行全仓平仓（主仓 + 所有对冲仓）
        
        Returns:
            (success, total_pnl, message)
        """
        main_pos = self.get_main_position(symbol)
        hedge_list = self.get_hedge_positions(symbol)
        
        total_pnl = 0.0
        
        # 平主仓
        if main_pos:
            pnl = self.calculate_position_pnl(main_pos, current_price)
            total_pnl += pnl
            
            if run_mode == 'live' and exchange:
                try:
                    # 执行真实平仓
                    side = 'sell' if main_pos.get('pos_side') == 'long' else 'buy'
                    exchange.create_order(
                        symbol=symbol,
                        side=side,
                        amount=main_pos.get('qty', 0),
                        order_type='market',
                        params={'reduceOnly': True, 'posSide': main_pos.get('pos_side')}
                    )
                except Exception as e:
                    logger.error(f"平主仓失败: {e}")
                    return False, 0.0, f"平主仓失败: {e}"
            
            # 删除数据库记录
            self.db.delete_paper_position(symbol, main_pos.get('pos_side'))
            
            # 更新模拟账户余额（平仓后释放保证金 + 盈亏）
            if run_mode != 'live':
                try:
                    paper_bal = self.db.get_paper_balance()
                    current_equity = float(paper_bal.get('equity', 0) or 0)
                    current_available = float(paper_bal.get('available', 0) or 0)
                    
                    # 计算释放的保证金
                    position_value = main_pos.get('qty', 0) * main_pos.get('entry_price', 0)
                    margin_released = position_value / self.leverage
                    
                    # 更新余额：equity += pnl, available += margin + pnl
                    new_equity = current_equity + pnl
                    new_available = current_available + margin_released + pnl
                    
                    self.db.update_paper_balance(equity=new_equity, available=new_available)
                    logger.info(f"模拟账户更新: 释放保证金=${margin_released:.2f}, PnL=${pnl:.2f}")
                except Exception as e:
                    logger.error(f"更新模拟余额失败: {e}")
            
            # 记录交易历史（用于计算胜率等统计）
            try:
                entry_price = main_pos.get('entry_price', 0)
                qty = main_pos.get('qty', 0)
                created_at = main_pos.get('created_at', 0)
                hold_time = int(time.time() * 1000 - created_at) // 1000 if created_at > 0 else 0
                self.db.insert_trade_history(
                    symbol=symbol,
                    pos_side=main_pos.get('pos_side', 'long'),
                    entry_price=entry_price,
                    exit_price=current_price,
                    qty=qty,
                    pnl=pnl,
                    hold_time=hold_time,
                    note='主仓止盈'
                )
            except Exception as e:
                logger.error(f"记录交易历史失败: {e}")
            
            logger.info(f"已平主仓 {symbol} {main_pos.get('pos_side')} | PnL: ${pnl:.2f}")
        
        # 平所有对冲仓
        for hedge_pos in hedge_list:
            pnl = self.calculate_position_pnl(hedge_pos, current_price)
            total_pnl += pnl
            
            if run_mode == 'live' and exchange:
                try:
                    side = 'sell' if hedge_pos.get('pos_side') == 'long' else 'buy'
                    exchange.create_order(
                        symbol=symbol,
                        side=side,
                        amount=hedge_pos.get('qty', 0),
                        order_type='market',
                        params={'reduceOnly': True, 'posSide': hedge_pos.get('pos_side')}
                    )
                except Exception as e:
                    logger.error(f"平对冲仓失败: {e}")
            
            # 删除数据库记录
            self.db.delete_hedge_position(hedge_pos.get('id'))
            
            # 更新模拟账户余额（平仓后释放保证金 + 盈亏）
            if run_mode != 'live':
                try:
                    paper_bal = self.db.get_paper_balance()
                    current_equity = float(paper_bal.get('equity', 0) or 0)
                    current_available = float(paper_bal.get('available', 0) or 0)
                    
                    # 计算释放的保证金
                    position_value = hedge_pos.get('qty', 0) * hedge_pos.get('entry_price', 0)
                    margin_released = position_value / self.leverage
                    
                    # 更新余额
                    new_equity = current_equity + pnl
                    new_available = current_available + margin_released + pnl
                    
                    self.db.update_paper_balance(equity=new_equity, available=new_available)
                except Exception as e:
                    logger.error(f"更新模拟余额失败: {e}")
            
            # 记录交易历史（用于计算胜率等统计）
            try:
                entry_price = hedge_pos.get('entry_price', 0)
                qty = hedge_pos.get('qty', 0)
                created_at = hedge_pos.get('created_at', 0)
                hold_time = int(time.time() * 1000 - created_at) // 1000 if created_at > 0 else 0
                self.db.insert_trade_history(
                    symbol=symbol,
                    pos_side=hedge_pos.get('pos_side', 'short'),
                    entry_price=entry_price,
                    exit_price=current_price,
                    qty=qty,
                    pnl=pnl,
                    hold_time=hold_time,
                    note='对冲仓止盈'
                )
            except Exception as e:
                logger.error(f"记录交易历史失败: {e}")
            
            logger.info(f"已平对冲仓 {symbol} {hedge_pos.get('pos_side')} | PnL: ${pnl:.2f}")
        
        return True, total_pnl, f"全仓平仓完成 | 总PnL: ${total_pnl:.2f}"
    
    def execute_unhook(self, symbol: str, current_price: float,
                       exchange=None, run_mode: str = 'paper') -> Tuple[bool, float, str]:
        """
        执行解对冲（平掉所有对冲仓，保留主仓）
        
        Returns:
            (success, hedge_pnl, message)
        """
        hedge_list = self.get_hedge_positions(symbol)
        
        if not hedge_list:
            return True, 0.0, "无对冲仓需要平仓"
        
        total_hedge_pnl = 0.0
        
        for hedge_pos in hedge_list:
            pnl = self.calculate_position_pnl(hedge_pos, current_price)
            total_hedge_pnl += pnl
            
            if run_mode == 'live' and exchange:
                try:
                    side = 'sell' if hedge_pos.get('pos_side') == 'long' else 'buy'
                    exchange.create_order(
                        symbol=symbol,
                        side=side,
                        amount=hedge_pos.get('qty', 0),
                        order_type='market',
                        params={'reduceOnly': True, 'posSide': hedge_pos.get('pos_side')}
                    )
                except Exception as e:
                    logger.error(f"解对冲失败: {e}")
            
            self.db.delete_hedge_position(hedge_pos.get('id'))
            
            # 更新模拟账户余额（平仓后释放保证金 + 盈亏）
            if run_mode != 'live':
                try:
                    paper_bal = self.db.get_paper_balance()
                    current_equity = float(paper_bal.get('equity', 0) or 0)
                    current_available = float(paper_bal.get('available', 0) or 0)
                    
                    position_value = hedge_pos.get('qty', 0) * hedge_pos.get('entry_price', 0)
                    margin_released = position_value / self.leverage
                    
                    new_equity = current_equity + pnl
                    new_available = current_available + margin_released + pnl
                    
                    self.db.update_paper_balance(equity=new_equity, available=new_available)
                except Exception as e:
                    logger.error(f"更新模拟余额失败: {e}")
        
        return True, total_hedge_pnl, f"解对冲完成 | 平仓{len(hedge_list)}个对冲仓 | PnL: ${total_hedge_pnl:.2f}"
    
    def execute_inheritance(self, symbol: str, hedge_pos: Dict[str, Any]) -> Tuple[bool, str]:
        """
        执行对冲转正（将对冲仓转为主仓）
        
        Returns:
            (success, message)
        """
        try:
            # 将对冲仓数据写入主仓表
            self.db.update_paper_position(
                symbol=symbol,
                pos_side=hedge_pos.get('pos_side'),
                qty=hedge_pos.get('qty'),
                entry_price=hedge_pos.get('entry_price'),
                unrealized_pnl=hedge_pos.get('unrealized_pnl', 0),
                updated_at=int(time.time())
            )
            
            # 删除对冲仓记录
            self.db.delete_hedge_position(hedge_pos.get('id'))
            
            return True, f"对冲转正完成: {symbol} {hedge_pos.get('pos_side')} @ ${hedge_pos.get('entry_price'):.4f}"
        except Exception as e:
            logger.error(f"对冲转正失败: {e}")
            return False, f"对冲转正失败: {e}"
    
    def open_hedge_position(self, symbol: str, pos_side: str, qty: float, 
                            entry_price: float, signal_type: str = None) -> Tuple[bool, str]:
        """
        开对冲仓
        
        Returns:
            (success, message)
        """
        can_open, reason = self.can_open_hedge(symbol)
        if not can_open:
            return False, reason
        
        try:
            hedge_id = self.db.add_hedge_position(
                symbol=symbol,
                pos_side=pos_side,
                qty=qty,
                entry_price=entry_price,
                signal_type=f"HEDGE_{signal_type}" if signal_type else "HEDGE"
            )
            return True, f"开对冲仓成功: {symbol} {pos_side} @ ${entry_price:.4f} | ID={hedge_id}"
        except Exception as e:
            logger.error(f"开对冲仓失败: {e}")
            return False, f"开对冲仓失败: {e}"
