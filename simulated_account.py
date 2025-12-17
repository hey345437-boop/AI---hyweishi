# simulated_account.py
# 模拟账户模型 - 标准金融字段定义
#
# 严格区分以下概念：
# - wallet_balance: 钱包余额（静态，充值-提现+已实现盈亏）
# - unrealized_pnl: 未实现盈亏（所有持仓的浮动盈亏之和）
# - equity: 动态权益 = wallet_balance + unrealized_pnl
# - used_margin: 已用保证金 = sum(position.margin)
# - free_margin: 可用保证金 = equity - used_margin

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class SimulatedPosition:
    """
    模拟持仓
    
    Attributes:
        symbol: 交易对
        side: 方向 ('long' or 'short')
        qty: 持仓数量
        entry_price: 入场均价
        leverage: 杠杆倍数
        contract_value: 合约面值（SWAP合约用）
    """
    symbol: str
    side: str  # 'long' or 'short'
    qty: float
    entry_price: float
    leverage: int = 1
    contract_value: float = 1.0
    signal_type: Optional[str] = None
    created_at: int = 0
    
    @property
    def notional_value(self) -> float:
        """名义价值 = qty × entry_price × contract_value"""
        return abs(self.qty) * self.entry_price * self.contract_value
    
    @property
    def margin(self) -> float:
        """占用保证金 = notional_value / leverage"""
        if self.leverage <= 0:
            return self.notional_value
        return self.notional_value / self.leverage
    
    def calc_unrealized_pnl(self, current_price: float) -> float:
        """
        计算未实现盈亏
        
        Args:
            current_price: 当前市场价格
        
        Returns:
            未实现盈亏（正数为盈利，负数为亏损）
        """
        if self.side == 'long':
            return (current_price - self.entry_price) * abs(self.qty) * self.contract_value
        else:  # short
            return (self.entry_price - current_price) * abs(self.qty) * self.contract_value


@dataclass
class AccountState:
    """
    账户状态快照
    
    标准金融字段：
    - wallet_balance: 钱包余额（静态）
    - unrealized_pnl: 未实现盈亏
    - equity: 动态权益
    - used_margin: 已用保证金
    - free_margin: 可用保证金
    """
    wallet_balance: float  # 钱包余额
    unrealized_pnl: float  # 未实现盈亏
    used_margin: float     # 已用保证金
    
    @property
    def equity(self) -> float:
        """动态权益 = wallet_balance + unrealized_pnl"""
        return self.wallet_balance + self.unrealized_pnl
    
    @property
    def free_margin(self) -> float:
        """可用保证金 = equity - used_margin"""
        return self.equity - self.used_margin
    
    def to_dict(self) -> Dict[str, float]:
        """转换为字典"""
        return {
            'wallet_balance': self.wallet_balance,
            'unrealized_pnl': self.unrealized_pnl,
            'equity': self.equity,
            'used_margin': self.used_margin,
            'free_margin': self.free_margin
        }
    
    def __str__(self) -> str:
        return (
            f"AccountState(wallet=${self.wallet_balance:.2f}, "
            f"upnl=${self.unrealized_pnl:.2f}, "
            f"equity=${self.equity:.2f}, "
            f"used_margin=${self.used_margin:.2f}, "
            f"free_margin=${self.free_margin:.2f})"
        )


