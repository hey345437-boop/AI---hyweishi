# order_size_calculator.py
# 订单数量计算器 - 正确计算 OKX SWAP 合约张数

import logging
import math
from dataclasses import dataclass
from typing import Dict, Optional, Any

logger = logging.getLogger(__name__)


@dataclass
class InstrumentInfo:
    """合约信息"""
    symbol: str
    ct_val: float      # 合约面值 (Contract Value)
    lot_sz: float      # 最小张数 (Lot Size)
    min_sz: float      # 最小下单量
    tick_sz: float     # 价格精度
    ct_mult: float = 1.0  # 合约乘数


@dataclass
class OrderSizeResult:
    """订单数量计算结果"""
    is_valid: bool
    contracts: float       # 合约张数 (sz)
    base_qty: float        # 基础数量
    margin: float          # 保证金
    notional: float        # 名义价值
    error: Optional[str] = None
    log_line: str = ""     # 可复核日志行


class OrderSizeCalculator:
    """
    订单数量计算器
    
    公式:
    - margin = equity * risk_pct
    - notional = margin * leverage
    - base_qty = notional / price
    - contracts = notional / (price * ctVal)
    - contracts = floor(contracts / lotSz) * lotSz
    """
    
    def __init__(self, exchange_adapter: Any = None):
        """
        初始化订单数量计算器
        
        Args:
            exchange_adapter: 交易所适配器，用于获取合约信息
        """
        self.exchange_adapter = exchange_adapter
        self._instrument_cache: Dict[str, InstrumentInfo] = {}
    
    def get_instrument_info(self, symbol: str) -> Optional[InstrumentInfo]:
        """
        获取合约信息（带缓存）
        
        Args:
            symbol: 交易对，如 'BTC/USDT:USDT'
        
        Returns:
            InstrumentInfo 或 None
        """
        # 检查缓存
        if symbol in self._instrument_cache:
            return self._instrument_cache[symbol]
        
        if self.exchange_adapter is None:
            logger.warning(f"No exchange adapter, cannot fetch instrument info for {symbol}")
            return None
        
        try:
            # 确保交易所已初始化
            if self.exchange_adapter.exchange is None:
                self.exchange_adapter.initialize()
            
            # 从 ccxt markets 获取合约信息
            markets = self.exchange_adapter.exchange.markets
            normalized_symbol = self.exchange_adapter.normalize_symbol(symbol)
            
            if normalized_symbol not in markets:
                logger.error(f"Symbol {normalized_symbol} not found in markets")
                return None
            
            market = markets[normalized_symbol]
            
            # 提取合约参数
            # OKX SWAP 合约参数位置
            ct_val = float(market.get('contractSize', 1.0))
            lot_sz = float(market.get('precision', {}).get('amount', 1.0))
            min_sz = float(market.get('limits', {}).get('amount', {}).get('min', 1.0))
            tick_sz = float(market.get('precision', {}).get('price', 0.01))
            ct_mult = float(market.get('contractMultiplier', 1.0) or 1.0)
            
            # 如果 lot_sz 是精度而不是最小张数，需要转换
            # ccxt 有时返回的是小数位数而不是实际值
            if lot_sz < 0.0001:
                lot_sz = 1.0
            
            info = InstrumentInfo(
                symbol=normalized_symbol,
                ct_val=ct_val,
                lot_sz=lot_sz,
                min_sz=min_sz,
                tick_sz=tick_sz,
                ct_mult=ct_mult
            )
            
            # 缓存
            self._instrument_cache[symbol] = info
            self._instrument_cache[normalized_symbol] = info
            
            logger.debug(f"Instrument info for {symbol}: ctVal={ct_val}, lotSz={lot_sz}, minSz={min_sz}")
            return info
            
        except Exception as e:
            logger.error(f"Failed to get instrument info for {symbol}: {e}")
            return None
    
    def calculate(
        self,
        symbol: str,
        equity: float,
        risk_pct: float,
        leverage: int,
        price: float,
        use_paper_equity: bool = False
    ) -> OrderSizeResult:
        """
        计算订单数量
        
        Args:
            symbol: 交易对
            equity: 账户净值 (USDT)
            risk_pct: 风险比例 (如 0.03 表示 3%)
            leverage: 杠杆倍数
            price: 当前价格
            use_paper_equity: 是否使用模拟账户净值（实盘测试模式）
        
        Returns:
            OrderSizeResult 包含计算结果和可复核日志
        """
        # 参数验证
        if price <= 0:
            return OrderSizeResult(
                is_valid=False,
                contracts=0,
                base_qty=0,
                margin=0,
                notional=0,
                error="价格不能为零或负数",
                log_line=f"[size] ERROR: price={price} <= 0"
            )
        
        if equity <= 0:
            return OrderSizeResult(
                is_valid=False,
                contracts=0,
                base_qty=0,
                margin=0,
                notional=0,
                error="净值不能为零或负数",
                log_line=f"[size] ERROR: equity={equity} <= 0"
            )
        
        # 获取合约信息
        inst_info = self.get_instrument_info(symbol)
        if inst_info is None:
            return OrderSizeResult(
                is_valid=False,
                contracts=0,
                base_qty=0,
                margin=0,
                notional=0,
                error=f"无法获取 {symbol} 的合约信息",
                log_line=f"[size] ERROR: instrument info missing for {symbol}"
            )
        
        # 核心计算公式
        margin = equity * risk_pct
        notional = margin * leverage
        base_qty = notional / price
        
        # 计算合约张数
        # contracts = notional / (price * ctVal)
        # 对于 OKX SWAP，ctVal 是每张合约的面值（以 USD 计）
        contracts_raw = notional / (price * inst_info.ct_val)
        
        # 按 lotSz 向下取整
        contracts = math.floor(contracts_raw / inst_info.lot_sz) * inst_info.lot_sz
        
        # 生成可复核日志行
        log_line = (
            f"[size] equity={equity:.2f} risk={risk_pct:.4f} lev={leverage} "
            f"margin={margin:.2f} notional={notional:.2f} price={price:.4f} "
            f"ctVal={inst_info.ct_val} lot={inst_info.lot_sz} "
            f"-> sz={contracts} (contracts) / base={base_qty:.6f}"
        )
        
        # 验证最小下单量
        if contracts < inst_info.min_sz:
            return OrderSizeResult(
                is_valid=False,
                contracts=contracts,
                base_qty=base_qty,
                margin=margin,
                notional=notional,
                error=f"计算张数 {contracts} < 最小张数 {inst_info.min_sz}",
                log_line=log_line + f" [REJECTED: sz < minSz({inst_info.min_sz})]"
            )
        
        return OrderSizeResult(
            is_valid=True,
            contracts=contracts,
            base_qty=base_qty,
            margin=margin,
            notional=notional,
            error=None,
            log_line=log_line
        )
    
    def clear_cache(self, symbol: str = None):
        """
        清除合约信息缓存
        
        Args:
            symbol: 指定交易对，None 表示清除全部
        """
        if symbol is None:
            self._instrument_cache.clear()
            logger.info("Cleared all instrument cache")
        elif symbol in self._instrument_cache:
            del self._instrument_cache[symbol]
            logger.info(f"Cleared instrument cache for {symbol}")
