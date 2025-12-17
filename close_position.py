# close_position.py
# 一键平仓功能实现

import logging
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

logger = logging.getLogger(__name__)


@dataclass
class ClosePositionResult:
    """单个持仓平仓结果"""
    symbol: str
    pos_side: str        # 'long' or 'short'
    before_sz: float
    after_sz: float
    order_id: Optional[str] = None
    status: str = "pending"  # 'success', 'failed', 'skipped'
    error: Optional[str] = None


@dataclass
class CloseAllResult:
    """一键平仓总结果"""
    success: bool = True
    cancelled_orders: List[str] = field(default_factory=list)
    closed_positions: List[ClosePositionResult] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'success': self.success,
            'cancelled_orders': self.cancelled_orders,
            'closed_positions': [
                {
                    'symbol': p.symbol,
                    'pos_side': p.pos_side,
                    'before_sz': p.before_sz,
                    'after_sz': p.after_sz,
                    'order_id': p.order_id,
                    'status': p.status,
                    'error': p.error
                }
                for p in self.closed_positions
            ],
            'errors': self.errors
        }


def close_all_positions(
    adapter: Any,
    symbol: Optional[str] = None
) -> CloseAllResult:
    """
    一键平仓
    
    流程:
    1. cancel_all_open_orders(symbol) - 撤销所有未成交委托
    2. fetch_positions(symbol) - 获取当前持仓
    3. 对每个 posSide 创建 reduceOnly 市价单
    4. 验证持仓为零
    
    Args:
        adapter: OKX 适配器
        symbol: 指定交易对，None 表示所有
    
    Returns:
        CloseAllResult 结构化结果
    """
    result = CloseAllResult()
    
    try:
        # 确保适配器已初始化
        if adapter.exchange is None:
            adapter.initialize()
        
        # Step 1: 撤销所有未成交委托
        logger.info(f"🔻 Step 1: 撤销未成交委托 (symbol={symbol or 'all'})")
        try:
            cancelled = _cancel_all_open_orders(adapter, symbol)
            result.cancelled_orders = cancelled
            logger.info(f"✅ 已撤销 {len(cancelled)} 个委托")
        except Exception as e:
            error_msg = f"撤销委托失败: {str(e)}"
            logger.error(f"❌ {error_msg}")
            result.errors.append(error_msg)
            # 继续尝试平仓
        
        # Step 2: 获取当前持仓
        logger.info(f"🔻 Step 2: 获取当前持仓")
        try:
            positions = _fetch_positions_with_size(adapter, symbol)
            logger.info(f"✅ 获取到 {len(positions)} 个持仓")
        except Exception as e:
            error_msg = f"获取持仓失败: {str(e)}"
            logger.error(f"❌ {error_msg}")
            result.errors.append(error_msg)
            result.success = False
            return result
        
        if not positions:
            logger.info("ℹ️ 无持仓需要平仓")
            return result
        
        # Step 3: 对每个持仓创建平仓订单
        logger.info(f"🔻 Step 3: 创建平仓订单")
        for pos in positions:
            pos_result = _close_single_position(adapter, pos)
            result.closed_positions.append(pos_result)
            
            if pos_result.status == "failed":
                result.success = False
                result.errors.append(pos_result.error or "Unknown error")
        
        # Step 4: 验证持仓为零
        logger.info(f"🔻 Step 4: 验证持仓")
        try:
            remaining = _fetch_positions_with_size(adapter, symbol)
            for pos in remaining:
                # 检查是否有残仓
                pos_sz = abs(float(pos.get('contracts', 0) or pos.get('positionAmt', 0) or 0))
                if pos_sz > 0:
                    pos_symbol = pos.get('symbol', 'unknown')
                    pos_side = pos.get('side', 'unknown')
                    logger.warning(f"⚠️ 残仓警告: {pos_symbol} {pos_side} 剩余 {pos_sz}")
                    
                    # 更新对应的结果
                    for pr in result.closed_positions:
                        if pr.symbol == pos_symbol and pr.pos_side == pos_side:
                            pr.after_sz = pos_sz
        except Exception as e:
            logger.warning(f"⚠️ 验证持仓失败: {e}")
        
        logger.info(f"✅ 一键平仓完成: success={result.success}, closed={len(result.closed_positions)}")
        return result
        
    except Exception as e:
        error_msg = f"一键平仓异常: {str(e)}"
        logger.error(f"❌ {error_msg}")
        result.errors.append(error_msg)
        result.success = False
        return result


def _cancel_all_open_orders(adapter: Any, symbol: Optional[str]) -> List[str]:
    """撤销所有未成交委托"""
    cancelled_ids = []
    
    try:
        # 获取未成交委托
        if symbol:
            normalized = adapter.normalize_symbol(symbol)
            open_orders = adapter.exchange.fetch_open_orders(normalized)
        else:
            open_orders = adapter.exchange.fetch_open_orders()
        
        # 逐个撤销
        for order in open_orders:
            try:
                order_id = order.get('id')
                order_symbol = order.get('symbol')
                adapter.exchange.cancel_order(order_id, order_symbol)
                cancelled_ids.append(order_id)
                logger.debug(f"已撤销委托: {order_id}")
            except Exception as e:
                logger.warning(f"撤销委托 {order.get('id')} 失败: {e}")
    
    except Exception as e:
        logger.warning(f"获取未成交委托失败: {e}")
    
    return cancelled_ids


