"""
AI 交易桥接模块

负责将 AI 决策转换为实际交易指令
核心安全逻辑：
1. 主界面必须是实盘模式 (run_mode == 'live')
2. AI 托管必须启用 (ai_takeover == True)
3. 两个条件同时满足才能执行真实交易，否则只进行虚拟交易
"""

import logging
import time
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class AITradeMode(Enum):
    """AI 交易模式"""
    SIMULATION = "simulation"  # 纯模拟（虚拟资金）
    LIVE = "live"              # 实盘交易


@dataclass
class AITradeSignal:
    """AI 交易信号 - 僧侣型交易员格式"""
    agent_name: str
    symbol: str
    signal: str  # open_long / open_short / close_long / close_short / hold / wait
    confidence: float  # 0-100
    entry_price: Optional[float] = None
    entry_type: str = "market"  # market / limit
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    rr_estimate: Optional[float] = None  # 风险回报比
    position_size_usd: float = 0.0  # 仓位金额 (USD)
    leverage: int = 1  # 杠杆倍数 1-20
    evidence: List[str] = None  # 证据列表
    reasoning: str = ""
    decision_id: Optional[int] = None  # P1: 关联的决策 ID（审计追踪）
    
    def __post_init__(self):
        if self.evidence is None:
            self.evidence = []


@dataclass
class AITradeResult:
    """AI 交易执行结果"""
    success: bool
    mode: AITradeMode
    order_id: Optional[str] = None
    message: str = ""
    executed_price: Optional[float] = None
    executed_amount: Optional[float] = None