class SimulatedAccount:
    """
    模拟账户
    
    管理钱包余额、持仓、保证金计算等。
    
    核心公式：
    - equity = wallet_balance + unrealized_pnl
    - used_margin = sum(position.margin for all positions)
    - free_margin = equity - used_margin
    
    风控规则：
    - 开仓前检查：free_margin >= required_margin
    - 持仓限制：used_margin <= equity × max_margin_ratio
    """
    
    DEFAULT_INITIAL_BALANCE = 200.0
    DEFAULT_MAX_MARGIN_RATIO = 0.10  # 最大保证金占比 10%
    
    def __init__(
        self,
        initial_balance: float = DEFAULT_INITIAL_BALANCE,
        max_margin_ratio: float = DEFAULT_MAX_MARGIN_RATIO,
        default_leverage: int = 50
    ):
        """
        初始化模拟账户
        
        Args:
            initial_balance: 初始余额
            max_margin_ratio: 最大保证金占比（相对于权益）
            default_leverage: 默认杠杆倍数
        """
        self._wallet_balance = initial_balance
        self._positions: Dict[str, SimulatedPosition] = {}  # key: "symbol:side"
        self._max_margin_ratio = max_margin_ratio
        self._default_leverage = default_leverage
        self._realized_pnl_total = 0.0  # 累计已实现盈亏
        
        logger.info(
            f"SimulatedAccount 初始化 | "
            f"初始余额: ${initial_balance:.2f} | "
            f"最大保证金占比: {max_margin_ratio*100:.1f}% | "
            f"默认杠杆: {default_leverage}x"
        )

    
    # ==================== 属性 ====================
    
    @property
    def wallet_balance(self) -> float:
        """钱包余额（静态余额）"""
        return self._wallet_balance
    
    @property
    def positions(self) -> Dict[str, SimulatedPosition]:
        """所有持仓"""
        return self._positions.copy()
    
    def calc_unrealized_pnl(self, prices: Dict[str, float]) -> float:
        """
        计算所有持仓的未实现盈亏
        
        Args:
            prices: 当前价格字典 {symbol: price}
        
        Returns:
            总未实现盈亏
        """
        total_upnl = 0.0
        for key, pos in self._positions.items():
            price = prices.get(pos.symbol, pos.entry_price)
            total_upnl += pos.calc_unrealized_pnl(price)
        return total_upnl
    
    def calc_used_margin(self) -> float:
        """计算已用保证金"""
        return sum(pos.margin for pos in self._positions.values())
    
    def get_state(self, prices: Dict[str, float]) -> AccountState:
        """
        获取账户状态快照
        
        Args:
            prices: 当前价格字典 {symbol: price}
        
        Returns:
            AccountState 账户状态
        """
        unrealized_pnl = self.calc_unrealized_pnl(prices)
        used_margin = self.calc_used_margin()
        
        return AccountState(
            wallet_balance=self._wallet_balance,
            unrealized_pnl=unrealized_pnl,
            used_margin=used_margin
        )
    
    def get_equity(self, prices: Dict[str, float]) -> float:
        """获取动态权益"""
        return self._wallet_balance + self.calc_unrealized_pnl(prices)
    
    def get_free_margin(self, prices: Dict[str, float]) -> float:
        """获取可用保证金"""
        equity = self.get_equity(prices)
        used_margin = self.calc_used_margin()
        return equity - used_margin

    
    # ==================== 风控检查 ====================
    
    def check_can_open_position(
        self,
        required_margin: float,
        prices: Dict[str, float]
    ) -> tuple:
        """
        检查是否可以开仓
        
        风控规则：
        1. free_margin >= required_margin（有足够可用保证金）
        2. (used_margin + required_margin) <= equity × max_margin_ratio
        
        Args:
            required_margin: 开仓所需保证金
            prices: 当前价格字典
        
        Returns:
            (can_open: bool, reason: str)
        """
        state = self.get_state(prices)
        
        # 检查 1: 可用保证金是否足够
        if state.free_margin < required_margin:
            return False, (
                f"可用保证金不足: free_margin=${state.free_margin:.2f} < "
                f"required=${required_margin:.2f}"
            )
        
        # 检查 2: 是否超过最大保证金占比
        new_used_margin = state.used_margin + required_margin
        max_allowed_margin = state.equity * self._max_margin_ratio
        
        if new_used_margin > max_allowed_margin:
            return False, (
                f"超过最大保证金限制: "
                f"(used=${state.used_margin:.2f} + new=${required_margin:.2f}) = "
                f"${new_used_margin:.2f} > "
                f"max=${max_allowed_margin:.2f} "
                f"(equity=${state.equity:.2f} × {self._max_margin_ratio*100:.0f}%)"
            )
        
        return True, "风控通过"
    
    def check_margin_ratio(self, prices: Dict[str, float]) -> tuple:
        """
        检查当前保证金占比
        
        Returns:
            (is_ok: bool, ratio: float, message: str)
        """
        state = self.get_state(prices)
        
        if state.equity <= 0:
            return False, 1.0, "权益为零或负数"
        
        ratio = state.used_margin / state.equity
        is_ok = ratio <= self._max_margin_ratio
        
        message = (
            f"保证金占比: {ratio*100:.2f}% "
            f"(used=${state.used_margin:.2f} / equity=${state.equity:.2f}) "
            f"{'✅ OK' if is_ok else '❌ 超限'}"
        )
        
        return is_ok, ratio, message

    
    # ==================== 持仓操作 ====================
    
    def open_position(
        self,
        symbol: str,
        side: str,
        qty: float,
        entry_price: float,
        leverage: Optional[int] = None,
        contract_value: float = 1.0,
        signal_type: Optional[str] = None
    ) -> tuple:
        """
        开仓
        
        Args:
            symbol: 交易对
            side: 方向 ('long' or 'short')
            qty: 数量
            entry_price: 入场价格
            leverage: 杠杆倍数
            contract_value: 合约面值
            signal_type: 信号类型
        
        Returns:
            (success: bool, message: str, position: SimulatedPosition or None)
        """
        if leverage is None:
            leverage = self._default_leverage
        
        # 创建持仓对象
        position = SimulatedPosition(
            symbol=symbol,
            side=side.lower(),
            qty=qty,
            entry_price=entry_price,
            leverage=leverage,
            contract_value=contract_value,
            signal_type=signal_type,
            created_at=int(datetime.now().timestamp())
        )
        
        # 计算所需保证金
        required_margin = position.margin
        
        # 风控检查（使用入场价格作为当前价格）
        prices = {symbol: entry_price}
        can_open, reason = self.check_can_open_position(required_margin, prices)
        
        if not can_open:
            logger.warning(f"开仓被拒绝: {reason}")
            return False, reason, None
        
        # 扣除保证金（从 wallet_balance 转移到 used_margin）
        # 注意：开仓不改变 wallet_balance，只是"冻结"了一部分资金
        # wallet_balance 只在平仓实现盈亏时才变化
        
        # 添加持仓
        key = f"{symbol}:{side.lower()}"
        
        if key in self._positions:
            # 加仓：更新均价和数量
            existing = self._positions[key]
            total_qty = existing.qty + qty
            avg_price = (
                (existing.qty * existing.entry_price + qty * entry_price) / total_qty
            )
            existing.qty = total_qty
            existing.entry_price = avg_price
            logger.info(
                f"加仓成功: {symbol} {side} | "
                f"新增 {qty} @ {entry_price} | "
                f"总量 {total_qty} @ {avg_price:.4f}"
            )
        else:
            self._positions[key] = position
            logger.info(
                f"开仓成功: {symbol} {side} | "
                f"数量 {qty} @ {entry_price} | "
                f"保证金 ${required_margin:.2f}"
            )
        
        return True, "开仓成功", self._positions[key]

    
    def close_position(
        self,
        symbol: str,
        side: str,
        qty: float,
        close_price: float,
        fee: float = 0.0
    ) -> tuple:
        """
        平仓
        
        Args:
            symbol: 交易对
            side: 方向
            qty: 平仓数量
            close_price: 平仓价格
            fee: 手续费
        
        Returns:
            (success: bool, realized_pnl: float, message: str)
        """
        key = f"{symbol}:{side.lower()}"
        
        if key not in self._positions:
            return False, 0.0, f"持仓不存在: {key}"
        
        position = self._positions[key]
        
        if qty > position.qty:
            return False, 0.0, f"平仓数量超过持仓: {qty} > {position.qty}"
        
        # 计算已实现盈亏
        realized_pnl = position.calc_unrealized_pnl(close_price) * (qty / position.qty)
        realized_pnl -= fee  # 扣除手续费
        
        # 更新钱包余额（已实现盈亏）
        self._wallet_balance += realized_pnl
        self._realized_pnl_total += realized_pnl
        
        # 更新或删除持仓
        if qty >= position.qty:
            # 全部平仓
            del self._positions[key]
            logger.info(
                f"全部平仓: {symbol} {side} | "
                f"数量 {qty} @ {close_price} | "
                f"已实现盈亏 ${realized_pnl:.2f}"
            )
        else:
            # 部分平仓
            position.qty -= qty
            logger.info(
                f"部分平仓: {symbol} {side} | "
                f"平仓 {qty} @ {close_price} | "
                f"剩余 {position.qty} | "
                f"已实现盈亏 ${realized_pnl:.2f}"
            )
        
        return True, realized_pnl, "平仓成功"
    
    def get_position(self, symbol: str, side: str) -> Optional[SimulatedPosition]:
        """获取指定持仓"""
        key = f"{symbol}:{side.lower()}"
        return self._positions.get(key)
    
    def has_position(self, symbol: str, side: Optional[str] = None) -> bool:
        """检查是否有持仓"""
        if side:
            key = f"{symbol}:{side.lower()}"
            return key in self._positions
        else:
            return any(
                pos.symbol == symbol 
                for pos in self._positions.values()
            )

    
    # ==================== 数据库同步 ====================
    
    def sync_from_db(self, db_bridge) -> None:
        """
        从数据库同步账户状态
        
        Args:
            db_bridge: 数据库桥接模块
        """
        # 同步余额
        paper_balance = db_bridge.get_paper_balance()
        if paper_balance:
            # 使用 equity 作为 wallet_balance（简化处理）
            self._wallet_balance = float(paper_balance.get('equity', self._wallet_balance) or self._wallet_balance)
        
        # 同步持仓
        self._positions.clear()
        
        # 主仓位
        paper_positions = db_bridge.get_paper_positions()
        if paper_positions:
            for pos_key, pos_data in paper_positions.items():
                symbol = pos_data.get('symbol', pos_key.split(':')[0] if ':' in pos_key else pos_key)
                side = pos_data.get('pos_side', pos_data.get('side', 'long'))
                qty = float(pos_data.get('qty', 0) or 0)
                entry_price = float(pos_data.get('entry_price', 0) or 0)
                
                if qty > 0 and entry_price > 0:
                    key = f"{symbol}:{side}"
                    self._positions[key] = SimulatedPosition(
                        symbol=symbol,
                        side=side,
                        qty=qty,
                        entry_price=entry_price,
                        leverage=self._default_leverage,
                        signal_type=pos_data.get('signal_type')
                    )
        
        # 对冲仓位
        hedge_positions = db_bridge.get_hedge_positions()
        if hedge_positions:
            for hedge_pos in hedge_positions:
                symbol = hedge_pos.get('symbol', '')
                side = hedge_pos.get('pos_side', 'long')
                qty = float(hedge_pos.get('qty', 0) or 0)
                entry_price = float(hedge_pos.get('entry_price', 0) or 0)
                
                if qty > 0 and entry_price > 0:
                    # 对冲仓位使用不同的 key 前缀
                    key = f"hedge:{symbol}:{side}"
                    self._positions[key] = SimulatedPosition(
                        symbol=symbol,
                        side=side,
                        qty=qty,
                        entry_price=entry_price,
                        leverage=self._default_leverage,
                        signal_type=hedge_pos.get('signal_type')
                    )
        
        logger.debug(f"从数据库同步: wallet=${self._wallet_balance:.2f}, positions={len(self._positions)}")
    
    def sync_to_db(self, db_bridge, prices: Dict[str, float]) -> None:
        """
        同步账户状态到数据库
        
        Args:
            db_bridge: 数据库桥接模块
            prices: 当前价格字典
        """
        state = self.get_state(prices)
        
        # 更新余额
        # 注意：数据库的 available 对应 free_margin
        db_bridge.update_paper_balance(
            equity=state.equity,
            available=state.free_margin
        )
        
        logger.debug(f"同步到数据库: equity=${state.equity:.2f}, free_margin=${state.free_margin:.2f}")

    
    # ==================== 日志输出 ====================
    
    def print_status(self, prices: Dict[str, float]) -> str:
        """
        打印账户状态
        
        Args:
            prices: 当前价格字典
        
        Returns:
            状态字符串
        """
        state = self.get_state(prices)
        
        lines = [
            "=" * 60,
            "📊 模拟账户状态",
            "=" * 60,
            f"💰 钱包余额 (Wallet Balance): ${state.wallet_balance:.2f}",
            f"📈 未实现盈亏 (Unrealized PnL): ${state.unrealized_pnl:.2f}",
            f"💎 动态权益 (Equity): ${state.equity:.2f}",
            f"🔒 已用保证金 (Used Margin): ${state.used_margin:.2f}",
            f"✅ 可用保证金 (Free Margin): ${state.free_margin:.2f}",
            "-" * 60,
        ]
        
        # 保证金占比
        if state.equity > 0:
            ratio = state.used_margin / state.equity * 100
            max_ratio = self._max_margin_ratio * 100
            status = "✅" if ratio <= max_ratio else "❌"
            lines.append(f"📊 保证金占比: {ratio:.2f}% / {max_ratio:.0f}% {status}")
        
        # 持仓列表
        if self._positions:
            lines.append("-" * 60)
            lines.append("📋 持仓列表:")
            for key, pos in self._positions.items():
                price = prices.get(pos.symbol, pos.entry_price)
                upnl = pos.calc_unrealized_pnl(price)
                lines.append(
                    f"  {pos.symbol} {pos.side.upper()} | "
                    f"qty={pos.qty:.6f} @ {pos.entry_price:.2f} | "
                    f"margin=${pos.margin:.2f} | "
                    f"upnl=${upnl:.2f}"
                )
        else:
            lines.append("📋 无持仓")
        
        lines.append("=" * 60)
        
        return "\n".join(lines)


# ==================== 便捷函数 ====================

def create_simulated_account(
    initial_balance: float = 200.0,
    max_margin_ratio: float = 0.10,
    default_leverage: int = 50
) -> SimulatedAccount:
    """
    创建模拟账户
    
    Args:
        initial_balance: 初始余额
        max_margin_ratio: 最大保证金占比
        default_leverage: 默认杠杆
    
    Returns:
        SimulatedAccount 实例
    """
    return SimulatedAccount(
        initial_balance=initial_balance,
        max_margin_ratio=max_margin_ratio,
        default_leverage=default_leverage
    )


def calc_required_margin(
    notional_value: float,
    leverage: int
) -> float:
    """
    计算所需保证金
    
    Args:
        notional_value: 名义价值
        leverage: 杠杆倍数
    
    Returns:
        所需保证金
    """
    if leverage <= 0:
        return notional_value
    return notional_value / leverage