def _fetch_positions_with_size(adapter: Any, symbol: Optional[str]) -> List[Dict]:
    """获取有持仓的仓位"""
    if symbol:
        symbols = [symbol]
    else:
        symbols = None
    
    positions = adapter.fetch_positions(symbols)
    
    # 过滤有持仓的
    active = []
    for pos in positions:
        contracts = abs(float(pos.get('contracts', 0) or pos.get('positionAmt', 0) or 0))
        if contracts > 0:
            active.append(pos)
    
    return active


def _close_single_position(adapter: Any, position: Dict) -> ClosePositionResult:
    """平仓单个持仓"""
    symbol = position.get('symbol', '')
    side = position.get('side', '').lower()
    contracts = abs(float(position.get('contracts', 0) or position.get('positionAmt', 0) or 0))
    
    result = ClosePositionResult(
        symbol=symbol,
        pos_side=side,
        before_sz=contracts,
        after_sz=0,
        status="pending"
    )
    
    if contracts <= 0:
        result.status = "skipped"
        result.error = "No position to close"
        return result
    
    try:
        # 确定平仓方向
        # long 持仓 -> sell 平仓
        # short 持仓 -> buy 平仓
        close_side = 'sell' if side == 'long' else 'buy'
        
        # 构建参数
        params = {
            'reduceOnly': True,
            'posSide': side  # OKX 双向持仓需要指定 posSide
        }
        
        logger.info(f"📤 平仓: {symbol} {side} {contracts} -> {close_side}")
        
        # 创建平仓订单
        order = adapter.create_order(
            symbol=symbol,
            side=close_side,
            amount=contracts,
            order_type='market',
            params=params,
            reduce_only=True
        )
        
        result.order_id = order.get('id')
        result.status = "success"
        result.after_sz = 0
        
        logger.info(f"✅ 平仓成功: {symbol} {side} order_id={result.order_id}")
        
    except Exception as e:
        result.status = "failed"
        result.error = str(e)
        result.after_sz = contracts  # 平仓失败，持仓不变
        logger.error(f"❌ 平仓失败: {symbol} {side} - {e}")
    
    return result


def format_close_result_table(result: CloseAllResult) -> str:
    """
    格式化平仓结果为表格
    
    格式:
    | Symbol | PosSide | Before | After | OrderID | Status |
    """
    lines = []
    lines.append("=" * 80)
    lines.append("一键平仓结果")
    lines.append("=" * 80)
    lines.append(f"{'Symbol':<20} {'PosSide':<8} {'Before':<10} {'After':<10} {'Status':<10} {'OrderID':<20}")
    lines.append("-" * 80)
    
    for pos in result.closed_positions:
        order_id = pos.order_id[:16] + "..." if pos.order_id and len(pos.order_id) > 16 else (pos.order_id or "-")
        lines.append(
            f"{pos.symbol:<20} {pos.pos_side:<8} {pos.before_sz:<10.4f} "
            f"{pos.after_sz:<10.4f} {pos.status:<10} {order_id:<20}"
        )
    
    lines.append("-" * 80)
    lines.append(f"撤销委托数: {len(result.cancelled_orders)}")
    lines.append(f"平仓数: {len(result.closed_positions)}")
    lines.append(f"总体状态: {'成功' if result.success else '失败'}")
    
    if result.errors:
        lines.append(f"错误: {'; '.join(result.errors[:3])}")
    
    lines.append("=" * 80)
    
    return "\n".join(lines)


def parse_close_result_table(table_str: str) -> Optional[CloseAllResult]:
    """
    从格式化的表格字符串解析平仓结果（round-trip）
    
    Args:
        table_str: format_close_result_table 生成的表格字符串
    
    Returns:
        CloseAllResult 或 None（解析失败时）
    """
    try:
        lines = table_str.strip().split('\n')
        
        result = CloseAllResult()
        positions = []
        
        # 查找数据行（在表头和分隔线之后）
        data_started = False
        for line in lines:
            line = line.strip()
            
            # 跳过空行和分隔线
            if not line or line.startswith('=') or line.startswith('-'):
                if data_started:
                    data_started = False  # 数据区域结束
                continue
            
            # 跳过标题行
            if '一键平仓结果' in line:
                continue
            
            # 检测表头
            if 'Symbol' in line and 'PosSide' in line:
                data_started = True
                continue
            
            # 解析元数据行
            if '撤销委托数:' in line:
                count = int(line.split(':')[1].strip())
                result.cancelled_orders = [''] * count
                continue
            
            if '平仓数:' in line:
                continue
            
            if '总体状态:' in line:
                status_str = line.split(':')[1].strip()
                result.success = '成功' in status_str
                continue
            
            if '错误:' in line:
                error_str = line.split(':', 1)[1].strip()
                result.errors = [e.strip() for e in error_str.split(';')]
                continue
            
            # 解析数据行
            if data_started:
                parts = line.split()
                if len(parts) >= 5:
                    pos = ClosePositionResult(
                        symbol=parts[0],
                        pos_side=parts[1],
                        before_sz=float(parts[2]),
                        after_sz=float(parts[3]),
                        status=parts[4],
                        order_id=parts[5] if len(parts) > 5 and parts[5] != '-' else None
                    )
                    positions.append(pos)
        
        result.closed_positions = positions
        return result
        
    except Exception as e:
        logger.error(f"Failed to parse close result table: {e}")
        return None