class AITradeBridge:
    """
    AI 交易桥接器
    
    负责：
    1. 检查交易权限（主界面模式 + AI 托管状态）
    2. 执行真实交易或虚拟交易
    3. 风控检查
    """
    
    def __init__(self, db_config: Dict = None):
        self.db_config = db_config
        self._okx_client = None
        self._db_bridge = None
    
    def _get_db_bridge(self):
        """懒加载 db_bridge"""
        if self._db_bridge is None:
            try:
                import db_bridge
                self._db_bridge = db_bridge
            except ImportError:
                logger.error("无法导入 db_bridge 模块")
        return self._db_bridge
    
    def _get_okx_client(self):
        """懒加载 OKX 客户端"""
        if self._okx_client is None:
            try:
                from okx_client import get_okx_client
                self._okx_client = get_okx_client()
            except Exception as e:
                logger.error(f"无法获取 OKX 客户端: {e}")
        return self._okx_client
    
    def get_main_run_mode(self) -> str:
        """
        获取主界面的运行模式
        
        返回: 'live' 或 'paper'
        """
        db = self._get_db_bridge()
        if not db:
            return 'paper'
        
        try:
            bot_config = db.get_bot_config(self.db_config)
            if bot_config:
                return bot_config.get('run_mode', 'paper')
        except Exception as e:
            logger.error(f"获取运行模式失败: {e}")
        
        return 'paper'
    
    def is_live_trading_allowed(self, ai_takeover: bool = False) -> bool:
        """
        检查是否允许 AI 进行实盘交易
        
        条件：
        1. 主界面 run_mode == 'live'
        2. ai_takeover == True
        
        返回: True 允许实盘，False 只能模拟
        """
        main_mode = self.get_main_run_mode()
        
        # 主界面必须是实盘模式
        if main_mode != 'live':
            logger.info(f"[AIBridge] 主界面为 {main_mode} 模式，AI 只能模拟交易")
            return False
        
        # AI 托管必须启用
        if not ai_takeover:
            logger.info("[AIBridge] AI 托管未启用，只能模拟交易")
            return False
        
        logger.info("[AIBridge] 实盘交易已授权")
        return True
    
    def get_current_trade_mode(self, ai_takeover: bool = False) -> AITradeMode:
        """获取当前 AI 交易模式"""
        if self.is_live_trading_allowed(ai_takeover):
            return AITradeMode.LIVE
        return AITradeMode.SIMULATION
    
    def execute_signal(
        self,
        signal: AITradeSignal,
        ai_takeover: bool = False,
        dry_run: bool = False
    ) -> AITradeResult:
        """
        执行 AI 交易信号
        
        参数:
            signal: AI 交易信号
            ai_takeover: AI 托管是否启用
            dry_run: 是否只模拟不执行
        
        返回:
            AITradeResult 执行结果
        """
        # 确定交易模式
        trade_mode = self.get_current_trade_mode(ai_takeover)
        
        # hold/wait 信号不执行
        if signal.signal in ['hold', 'wait']:
            return AITradeResult(
                success=True,
                mode=trade_mode,
                message=f"{signal.signal.upper()} 信号，不执行交易"
            )
        
        # 基本参数验证（不是风控，只是确保参数有效）
        validation = self._validate_signal_params(signal)
        if not validation['valid']:
            logger.warning(f"[AIBridge] {signal.agent_name} {signal.symbol} 参数无效: {validation['reason']}")
            return AITradeResult(
                success=False,
                mode=trade_mode,
                message=f"参数无效: {validation['reason']}"
            )
        
        # 根据模式执行
        if trade_mode == AITradeMode.LIVE and not dry_run:
            return self._execute_live_trade(signal)
        else:
            return self._execute_simulation_trade(signal)
    
    def _validate_signal_params(
        self, 
        signal: AITradeSignal
    ) -> Dict[str, Any]:
        """
        验证信号参数（不是风控，只是确保参数有效）
        
        风控逻辑完全由 AI 根据提示词自己决定！
        这里只检查技术上必须的参数：
        1. 杠杆范围 1-20（交易所限制）
        2. 仓位金额 > 0（否则无法下单）
        """
        # hold/wait 信号直接通过
        if signal.signal in ['hold', 'wait']:
            return {'valid': True, 'reason': ''}
        
        # 开仓信号检查
        if signal.signal.startswith('open_'):
            # 杠杆范围（交易所技术限制）
            if signal.leverage > 20:
                return {
                    'valid': False,
                    'reason': f"杠杆 {signal.leverage}x 超过交易所限制 20x"
                }
            
            if signal.leverage < 1:
                signal.leverage = 1  # 自动修正为 1
            
            # 仓位金额必须 > 0（否则无法下单）
            if signal.position_size_usd <= 0:
                return {
                    'valid': False,
                    'reason': "仓位金额必须大于 0"
                }
        
        return {'valid': True, 'reason': ''}
    
    def _execute_live_trade(self, signal: AITradeSignal) -> AITradeResult:
        """
        执行实盘交易
        
        通过 OKX 客户端下单
        """
        logger.info(f"[AIBridge] 执行实盘交易: {signal.agent_name} {signal.signal} {signal.symbol} "
                   f"{signal.position_size_usd}USD {signal.leverage}x")
        
        try:
            okx = self._get_okx_client()
            if not okx:
                return AITradeResult(
                    success=False,
                    mode=AITradeMode.LIVE,
                    message="OKX 客户端不可用"
                )
            
            # 获取账户余额检查
            balance = self._get_available_balance()
            if balance <= 0:
                return AITradeResult(
                    success=False,
                    mode=AITradeMode.LIVE,
                    message="可用余额不足"
                )
            
            # 检查仓位金额是否超过余额
            if signal.position_size_usd > balance:
                return AITradeResult(
                    success=False,
                    mode=AITradeMode.LIVE,
                    message=f"仓位 {signal.position_size_usd}USD 超过可用余额 {balance:.2f}USD"
                )
            
            # 确定方向 (open_long/open_short/close_long/close_short)
            if signal.signal == 'open_long':
                side, pos_side, reduce_only = 'buy', 'long', False
            elif signal.signal == 'open_short':
                side, pos_side, reduce_only = 'sell', 'short', False
            elif signal.signal == 'close_long':
                side, pos_side, reduce_only = 'sell', 'long', True
            elif signal.signal == 'close_short':
                side, pos_side, reduce_only = 'buy', 'short', True
            else:
                return AITradeResult(
                    success=False,
                    mode=AITradeMode.LIVE,
                    message=f"未知信号类型: {signal.signal}"
                )
            
            # 🔥 设置杠杆（在下单前，仅开仓时）
            if signal.leverage > 1 and not reduce_only:
                try:
                    okx.set_leverage(
                        symbol=signal.symbol,
                        leverage=signal.leverage,
                        margin_mode='cross',
                        pos_side=pos_side
                    )
                    logger.info(f"[AIBridge] 杠杆已设置: {signal.symbol} {signal.leverage}x")
                except Exception as e:
                    logger.warning(f"[AIBridge] 设置杠杆失败: {e}，使用默认杠杆继续")
            
            # 使用 AI 指定的仓位金额
            trade_amount = signal.position_size_usd
            
            # 下单参数
            order_params = {
                'posSide': pos_side,  # long 或 short
                'reduceOnly': reduce_only
            }
            
            # 限价单需要价格
            order_price = None
            if signal.entry_type == 'limit':
                if signal.entry_price is None:
                    return AITradeResult(
                        success=False,
                        mode=AITradeMode.LIVE,
                        message="限价单必须指定入场价格 (entry_price)"
                    )
                order_price = signal.entry_price
                logger.info(f"[AIBridge] 限价单: {signal.symbol} @ {order_price}")
            
            # 调用 create_order（不是 place_order）
            result = okx.create_order(
                symbol=signal.symbol,
                side=side,
                order_type=signal.entry_type,
                amount=trade_amount,
                price=order_price,
                params=order_params
            )
            
            # ccxt 返回的订单 ID 字段是 'id'，不是 'ordId'
            order_id = result.get('id') or result.get('ordId')
            if result and order_id:
                # 记录到数据库
                self._record_ai_trade(signal, result, AITradeMode.LIVE)
                
                order_type_str = "限价" if signal.entry_type == 'limit' else "市价"
                price_str = f" @ {order_price}" if order_price else ""
                
                return AITradeResult(
                    success=True,
                    mode=AITradeMode.LIVE,
                    order_id=order_id,
                    message=f"实盘{order_type_str}单成功: {order_id}{price_str} ({signal.leverage}x, RR:{signal.rr_estimate or 'N/A'})",
                    executed_price=order_price,
                    executed_amount=trade_amount
                )
            else:
                return AITradeResult(
                    success=False,
                    mode=AITradeMode.LIVE,
                    message=f"下单失败: {result}"
                )
        
        except Exception as e:
            logger.error(f"[AIBridge] 实盘交易异常: {e}")
            return AITradeResult(
                success=False,
                mode=AITradeMode.LIVE,
                message=f"交易异常: {str(e)}"
            )
    
    def _execute_simulation_trade(self, signal: AITradeSignal) -> AITradeResult:
        """
        执行模拟交易
        
        写入 arena.db 的虚拟持仓表
        """
        logger.info(f"[AIBridge] 执行模拟交易: {signal.agent_name} {signal.signal} {signal.symbol} "
                   f"{signal.position_size_usd}USD {signal.leverage}x")
        
        try:
            from ai_db_manager import get_ai_db_manager
            db = get_ai_db_manager()
            
            # 获取当前价格（使用信号中的价格或获取实时价格）
            price = signal.entry_price or self._get_current_price(signal.symbol)
            if not price:
                return AITradeResult(
                    success=False,
                    mode=AITradeMode.SIMULATION,
                    message="无法获取当前价格"
                )
            
            # 检查当前持仓
            open_positions = db.get_open_positions(signal.agent_name)
            
            # 检查是否已有同币种同方向的持仓
            has_same_position = False
            for pos in open_positions:
                if pos['symbol'] == signal.symbol:
                    if signal.signal == 'open_long' and pos['side'] == 'long':
                        has_same_position = True
                        break
                    elif signal.signal == 'open_short' and pos['side'] == 'short':
                        has_same_position = True
                        break
            
            if has_same_position:
                logger.info(f"[AIBridge] {signal.agent_name} 已有 {signal.symbol} 同方向持仓，跳过开仓")
                return AITradeResult(
                    success=True,
                    mode=AITradeMode.SIMULATION,
                    message=f"已有同方向持仓，跳过"
                )
            
            if signal.signal == 'open_long':
                # 平掉空仓
                for pos in open_positions:
                    if pos['symbol'] == signal.symbol and pos['side'] == 'short':
                        pnl = db.close_position(pos['id'], price)
                        logger.info(f"[AIBridge] 平空仓 PnL: {pnl:.4f}")
                
                # 开多仓
                pos_id = db.open_position(
                    agent_name=signal.agent_name,
                    symbol=signal.symbol,
                    side='long',
                    entry_price=price,
                    qty=signal.position_size_usd,
                    leverage=signal.leverage,
                    signal_type=f"AI:{signal.agent_name}",
                    decision_id=signal.decision_id
                )
                
            elif signal.signal == 'open_short':
                # 平掉多仓
                for pos in open_positions:
                    if pos['symbol'] == signal.symbol and pos['side'] == 'long':
                        pnl = db.close_position(pos['id'], price)
                        logger.info(f"[AIBridge] 平多仓 PnL: {pnl:.4f}")
                
                # 开空仓
                pos_id = db.open_position(
                    agent_name=signal.agent_name,
                    symbol=signal.symbol,
                    side='short',
                    entry_price=price,
                    qty=signal.position_size_usd,
                    leverage=signal.leverage,
                    signal_type=f"AI:{signal.agent_name}",
                    decision_id=signal.decision_id
                )
                
            elif signal.signal == 'close_long':
                # 平多仓
                for pos in open_positions:
                    if pos['symbol'] == signal.symbol and pos['side'] == 'long':
                        pnl = db.close_position(pos['id'], price)
                        logger.info(f"[AIBridge] 平多仓 PnL: {pnl:.4f}")
                        
            elif signal.signal == 'close_short':
                # 平空仓
                for pos in open_positions:
                    if pos['symbol'] == signal.symbol and pos['side'] == 'short':
                        pnl = db.close_position(pos['id'], price)
                        logger.info(f"[AIBridge] 平空仓 PnL: {pnl:.4f}")
            
            return AITradeResult(
                success=True,
                mode=AITradeMode.SIMULATION,
                order_id=f"SIM-{int(time.time()*1000)}",
                message=f"模拟交易成功 @ {price:.2f} ({signal.leverage}x, RR:{signal.rr_estimate or 'N/A'})",
                executed_price=price,
                executed_amount=signal.position_size_usd
            )
        
        except Exception as e:
            logger.error(f"[AIBridge] 模拟交易异常: {e}")
            return AITradeResult(
                success=False,
                mode=AITradeMode.SIMULATION,
                message=f"模拟交易异常: {str(e)}"
            )
    
    def _get_available_balance(self) -> float:
        """获取可用余额"""
        try:
            okx = self._get_okx_client()
            if okx:
                balance = okx.get_balance()
                if balance:
                    return float(balance.get('availBal', 0) or balance.get('available', 0))
        except Exception as e:
            logger.error(f"获取余额失败: {e}")
        return 0.0
    
    def _get_current_price(self, symbol: str) -> Optional[float]:
        """获取当前价格"""
        try:
            # 尝试从 Market API 获取
            from ai_indicators import get_data_source
            ds = get_data_source()
            ohlcv = ds.fetch_ohlcv(symbol, '1m', 1)
            if ohlcv:
                return ohlcv[-1][4]  # 收盘价
        except Exception as e:
            logger.error(f"获取价格失败: {e}")
        return None
    
    def _record_ai_trade(self, signal: AITradeSignal, result: Dict, mode: AITradeMode):
        """记录 AI 交易到数据库"""
        try:
            db = self._get_db_bridge()
            if db:
                db.create_order(
                    db_config=self.db_config,
                    symbol=signal.symbol,
                    side='buy' if signal.signal == 'BUY' else 'sell',
                    pos_side='long' if signal.signal == 'BUY' else 'short',
                    amount=signal.position_size_usd,
                    order_type='market',
                    run_mode=mode.value,
                    signal_reason=f"AI:{signal.agent_name} conf:{signal.confidence:.0%}"
                )
        except Exception as e:
            logger.error(f"记录交易失败: {e}")


# 全局实例
_bridge: Optional[AITradeBridge] = None


def get_ai_trade_bridge(db_config: Dict = None) -> AITradeBridge:
    """获取全局 AI 交易桥接器"""
    global _bridge
    if _bridge is None:
        _bridge = AITradeBridge(db_config)
    return _bridge


def execute_ai_signal(
    signal: AITradeSignal,
    ai_takeover: bool = False,
    db_config: Dict = None
) -> AITradeResult:
    """
    便捷函数：执行 AI 交易信号
    
    参数:
        signal: AI 交易信号
        ai_takeover: AI 托管是否启用
        db_config: 数据库配置
    
    返回:
        AITradeResult 执行结果
    """
    bridge = get_ai_trade_bridge(db_config)
    return bridge.execute_signal(signal, ai_takeover)


def get_ai_trade_mode(ai_takeover: bool = False, db_config: Dict = None) -> AITradeMode:
    """
    便捷函数：获取当前 AI 交易模式
    
    返回:
        AITradeMode.LIVE 或 AITradeMode.SIMULATION
    """
    bridge = get_ai_trade_bridge(db_config)
    return bridge.get_current_trade_mode(ai_takeover)
