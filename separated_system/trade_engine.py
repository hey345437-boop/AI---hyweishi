import os
import sys
import io
import time
import json
import logging
import asyncio
from datetime import datetime
from typing import Dict, Any, List
from concurrent.futures import ThreadPoolExecutor, as_completed

# ============ 加载 .env 环境变量 ============
# 必须在其他模块导入之前执行，确保加密密钥等配置正确加载
try:
    from dotenv import load_dotenv
    # 从项目根目录加载 .env 文件
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env_path = os.path.join(project_root, '.env')
    if os.path.exists(env_path):
        load_dotenv(env_path)
except ImportError:
    pass  # dotenv 未安装，跳过

# ============ Windows UTF-8 编码修复 ============
# 必须在所有其他操作之前执行
if sys.platform.startswith('win'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except AttributeError:
        sys.stdout = io.TextIOWrapper(
            sys.stdout.buffer, encoding='utf-8', errors='replace', line_buffering=True
        )
        sys.stderr = io.TextIOWrapper(
            sys.stderr.buffer, encoding='utf-8', errors='replace', line_buffering=True
        )

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 🔥 辅助函数：获取当前分钟需要处理的周期（收线确认模式）
def get_due_timeframes(current_minute: int, timeframes: List[str]) -> List[str]:
    """
    返回已收盘的周期列表（收线确认模式）
    
    规则（整分扫描，00秒触发）：
    - 每个分钟00秒：必扫1m（上一分钟的K线已收盘）
    - 若minute % 3 == 0：额外扫3m（3m K线刚收盘）
    - 若minute % 5 == 0：额外扫5m
    - 若minute % 15 == 0：额外扫15m
    - 若minute % 30 == 0：额外扫30m
    - 若minute == 0：额外扫1h
    
    与59秒模式的区别：
    - 59秒模式：在K线收盘前1秒触发，使用"即将收盘"的K线
    - 00秒模式：在K线收盘后触发，使用"已收盘"的K线（对齐TradingView）
    """
    due_tfs = []
    
    # 1m周期总是需要处理（每个分钟的00秒触发，上一分钟K线已收盘）
    if '1m' in timeframes:
        due_tfs.append('1m')
    
    # 3m周期：当前分钟是0,3,6,...分（3m K线刚收盘）
    if '3m' in timeframes and current_minute % 3 == 0:
        due_tfs.append('3m')
    
    # 5m周期：当前分钟是0,5,10,...分（5m K线刚收盘）
    if '5m' in timeframes and current_minute % 5 == 0:
        due_tfs.append('5m')
    
    # 15m周期：当前分钟是0,15,30,45分（15m K线刚收盘）
    if '15m' in timeframes and current_minute % 15 == 0:
        due_tfs.append('15m')
    
    # 30m周期：当前分钟是0,30分（30m K线刚收盘）
    if '30m' in timeframes and current_minute % 30 == 0:
        due_tfs.append('30m')
    
    # 1h周期：当前分钟是0分（1h K线刚收盘）
    if '1h' in timeframes and current_minute == 0:
        due_tfs.append('1h')
    
    return due_tfs

from config import (
    OKX_API_KEY, OKX_API_SECRET, OKX_API_PASSPHRASE,
    OKX_MARKET_TYPE, OKX_TD_MODE, OKX_SANDBOX,
    TIMEFRAME, SCAN_INTERVAL_SEC,
    EXIT_ON_FATAL, MAX_CYCLE_ERRORS
)
from db_bridge import (
    init_db, get_engine_status, get_control_flags,
    get_bot_config, set_control_flags, update_engine_status,
    insert_performance_metrics, upsert_ohlcv, insert_signal_event,
    get_paper_balance, update_paper_balance,
    get_paper_positions, get_paper_position, update_paper_position,
    delete_paper_position, add_paper_fill,
    load_decrypted_credentials, debug_db_identity,
    # 🔥 新增：对冲仓位管理
    get_hedge_positions, add_hedge_position, delete_hedge_position,
    delete_hedge_positions_by_symbol, count_hedge_positions,
    get_trading_params,
    # P2修复: 信号缓存持久化
    get_signal_cache, set_signal_cache, load_all_signal_cache, clear_signal_cache_db
)
from logging_utils import setup_logger, get_logger, render_scan_block, render_idle_block, render_risk_check
from exchange_adapters.factory import ExchangeAdapterFactory
from market_data_provider import MarketDataProvider

# P1修复: 导入风控模块
from risk_control import RiskControlModule, RiskControlConfig

# 🔥 导入对冲管理器
import db_bridge as db_bridge_module
from separated_system.hedge_manager import HedgeManager

# 🔥 导入K线时间处理工具
from candle_time_utils import (
    get_closed_candles,
    get_latest_closed_candle,
    is_candle_closed,
    get_timeframe_ms,
    normalize_daily_timeframe,
    format_scan_summary,
    utc_ms_to_beijing_str,
    get_closed_candle_tracker,
    ClosedCandleSignalTracker
)

# 🔥 导入策略注册表（从UI选择的策略）
from strategy_registry import (
    get_strategy_registry,
    validate_and_fallback_strategy
)

# 🔥 K线数据缓存（防止重复拉取）
_ohlcv_cache: Dict[str, Any] = {}  # {(symbol, timeframe): {'data': df, 'ts': timestamp}}
_OHLCV_CACHE_TTL = 30  # 缓存有效期（秒）

def get_cached_ohlcv(symbol: str, timeframe: str) -> Any:
    """获取缓存的K线数据"""
    key = (symbol, timeframe)
    if key in _ohlcv_cache:
        cache_entry = _ohlcv_cache[key]
        if time.time() - cache_entry['ts'] < _OHLCV_CACHE_TTL:
            return cache_entry['data']
    return None

def set_cached_ohlcv(symbol: str, timeframe: str, data: Any) -> None:
    """设置K线数据缓存"""
    key = (symbol, timeframe)
    _ohlcv_cache[key] = {'data': data, 'ts': time.time()}

def clear_ohlcv_cache() -> None:
    """清除K线缓存"""
    global _ohlcv_cache
    _ohlcv_cache.clear()

# ============ P0修复: 信号去重全局变量 ============
# 记录最后处理的K线时间戳，防止同一根K线重复触发信号
# P2修复: 现在同时持久化到数据库，重启后不丢失
_last_signal_candle = {}  # {(symbol, timeframe, action): candle_timestamp}
_signal_cache_loaded = False  # 标记是否已从数据库加载

def load_signal_cache_from_db():
    """P2修复: 从数据库加载信号缓存到内存"""
    global _last_signal_candle, _signal_cache_loaded
    if not _signal_cache_loaded:
        try:
            _last_signal_candle = load_all_signal_cache()
            _signal_cache_loaded = True
        except Exception:
            pass  # 数据库未初始化时忽略

def should_execute_signal(symbol: str, timeframe: str, action: str, candle_time: int) -> bool:
    """
    P0修复: 信号去重 - 检查是否应该执行该信号
    P2修复: 同时持久化到数据库，重启后不丢失
    
    同一根K线的同一信号只执行一次
    
    参数:
    - symbol: 交易对
    - timeframe: 时间周期
    - action: 信号动作 (BUY/SELL)
    - candle_time: K线时间戳 (毫秒)
    
    返回:
    - True=应该执行, False=已处理过
    """
    global _last_signal_candle
    key = (symbol, timeframe, action)
    
    if key in _last_signal_candle and _last_signal_candle[key] == candle_time:
        return False  # 同一根K线已处理
    
    # 更新内存缓存
    _last_signal_candle[key] = candle_time
    
    # P2修复: 同时持久化到数据库
    try:
        set_signal_cache(symbol, timeframe, action, candle_time)
    except Exception:
        pass  # 数据库写入失败不影响交易
    
    return True

def clear_signal_cache():
    """清除信号缓存（内存+数据库）"""
    global _last_signal_candle
    _last_signal_candle.clear()
    try:
        clear_signal_cache_db()
    except Exception:
        pass

def simulate_fill(order: dict, last_price: float, db_config=None) -> dict:
    """模拟撮合引擎
    
    Args:
        order: 订单信息字典
        last_price: 最近成交价
        db_config: 数据库配置
    
    Returns:
        包含balance、positions和fill信息的字典
    """
    # 获取当前模拟余额
    balance = get_paper_balance(db_config)
    available = balance.get('available', 10000.0)
    
    # 获取当前模拟持仓
    symbol = order['symbol']
    pos_side = order['posSide']
    current_pos = get_paper_position(symbol, pos_side, db_config)
    
    # 计算成交金额
    qty = order['amount']
    price = last_price
    amount = qty * price
    fee = amount * 0.0002  # 假设0.02%的手续费
    
    # 计算可用资金变化
    if order['side'] == 'buy':
        # 买入需要扣除资金
        if available < amount + fee:
            raise ValueError(f"可用资金不足: {available} < {amount + fee}")
        new_available = available - amount - fee
    else:
        # 卖出获得资金
        new_available = available + amount - fee
    
    # 更新持仓
    new_positions = {}
    pos_key = f"{symbol}_{pos_side}"
    
    if current_pos:
        current_qty = current_pos.get('qty', 0.0)
        current_entry = current_pos.get('entry_price', 0.0)
        
        if order['side'] == 'buy':
            # 买入加仓
            total_qty = current_qty + qty
            avg_price = (current_qty * current_entry + qty * price) / total_qty
            new_pos = {
                'symbol': symbol,
                'pos_side': pos_side,
                'qty': total_qty,
                'entry_price': avg_price,
                'unrealized_pnl': total_qty * (price - avg_price)
            }
            new_positions[pos_key] = new_pos
        else:
            # 卖出减仓
            if current_qty <= qty:
                # 完全平仓
                new_pos = None
                realized_pnl = current_qty * (price - current_entry) - fee
            else:
                # 部分平仓
                new_qty = current_qty - qty
                realized_pnl = qty * (price - current_entry) - fee
                new_pos = {
                    'symbol': symbol,
                    'pos_side': pos_side,
                    'qty': new_qty,
                    'entry_price': current_entry,
                    'unrealized_pnl': new_qty * (price - current_entry)
                }
                new_positions[pos_key] = new_pos
    else:
        # 新开仓
        if order['side'] == 'buy':
            new_qty = qty
        else:
            new_qty = -qty  # 做空
        
        new_pos = {
            'symbol': symbol,
            'pos_side': pos_side,
            'qty': abs(new_qty),
            'entry_price': price,
            'unrealized_pnl': 0.0
        }
        new_positions[pos_key] = new_pos
    
    # 更新余额
    new_balance = {
        'id': balance.get('id', 1),
        'currency': balance.get('currency', 'USDT'),
        'equity': new_available,
        'available': new_available,
        'updated_at': int(time.time())
    }
    
    # 创建成交记录
    fill = {
        'ts': int(time.time() * 1000),
        'symbol': symbol,
        'side': order['side'],
        'pos_side': pos_side,
        'qty': qty,
        'price': price,
        'fee': fee,
        'note': f"模拟成交: {order['order_type']}"
    }
    
    return {
        'balance': new_balance,
        'positions': new_positions,
        'fill': fill
    }


def main():
    """交易引擎主函数
    
    实现24h常驻运行的交易引擎，与UI通过SQLite数据库解耦
    """
    # 修复Windows控制台编码问题
    try:
        import win_unicode_console
        win_unicode_console.enable()
    except ImportError:
        pass

    # 设置stdout和stderr编码为UTF-8
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except AttributeError:
        # 兼容旧版本Python
        if sys.platform.startswith('win'):
            import io
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
            sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    
    # 配置日志
    logger = setup_logger()
    logger.debug("=== 交易引擎启动 ===")
    
    # 初始化数据库
    init_db()
    
    # P2修复: 从数据库加载信号缓存（重启后恢复）
    load_signal_cache_from_db()
    logger.debug(f"信号缓存已从数据库加载: {len(_last_signal_candle)} 条记录")
    
    # 打印数据库身份信息用于调试
    db_identity = debug_db_identity()
    logger.debug(f"数据库身份信息: {db_identity}")
    
    # 获取机器人配置（必须在使用前定义）
    bot_config = get_bot_config()
    run_mode = bot_config.get('run_mode', 'sim')
    
    # 加载解密后的凭证
    new_creds = load_decrypted_credentials()
    api_key = new_creds.get('okx_api_key') or bot_config.get('okx_api_key', '')
    api_secret = new_creds.get('okx_api_secret')
    api_passphrase = new_creds.get('okx_api_passphrase')
    symbols_str = bot_config.get('symbols', 'BTC/USDT:USDT,ETH/USDT:USDT')
    base_position_size = bot_config.get('position_size', 0.01)
    enable_trading = bot_config.get('enable_trading', 0)
    
    # 解析交易对
    symbols = symbols_str.split(',')
    # 确保交易对格式正确
    TRADE_SYMBOLS = {}
    for symbol in symbols:
        symbol = symbol.strip()
        if not symbol:
            continue
        # 移除可能的斜杠前缀
        if symbol.startswith('/'):
            symbol = symbol[1:]
        # 确保格式正确（带结算货币）
        if '/' in symbol and ':' not in symbol:
            symbol = f"{symbol}:USDT"
        TRADE_SYMBOLS[symbol] = {}
    
    logger.debug(f"初始配置: run_mode={run_mode}, symbols={list(TRADE_SYMBOLS.keys())}, enable_trading={enable_trading}")
    
    # 初始化交易所适配器
    exchange = None
    provider = None
    
    try:
        # 从bot_config获取API密钥（使用受信任的后端解密接口）
        creds = load_decrypted_credentials()
        api_key = creds.get('okx_api_key') or bot_config.get('okx_api_key', '')
        api_secret = creds.get('okx_api_secret')
        api_passphrase = creds.get('okx_api_passphrase')
        
        # 只有当API密钥都提供时才初始化交易所适配器
        if api_key and api_secret and api_passphrase:
            # 🔥 关键修复：传递 run_mode，禁用 sandbox
            # run_mode: 'live' = 实盘下单, 'paper_on_real' = 实盘行情+本地模拟
            # 注意：'sim' 会被 OKXAdapter 自动映射为 'paper_on_real'
            exchange_config = {
                "exchange_type": "okx",
                "api_key": api_key,
                "api_secret": api_secret,
                "api_passphrase": api_passphrase,
                "run_mode": run_mode,  # 传递运行模式
                "market_type": OKX_MARKET_TYPE,
                "td_mode": OKX_TD_MODE
                # 注意：不再传递 sandbox，OKXAdapter 会强制禁用
            }
            
            exchange = ExchangeAdapterFactory.get_exchange_adapter(exchange_config)
            exchange.initialize()
            logger.debug(f"交易所连接初始化成功 | run_mode={run_mode}")
            
            # P0修复: 启动时强制设置仓位模式为双向持仓
            try:
                if hasattr(exchange, 'ensure_position_mode'):
                    success = exchange.ensure_position_mode(hedged=True)
                    if success:
                        logger.debug("仓位模式已设置为双向持仓 (long/short)")
                    else:
                        logger.warning("仓位模式设置失败，请手动在OKX设置为双向持仓模式")
            except Exception as e:
                logger.warning(f"设置仓位模式异常: {e}，请确认账户为双向持仓模式")
            
            # 初始化MarketDataProvider
            provider = MarketDataProvider(
                exchange_adapter=exchange,
                timeframe=TIMEFRAME,
                ohlcv_limit=100  # 默认K线数量
            )
            logger.debug(f"MarketDataProvider初始化成功")
        else:
            logger.debug("API密钥未完全配置，将以模拟模式继续运行")
    except Exception as e:
        logger.error(f"初始化交易所适配器失败: {e}")
        logger.debug("将以模拟模式继续运行")
        update_engine_status(last_error=f"API初始化错误: {str(e)[:50]}...")
        # 不退出，继续运行以测试数据库功能
    
    # 无论是否连接交易所，都初始化引擎状态
    update_engine_status(
        ts=int(time.time() * 1000),
        last_okx_latency_ms=0,
        run_mode=run_mode,
        pause_trading=0,
        last_plan_order_json=json.dumps({})
    )
    
    # 检查exchange和provider是否初始化成功
    if not exchange or not provider:
        logger.warning("交易所或MarketDataProvider未初始化，将使用模拟数据进行测试")
    
    # 初始化引擎状态
    update_engine_status(
        ts=int(time.time() * 1000),
        alive=1,
        cycle_ms=0,
        last_error="",
        last_okx_latency_ms=0,
        run_mode=run_mode,
        pause_trading=0,
        last_plan_order_json=json.dumps({})
    )
    
    # 记录当前配置的更新时间，用于热加载检测
    last_config_updated_at = bot_config.get('updated_at', 0)
    
    # 记录当前使用的API密钥，用于检测变化（解密后，仅在后端使用）
    current_creds = load_decrypted_credentials()
    current_api_key = current_creds.get('okx_api_key') or bot_config.get('okx_api_key', '')
    current_api_secret = current_creds.get('okx_api_secret')
    current_api_passphrase = current_creds.get('okx_api_passphrase')
    
    cycle_error_count = 0
    cycle_id = 0  # 初始化周期ID
    last_trigger_minute = -1  # 初始化上次触发的分钟，用于每分钟末扫描调度
    
    # 定义支持的时间周期
    supported_timeframes = ['1m', '3m', '5m', '15m', '30m', '1h']
    
    # ============================================================
    # 🔥 后台余额同步器 (Pre-Flight Check)
    # 独立线程在每分钟的 30秒、55秒 预先检查余额和风控
    # 确保 00秒 的扫描线程零延迟进入数据拉取
    # ============================================================
    import threading
    
    # 预风控缓存（线程安全）
    class PreFlightCache:
        """预检查缓存 - 线程安全的风控状态 + 策略预加载"""
        def __init__(self):
            self._lock = threading.Lock()
            # 风控状态
            self.can_open_new = True       # 是否可以开新主仓
            self.remaining_base = 0.0      # 剩余可用本金
            self.equity = 0.0              # 账户权益
            self.last_check_time = 0       # 上次检查时间
            self.last_check_second = -1    # 上次检查的秒数（避免重复）
            self.check_reason = ""         # 检查结果原因
            # 🔥 策略预加载缓存
            self.strategy_engine = None    # 预加载的策略引擎实例
            self.strategy_id = None        # 当前策略ID
            self.strategy_meta = None      # 策略元数据
            self.strategy_load_time = 0    # 策略加载时间
        
        def update(self, can_open: bool, remaining: float, equity: float, reason: str = ""):
            with self._lock:
                self.can_open_new = can_open
                self.remaining_base = remaining
                self.equity = equity
                self.last_check_time = time.time()
                self.check_reason = reason
        
        def update_strategy(self, strategy_engine, strategy_id: str, strategy_meta: dict):
            """更新预加载的策略引擎"""
            with self._lock:
                self.strategy_engine = strategy_engine
                self.strategy_id = strategy_id
                self.strategy_meta = strategy_meta
                self.strategy_load_time = time.time()
        
        def get_status(self):
            with self._lock:
                return {
                    'can_open_new': self.can_open_new,
                    'remaining_base': self.remaining_base,
                    'equity': self.equity,
                    'last_check_time': self.last_check_time,
                    'check_reason': self.check_reason
                }
        
        def get_strategy(self):
            """获取预加载的策略引擎（零延迟）"""
            with self._lock:
                return {
                    'engine': self.strategy_engine,
                    'id': self.strategy_id,
                    'meta': self.strategy_meta,
                    'load_time': self.strategy_load_time
                }
    
    preflight_cache = PreFlightCache()
    
    # 后台余额同步函数
    def background_balance_syncer():
        """
        后台余额同步线程
        
        在每分钟的 30秒 和 55秒 执行预检查：
        - 查询余额
        - 计算风控
        - 更新 preflight_cache
        """
        nonlocal run_mode, max_lev, TRADE_SYMBOLS
        
        while True:
            try:
                now = datetime.now()
                current_second = now.second
                
                # 🔥 在 30秒 和 55秒 执行预检查
                if current_second in [30, 55]:
                    # 避免同一秒重复检查
                    if preflight_cache.last_check_second == current_second:
                        time.sleep(0.5)
                        continue
                    
                    preflight_cache.last_check_second = current_second
                    
                    # 检查交易是否启用
                    _bot_config = get_bot_config()
                    _enable_trading = _bot_config.get('enable_trading', 0)
                    _control = get_control_flags()
                    _pause_trading = _control.get("pause_trading", 0)
                    
                    if _enable_trading != 1 or _pause_trading == 1:
                        # 交易未启用，跳过检查
                        time.sleep(0.5)
                        continue
                    
                    # 🔥 执行余额和风控检查
                    try:
                        equity = 0.0
                        total_base_used = 0.0
                        
                        if run_mode == 'paper':
                            # Paper模式：使用本地模拟账户
                            paper_bal = get_paper_balance()
                            equity = float(paper_bal.get('equity', 0) or 0) if paper_bal else 0
                            
                            if equity == 0:
                                equity = 200.0  # 默认值
                            
                            # 计算已用本金
                            paper_positions = get_paper_positions()
                            if paper_positions:
                                for pos_key, pos in paper_positions.items():
                                    qty = float(pos.get('qty', 0) or 0)
                                    entry_price = float(pos.get('entry_price', 0) or 0)
                                    if qty > 0 and entry_price > 0:
                                        position_value = qty * entry_price
                                        position_base = position_value / max_lev
                                        total_base_used += position_base
                            
                            # 计算对冲仓位
                            hedge_positions = get_hedge_positions()
                            if hedge_positions:
                                for hedge_pos in hedge_positions:
                                    qty = float(hedge_pos.get('qty', 0) or 0)
                                    entry_price = float(hedge_pos.get('entry_price', 0) or 0)
                                    if qty > 0 and entry_price > 0:
                                        position_value = qty * entry_price
                                        position_base = position_value / max_lev
                                        total_base_used += position_base
                        else:
                            # Live模式：从交易所获取真实数据
                            if provider is None:
                                preflight_cache.update(True, 0.0, 0.0, "provider未初始化")
                                time.sleep(0.5)
                                continue
                            
                            try:
                                bal = provider.get_balance()
                                equity = float(bal.get('total', {}).get('USDT', 0)) if isinstance(bal, dict) else 0
                            except Exception as e:
                                logger.debug(f"[balance-sync] 余额获取失败: {e}")
                                time.sleep(0.5)
                                continue
                            
                            # 获取持仓
                            try:
                                positions = provider.get_positions(list(TRADE_SYMBOLS.keys()) if TRADE_SYMBOLS else None)
                                if positions:
                                    for symbol, pos in positions.items():
                                        contracts = float(pos.get('contracts', 0) or pos.get('positionAmt', 0) or 0)
                                        if contracts > 0:
                                            mark_price = float(pos.get('markPrice', 0) or pos.get('entryPrice', 0) or 0)
                                            if mark_price > 0:
                                                position_value = contracts * mark_price
                                                position_base = position_value / max_lev
                                                total_base_used += position_base
                            except Exception:
                                pass
                        
                        # 🔥 风控计算：总本金 < 权益 × 10%
                        if equity == 0:
                            preflight_cache.update(False, 0.0, 0.0, "余额为0")
                        else:
                            max_allowed_base = equity * 0.10
                            remaining_base = max_allowed_base - total_base_used
                            
                            if total_base_used >= max_allowed_base:
                                preflight_cache.update(False, 0.0, equity, f"本金已用尽 ({total_base_used:.2f}/{max_allowed_base:.2f})")
                            else:
                                preflight_cache.update(True, remaining_base, equity, "OK")
                        
                        logger.info(f"[balance-sync] {now.strftime('%H:%M:%S')} | 权益: ${equity:.2f} | 可开新仓: {preflight_cache.can_open_new} | 剩余本金: ${preflight_cache.remaining_base:.2f}")
                        
                    except Exception as e:
                        logger.error(f"[balance-sync] 预检查异常: {e}")
                        preflight_cache.update(True, 0.0, 0.0, f"异常: {e}")
                    
                    # ============================================================
                    # 🔥 策略预加载 (Strategy Pre-Loading)
                    # 在 30秒/55秒 预先加载策略引擎，减少 00秒 扫描时的延迟
                    # ============================================================
                    try:
                        selected_strategy_id = _bot_config.get('selected_strategy_id')
                        validated_strategy_id = validate_and_fallback_strategy(selected_strategy_id)
                        
                        # 检查策略是否需要重新加载（策略ID变更时）
                        cached_strategy = preflight_cache.get_strategy()
                        if cached_strategy['id'] != validated_strategy_id or cached_strategy['engine'] is None:
                            # 🔥 动态加载策略引擎
                            registry = get_strategy_registry()
                            strategy_engine = registry.instantiate_strategy(validated_strategy_id)
                            strategy_meta = registry.get_strategy_meta(validated_strategy_id)
                            
                            # 更新缓存
                            preflight_cache.update_strategy(strategy_engine, validated_strategy_id, strategy_meta)
                            
                            strategy_display_name = strategy_meta.get('display_name', validated_strategy_id) if strategy_meta else validated_strategy_id
                            logger.info(f"[strategy-preload] {now.strftime('%H:%M:%S')} | 策略预加载: {strategy_display_name}")
                    except Exception as e:
                        logger.error(f"[strategy-preload] 策略预加载失败: {e}")
                
                # 低延迟空转
                time.sleep(0.2)
                
            except Exception as e:
                logger.error(f"[balance-sync] 后台线程异常: {e}")
                time.sleep(1)
    
    # 启动后台余额同步线程
    balance_syncer_thread = threading.Thread(target=background_balance_syncer, daemon=True, name="BalanceSyncer")
    balance_syncer_thread.start()
    logger.info("[balance-sync] 后台余额同步线程已启动")
    
    print(f"🕰️ 进入时间监听模式...（收线确认模式：每分钟00-02秒触发）\n")
    print(f"⚠️ 交易功能默认关闭，请在前端手动启用交易\n")
    
    # 主循环
    previous_state = None  # 记录上一次的状态，用于避免重复日志
    
    # 🔥 从数据库加载交易参数（默认20倍杠杆）
    trading_params = get_trading_params()
    max_lev = trading_params.get('leverage', 20)
    main_position_pct = trading_params.get('main_position_pct', 0.03)
    sub_position_pct = trading_params.get('sub_position_pct', 0.01)
    hard_tp_pct = trading_params.get('hard_tp_pct', 0.02)
    hedge_tp_pct = trading_params.get('hedge_tp_pct', 0.005)
    
    logger.debug(f"交易参数: 杠杆={max_lev}x, 主仓={main_position_pct*100}%, 次仓={sub_position_pct*100}%, 硬止盈={hard_tp_pct*100}%, 对冲止盈={hedge_tp_pct*100}%")
    
    # P1修复: 初始化风控模块（日损失限制）
    risk_config = RiskControlConfig(
        max_order_size=1000.0,  # 单笔最大$1000
        daily_loss_limit_pct=0.10  # 日损失限制10%
    )
    risk_control = RiskControlModule(risk_config)
    logger.debug(f"风控模块已初始化: 单笔限额=${risk_config.max_order_size}, 日损失限制={risk_config.daily_loss_limit_pct*100}%")
    
    # 🔥 初始化对冲管理器
    hedge_manager = HedgeManager(
        db_bridge_module=db_bridge_module,
        leverage=max_lev,
        hard_tp_pct=hard_tp_pct,
        hedge_tp_pct=hedge_tp_pct
    )
    logger.debug("对冲管理器已初始化")
    
    # 启动成功摘要（简洁版，只打印到控制台）
    print(f"\n{'='*70}")
    print(f"✅ 交易引擎启动成功 | 模式: {run_mode} | 币种: {len(TRADE_SYMBOLS)} | 交易: {'启用' if enable_trading else '禁用'}")
    print(f"{'='*70}\n")
    logger.debug(f"交易引擎启动成功 | 模式: {run_mode} | 币种: {len(TRADE_SYMBOLS)}")
    
    # ============================================================
    # 🔥 强制启动预热 (Force Warmup)
    # 在进入主循环之前，并发拉取所有币种的所有周期历史数据
    # 确保后续扫描只需增量更新，不会因懒加载导致卡顿
    # ============================================================
    if provider is not None:
        warmup_start = time.time()
        warmup_symbols = list(TRADE_SYMBOLS.keys())
        warmup_timeframes = supported_timeframes  # ['1m', '3m', '5m', '15m', '30m', '1h']
        warmup_total = len(warmup_symbols) * len(warmup_timeframes)
        warmup_success = 0
        warmup_failed = []
        
        print(f"\n{'='*70}")
        print(f"🔥 [Warmup] 开始系统预热...")
        print(f"   币种: {len(warmup_symbols)} | 周期: {len(warmup_timeframes)} | 总任务: {warmup_total}")
        print(f"{'='*70}")
        logger.info(f"[Warmup] 开始预热 | 币种: {warmup_symbols} | 周期: {warmup_timeframes}")
        
        def warmup_fetch_task(symbol: str, tf: str):
            """预热任务：拉取单个币种单个周期的完整历史数据"""
            try:
                # 强制全量拉取 1000 根 K线
                ohlcv_data, is_stale = provider.get_ohlcv(
                    symbol, timeframe=tf, limit=1000, force_fetch=True
                )
                if ohlcv_data and len(ohlcv_data) >= 100:
                    return symbol, tf, len(ohlcv_data), None
                else:
                    return symbol, tf, 0, f"数据不足: {len(ohlcv_data) if ohlcv_data else 0}"
            except Exception as e:
                return symbol, tf, 0, str(e)
        
        # 使用 ThreadPoolExecutor 并发预热
        with ThreadPoolExecutor(max_workers=5) as executor:
            warmup_futures = []
            for symbol in warmup_symbols:
                for tf in warmup_timeframes:
                    warmup_futures.append(executor.submit(warmup_fetch_task, symbol, tf))
            
            # 等待所有预热任务完成
            for future in as_completed(warmup_futures):
                try:
                    sym, tf, bar_count, error = future.result()
                    if error:
                        warmup_failed.append((sym, tf, error))
                        print(f"   ❌ [Warmup] {sym} {tf} 失败: {error[:50]}")
                        logger.warning(f"[Warmup] {sym} {tf} 失败: {error}")
                    else:
                        warmup_success += 1
                        print(f"   ✅ [Warmup] {sym} {tf} 完成 ({bar_count} bars)")
                        logger.debug(f"[Warmup] {sym} {tf} 完成 ({bar_count} bars)")
                except Exception as e:
                    logger.error(f"[Warmup] 任务异常: {e}")
        
        warmup_cost = time.time() - warmup_start
        print(f"\n{'='*70}")
        print(f"✅ [Warmup] 系统预热完成 | 成功: {warmup_success}/{warmup_total} | 耗时: {warmup_cost:.2f}s")
        if warmup_failed:
            print(f"   ⚠️ 失败任务: {len(warmup_failed)}")
            for sym, tf, err in warmup_failed[:5]:  # 只显示前5个
                print(f"      - {sym} {tf}: {err[:30]}")
        print(f"{'='*70}\n")
        logger.info(f"[Warmup] 预热完成 | 成功: {warmup_success}/{warmup_total} | 耗时: {warmup_cost:.2f}s | 失败: {len(warmup_failed)}")
    else:
        print(f"\n⚠️ [Warmup] MarketDataProvider 未初始化，跳过预热")
        logger.warning("[Warmup] MarketDataProvider 未初始化，跳过预热")
    
    # 🔥 首次扫描标记（预热后的第一次扫描只计算信号，不执行下单）
    is_first_scan_after_warmup = True
    
    while True:
        # 🔥 极速监听系统时间
        now = datetime.now()
        
        # 🔥 风控检查已移至后台线程 (background_balance_syncer)
        # 在 30秒 和 55秒 自动执行，无需在主循环中处理
        
        # 🔥 收线确认模式：每分钟00-02秒触发（整分扫描，防止错过）
        # 在00秒拉取时，交易所的最新K线(-1)是刚开盘的那根，倒数第二根(-2)就是已收线的K线
        if 0 <= now.second <= 2 and now.minute != last_trigger_minute:
            last_trigger_minute = now.minute
            cycle_id += 1  # 递增周期ID
            cycle_start_time = time.time()
            
            # 总闸门控制逻辑
            control = get_control_flags()
            bot_config = get_bot_config()
            enable_trading = bot_config.get('enable_trading', 0)
            pause_trading = control.get("pause_trading", 0)
            
            # 确定当前状态
            current_state = "idle"
            if enable_trading == 1:
                if pause_trading == 1:
                    current_state = "paused"
                else:
                    current_state = "running"
            
            # 检查交易是否被禁用或暂停
            if enable_trading != 1:
                # 更新引擎状态
                update_engine_status(alive=1, pause_trading=0)
                # 只有状态变化时才记录日志
                if previous_state != "idle":
                    render_idle_block(now.strftime('%H:%M:%S'), "交易功能已禁用，等待前端启用", logger)
                    previous_state = "idle"
                continue
            elif pause_trading == 1:
                # 更新引擎状态
                update_engine_status(alive=1, pause_trading=1)
                # 只有状态变化时才记录日志
                if previous_state != "paused":
                    render_idle_block(now.strftime('%H:%M:%S'), "交易已暂停，跳过扫描", logger)
                    previous_state = "paused"
                continue
            else:
                # 只有状态变化时才记录日志
                if previous_state != "running":
                    logger.debug("交易已启用，开始执行扫描与信号计算")
                    previous_state = "running"
            
            # 获取需要扫描的时间周期
            due_timeframes = get_due_timeframes(now.minute, supported_timeframes)
            
            if not due_timeframes:
                continue
            
            # 🔥 收集扫描数据，最后统一输出
            scan_time_str = now.strftime('%H:%M:%S')
            # 从预检查缓存获取风控状态（零延迟，不查询余额）
            preflight_status = preflight_cache.get_status()
            scan_risk_status = "可开新主仓" if preflight_status['can_open_new'] else "仅允许对冲仓"
            scan_collected_signals = []  # 收集发现的信号
            scan_collected_orders = []   # 收集执行的订单
            
            # 检查停止信号
            if control.get("stop_signal", 0) == 1:
                logger.debug("收到停止信号，正在停止引擎...")
                print(f"\n{'='*70}")
                print(f"🛑 [{now.strftime('%H:%M:%S')}] 收到停止信号，正在停止引擎...")
                print(f"{'='*70}")
                update_engine_status(alive=0)
                break
            
            # 检查并处理紧急平仓
            if control.get("emergency_flatten", 0) == 1:
                logger.warning("收到紧急平仓信号，正在执行平仓操作...")
                print(f"\n{'='*70}")
                print(f"🔥 [{now.strftime('%H:%M:%S')}] 执行紧急平仓...")
                print(f"{'='*70}")
                try:
                    if run_mode == "live":
                        # 实盘模式：从交易所获取真实持仓
                        if provider is None:
                            logger.error("MarketDataProvider未初始化，无法获取持仓信息")
                            positions = {}
                        else:
                            positions = provider.get_positions(list(TRADE_SYMBOLS.keys()))
                        
                        # 遍历所有持仓进行平仓
                        for symbol, position in positions.items():
                            if position.get("positionAmt", 0) != 0:
                                side = "sell" if position.get("positionAmt") > 0 else "buy"
                                posSide = "long" if position.get("positionAmt") > 0 else "short"
                                try:
                                    order_result = exchange.create_order(
                                        symbol=symbol,
                                        side=side,
                                        amount=abs(position.get("positionAmt")),
                                        order_type="market",
                                        params={
                                            "posSide": posSide,
                                            "tdMode": OKX_TD_MODE,
                                            "reduceOnly": True
                                        }
                                    )
                                    print(f"   ✅ {symbol} 紧急平仓成功")
                                    logger.debug(f"{symbol} 紧急平仓成功")
                                    provider.invalidate_positions()
                                    provider.invalidate_balance()
                                except Exception as e:
                                    print(f"   ❌ {symbol} 紧急平仓失败: {e}")
                                    logger.debug(f"{symbol} 紧急平仓失败: {e}")
                    else:
                        # 🔥 模拟模式：从数据库获取模拟持仓并清除
                        paper_positions = get_paper_positions()
                        if paper_positions:
                            # 🔥 修复：get_paper_positions() 返回字典 {key: pos_data}
                            for pos_key, pos in paper_positions.items():
                                symbol = pos.get('symbol')
                                pos_side = pos.get('pos_side')
                                qty = pos.get('qty', 0)
                                if qty > 0:
                                    try:
                                        delete_paper_position(symbol, pos_side)
                                        print(f"   ✅ 模拟平仓 {symbol} {pos_side} 数量: {qty}")
                                        logger.debug(f"模拟平仓成功 {symbol} {pos_side} 数量: {qty}")
                                    except Exception as e:
                                        print(f"   ❌ 模拟平仓失败 {symbol}: {e}")
                                        logger.error(f"模拟平仓失败 {symbol}: {e}")
                        else:
                            print(f"   ℹ️ 无模拟主仓需要平仓")
                        
                        # 🔥 同时清除对冲仓位
                        hedge_positions = get_hedge_positions()
                        if hedge_positions:
                            for hedge_pos in hedge_positions:
                                hedge_id = hedge_pos.get('id')
                                symbol = hedge_pos.get('symbol')
                                pos_side = hedge_pos.get('pos_side')
                                qty = hedge_pos.get('qty', 0)
                                if hedge_id and qty > 0:
                                    try:
                                        delete_hedge_position(hedge_id)
                                        print(f"   ✅ 模拟平对冲仓 {symbol} {pos_side} 数量: {qty}")
                                        logger.debug(f"模拟平对冲仓成功 {symbol} {pos_side} 数量: {qty}")
                                    except Exception as e:
                                        print(f"   ❌ 模拟平对冲仓失败 {symbol}: {e}")
                                        logger.error(f"模拟平对冲仓失败 {symbol}: {e}")
                        else:
                            print(f"   ℹ️ 无对冲仓需要平仓")
                except Exception as e:
                    logger.error(f"执行紧急平仓操作失败: {e}")
                    update_engine_status(last_error=str(e))
                finally:
                    set_control_flags(emergency_flatten=0)
                    print(f"   ✅ 紧急平仓操作完成")
                    print(f"{'='*70}")
                    logger.debug("紧急平仓操作完成")
            
            # 🔥 每次扫描前都从数据库重新加载交易池（确保前端修改立即生效）
            symbols_str = bot_config.get('symbols', '')
            if symbols_str:
                symbols = symbols_str.split(',')
                TRADE_SYMBOLS = {}
                for symbol in symbols:
                    symbol = symbol.strip()
                    if not symbol:
                        continue
                    if symbol.startswith('/'):
                        symbol = symbol[1:]
                    if '/' in symbol and ':' not in symbol:
                        symbol = f"{symbol}:USDT"
                    TRADE_SYMBOLS[symbol] = {}
            
            # 静默检查配置更新（不打印日志）
            new_bot_config = get_bot_config()
            if new_bot_config.get('updated_at', 0) > last_config_updated_at:
                try:
                    run_mode = new_bot_config.get('run_mode', 'sim')
                    base_position_size = new_bot_config.get('base_position_size', 0.01)
                    enable_trading = new_bot_config.get('enable_trading', 0)
                    last_config_updated_at = new_bot_config.get('updated_at', 0)
                    update_engine_status(run_mode=run_mode)
                except Exception as e:
                    logger.error(f"配置重载失败: {e}")
        
            # 静默处理重载配置信号（不打印日志）
            if control.get("reload_config", 0) == 1:
                try:
                    new_bot_config = get_bot_config()
                    run_mode = new_bot_config.get('run_mode', 'sim')
                    symbols_str = new_bot_config.get('symbols', '')
                    base_position_size = new_bot_config.get('base_position_size', 0.01)
                    enable_trading = new_bot_config.get('enable_trading', 0)
                    
                    # 解析新的交易对
                    if symbols_str:
                        symbols = symbols_str.split(',')
                        TRADE_SYMBOLS = {}
                        for symbol in symbols:
                            symbol = symbol.strip()
                            if not symbol:
                                continue
                            if symbol.startswith('/'):
                                symbol = symbol[1:]
                            if '/' in symbol and ':' not in symbol:
                                symbol = f"{symbol}:USDT"
                            TRADE_SYMBOLS[symbol] = {}
                    
                    last_config_updated_at = new_bot_config.get('updated_at', 0)
                    set_control_flags(reload_config=0)
                except Exception as e:
                    logger.error(f"配置重载失败: {e}")
                    set_control_flags(reload_config=0)
            
            # 🔥 步骤2：获取所有币种的实时价格（静默模式）
            tickers = {}
            price_fetch_start = time.time()
            
            for symbol in TRADE_SYMBOLS.keys():
                try:
                    if provider is not None:
                        ticker = provider.get_ticker(symbol)
                        tickers[symbol] = ticker
                    else:
                        tickers[symbol] = {'last': 45000.0 + (cycle_id % 1000)}
                except Exception:
                    pass  # 静默处理失败
            
            price_fetch_time = time.time() - price_fetch_start
            scan_price_ok = len(tickers)  # 记录价格获取成功数量
            
            # 🔥 收线确认模式：计算上一分钟的K线时间戳
            # 例如：10:06:00 触发 -> 期望的已收线K线时间戳为 10:05:00.000
            # 注意：在00秒触发时，我们要的是上一分钟已收盘的K线
            current_minute_ts = int(now.replace(second=0, microsecond=0).timestamp() * 1000)
            expected_closed_candle_ts = current_minute_ts - 60 * 1000  # 上一分钟的K线
            
            # ============================================================
            # 🔥 并行数据准备：使用 ThreadPoolExecutor 并发拉取所有币种的K线
            # ============================================================
            fetch_start_time = time.perf_counter()
            
            # 预加载数据结构（保持原有变量名）
            preloaded_data = {}  # {symbol: {timeframe: DataFrame}}
            ohlcv_data_dict = {}  # 兼容原有逻辑
            ohlcv_stale_dict = {}
            ohlcv_lag_dict = {}
            ohlcv_ok_count = 0
            ohlcv_stale_count = 0
            ohlcv_lag_count = 0
            fetch_failed_list = []  # 记录拉取失败的币种
            
            # 定义并行拉取任务（带重试）
            def fetch_ohlcv_task(symbol: str, tf: str, retry_count: int = 0):
                """并行拉取单个币种单个周期的K线数据"""
                max_retries = 2
                last_error = None
                
                for attempt in range(max_retries + 1):
                    try:
                        if provider is not None:
                            ohlcv_data, is_stale = provider.get_ohlcv(
                                symbol, timeframe=tf, limit=1000, force_fetch=True
                            )
                            return symbol, tf, ohlcv_data, is_stale, None
                        else:
                            # 模拟数据
                            mock_data = [[expected_closed_candle_ts, 45000, 45100, 44900, 45050, 1000]]
                            return symbol, tf, mock_data, False, None
                    except Exception as e:
                        last_error = str(e)
                        if attempt < max_retries:
                            time.sleep(0.2 * (attempt + 1))  # 指数退避
                        continue
                
                return symbol, tf, None, False, last_error
            
            # 构建任务列表：所有币种 × 所有到期周期
            fetch_tasks = []
            current_symbols = list(TRADE_SYMBOLS.keys())
            
            # 🔥 优先处理待初始化的币种（上一轮失败的）
            if provider is not None:
                pending_symbols = provider.get_pending_init_symbols()
                if pending_symbols:
                    logger.info(f"[scan] 发现 {len(pending_symbols)} 个待初始化币种，优先处理")
            
            # 使用 ThreadPoolExecutor 并行拉取
            import pandas as pd
            with ThreadPoolExecutor(max_workers=5) as executor:
                for symbol in current_symbols:
                    for tf in due_timeframes:
                        fetch_tasks.append(executor.submit(fetch_ohlcv_task, symbol, tf))
                
                # 等待所有结果
                for future in as_completed(fetch_tasks):
                    try:
                        sym, tf, ohlcv_data, is_stale, error = future.result()
                        
                        if error:
                            logger.warning(f"[scan] K线获取失败 {sym} {tf}: {error}")
                            fetch_failed_list.append((sym, tf))
                            continue
                        
                        if ohlcv_data and len(ohlcv_data) > 0:
                            # 🔥 计算该周期的期望K线时间戳
                            tf_ms = 60 * 1000  # 默认1分钟
                            if tf == '3m':
                                tf_ms = 3 * 60 * 1000
                            elif tf == '5m':
                                tf_ms = 5 * 60 * 1000
                            elif tf == '15m':
                                tf_ms = 15 * 60 * 1000
                            elif tf == '30m':
                                tf_ms = 30 * 60 * 1000
                            elif tf == '1h':
                                tf_ms = 60 * 60 * 1000
                            
                            # 期望的已收线K线时间戳 = 当前分钟向下取整到该周期 - 该周期时长
                            expected_tf_ts = ((current_minute_ts // tf_ms) * tf_ms) - tf_ms
                            
                            # 检查数据是否滞后
                            latest_candle_ts = ohlcv_data[-1][0]
                            is_lag = latest_candle_ts < expected_tf_ts
                            
                            if is_lag:
                                ohlcv_lag_count += 1
                                logger.debug(f"[scan-skip] reason=data_lag symbol={sym} tf={tf} current_ts={latest_candle_ts} expected={expected_tf_ts}")
                            
                            # 🔥 关键：去除最后一根未收线K线，只保留已收线数据
                            # 在00秒拉取时，交易所返回的最新K线(-1)是刚开盘的那根
                            # 倒数第二根(-2)才是我们要的已收线K线
                            # 因此去掉最后一根，策略里取 iloc[-1] 就自然是"刚收线的那根"
                            df = pd.DataFrame(ohlcv_data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                            if len(df) >= 2:
                                clean_df = df.iloc[:-1].copy()  # 去除最后一根未收线K线
                            else:
                                clean_df = df.copy()
                            
                            # 存入预加载数据（保持原有变量名兼容）
                            if sym not in preloaded_data:
                                preloaded_data[sym] = {}
                            preloaded_data[sym][tf] = clean_df
                            
                            # 兼容原有逻辑的数据结构
                            if sym not in ohlcv_data_dict:
                                ohlcv_data_dict[sym] = {}
                            ohlcv_data_dict[sym][tf] = ohlcv_data  # 原始数据用于 upsert
                            
                            if sym not in ohlcv_stale_dict:
                                ohlcv_stale_dict[sym] = {}
                            ohlcv_stale_dict[sym][tf] = is_stale
                            
                            if sym not in ohlcv_lag_dict:
                                ohlcv_lag_dict[sym] = {}
                            ohlcv_lag_dict[sym][tf] = is_lag
                            
                            # 持久化到数据库
                            upsert_ohlcv(sym, tf, ohlcv_data)
                            ohlcv_ok_count += 1
                            if is_stale:
                                ohlcv_stale_count += 1
                        else:
                            # 数据为空
                            fetch_failed_list.append((sym, tf))
                    except Exception as e:
                        logger.error(f"并行拉取结果处理失败: {e}")
            
            fetch_cost = time.perf_counter() - fetch_start_time
            
            # 🔥 记录拉取失败的币种数量
            fail_info = f" | 失败: {len(fetch_failed_list)}" if fetch_failed_list else ""
            logger.info(f"[scan] 并行拉取完成 | 耗时: {fetch_cost:.2f}s | 触发时间: {now.strftime('%H:%M:%S')} | 成功: {ohlcv_ok_count}/{len(current_symbols) * len(due_timeframes)}{fail_info}")
            
            # K线获取结果记录到DEBUG日志
            log_parts = [f"K线获取: {ohlcv_ok_count}/{len(current_symbols) * len(due_timeframes)}"]
            if ohlcv_stale_count > 0:
                log_parts.append(f"stale: {ohlcv_stale_count}")
            if ohlcv_lag_count > 0:
                log_parts.append(f"lag: {ohlcv_lag_count}")
            logger.debug(" | ".join(log_parts))
            
            # 对每个到期的时间周期执行扫描
            for timeframe in due_timeframes:
                # 🔥 初始化扫描统计变量
                scan_new_closed = 0
                scan_signals = 0
                scan_orders = 0
                
                # 🔥 计算该周期的期望K线时间戳（用于校验）
                tf_ms = 60 * 1000  # 默认1分钟
                if timeframe == '3m':
                    tf_ms = 3 * 60 * 1000
                elif timeframe == '5m':
                    tf_ms = 5 * 60 * 1000
                elif timeframe == '15m':
                    tf_ms = 15 * 60 * 1000
                elif timeframe == '30m':
                    tf_ms = 30 * 60 * 1000
                elif timeframe == '1h':
                    tf_ms = 60 * 60 * 1000
                
                # 期望的已收线K线时间戳
                expected_tf_ts = ((current_minute_ts // tf_ms) * tf_ms) - tf_ms
            
                # P1修复: 行情断流检测
                if 'market_data_fail_count' not in dir():
                    market_data_fail_count = 0
                
                if not tickers or not ohlcv_data_dict:
                    market_data_fail_count += 1
                    if market_data_fail_count >= 3:
                        logger.warning(f"行情断流: 连续{market_data_fail_count}次失败，自动暂停")
                        set_control_flags(pause_trading=1)
                        update_engine_status(ts=int(time.time() * 1000), last_error=f"行情断流")
                    continue
                else:
                    market_data_fail_count = 0
            
                # 获取持仓（静默）
                try:
                    positions = provider.get_positions(list(TRADE_SYMBOLS.keys())) if provider else {}
                    positions_json = json.dumps(positions)
                except Exception:
                    positions_json = json.dumps({})
            
                # 【B】修复: 初始化 plan_order 为 None，确保在任何路径下都有定义
                # 这样可以避免 UnboundLocalError
                plan_order = None
                can_execute_real_order = False
                can_execute_paper_order = False
                blocked_reasons = []
                
                # 🔥 热加载交易参数（每个周期检查一次）
                _trading_params = get_trading_params()
                if _trading_params.get('leverage') != max_lev:
                    max_lev = _trading_params.get('leverage', 20)
                    hedge_manager.update_params(leverage=max_lev)
                if _trading_params.get('hard_tp_pct') != hard_tp_pct:
                    hard_tp_pct = _trading_params.get('hard_tp_pct', 0.02)
                    hedge_manager.update_params(hard_tp_pct=hard_tp_pct)
                if _trading_params.get('hedge_tp_pct') != hedge_tp_pct:
                    hedge_tp_pct = _trading_params.get('hedge_tp_pct', 0.005)
                    hedge_manager.update_params(hedge_tp_pct=hedge_tp_pct)
                main_position_pct = _trading_params.get('main_position_pct', 0.03)
                sub_position_pct = _trading_params.get('sub_position_pct', 0.01)
                
                # 🔥 步骤1：止盈检查（在信号处理之前）
                for symbol, ticker in tickers.items():
                    if not ticker or ticker.get("last", 0) <= 0:
                        continue
                    
                    current_price = ticker.get("last")
                    
                    # 🔥 检查对冲逃生（有对冲仓时）
                    should_escape, net_pnl, escape_reason = hedge_manager.check_hedge_escape(symbol, current_price)
                    if should_escape:
                        success, total_pnl, msg = hedge_manager.execute_close_all(
                            symbol, current_price, exchange, run_mode
                        )
                        if success:
                            scan_collected_orders.append({
                                'symbol': symbol, 'action': 'ESCAPE', 'price': current_price,
                                'type': escape_reason, 'is_hedge': False
                            })
                            add_paper_fill(
                                ts=int(time.time() * 1000),
                                symbol=symbol,
                                side='close',
                                pos_side='all',
                                qty=0,
                                price=current_price,
                                fee=0,
                                note=f"对冲逃生: {escape_reason}"
                            )
                        continue
                    
                    # 🔥 检查硬止盈（仅主仓时）
                    should_tp, pnl, tp_reason = hedge_manager.check_hard_take_profit(symbol, current_price)
                    if should_tp:
                        success, total_pnl, msg = hedge_manager.execute_close_all(
                            symbol, current_price, exchange, run_mode
                        )
                        if success:
                            scan_collected_orders.append({
                                'symbol': symbol, 'action': 'TP', 'price': current_price,
                                'type': tp_reason, 'is_hedge': False
                            })
                            add_paper_fill(
                                ts=int(time.time() * 1000),
                                symbol=symbol,
                                side='close',
                                pos_side='all',
                                qty=0,
                                price=current_price,
                                fee=0,
                                note=f"硬止盈: {tp_reason}"
                            )
                        continue
                
                # ============================================================
                # 🔥 步骤2：动态策略分发与标准化 (Dynamic Strategy Dispatch)
                # 策略引擎已在后台线程预加载，这里直接从缓存获取（零延迟）
                # ============================================================
                
                # 从数据库获取UI选择的策略
                _bot_config = get_bot_config()
                selected_strategy_id = _bot_config.get('selected_strategy_id')
                try:
                    strategy_id = validate_and_fallback_strategy(selected_strategy_id)
                except Exception as e:
                    logger.error(f"策略校验失败: {e}")
                    # 明确跳过此次扫描而不是静默回退
                    continue

                # 🔥 从预加载缓存获取策略引擎（零延迟）
                cached_strategy = preflight_cache.get_strategy()
                
                if cached_strategy['engine'] is not None and cached_strategy['id'] == strategy_id:
                    # 🔥 命中缓存：直接使用预加载的策略引擎
                    strategy_engine = cached_strategy['engine']
                    strategy_meta = cached_strategy['meta']
                else:
                    # 🔥 缓存未命中或策略ID不匹配：实时加载（首次启动或策略刚切换）
                    try:
                        registry = get_strategy_registry()
                        strategy_engine = registry.instantiate_strategy(strategy_id)
                        strategy_meta = registry.get_strategy_meta(strategy_id)
                        # 更新缓存供下次使用
                        preflight_cache.update_strategy(strategy_engine, strategy_id, strategy_meta)
                        logger.debug(f"[strategy] 实时加载策略: {strategy_id}")
                    except Exception as e:
                        logger.error(f"加载策略引擎失败: {e}")
                        continue

                # 🔥 获取策略元数据用于信号标准化
                strategy_display_name = strategy_meta.get('display_name', strategy_id) if strategy_meta else strategy_id
                strategy_class_name = strategy_engine.__class__.__name__
                
                # ============================================================
                # 🔥 信号类型映射表（两个策略的信号类型定义）
                # ============================================================
                # 共同信号类型：
                #   - MAIN_TREND: 主趋势信号（开仓用，主仓位）
                #   - SUB_BOTTOM: 次级底部信号（开仓用，次仓位）
                #   - SUB_TOP: 次级顶部信号（开仓用，次仓位）
                #   - SUB_ORDER_BLOCK: 次级订单块信号（开仓用，次仓位）
                #   - NONE: 无信号
                #
                # Strategy V2 额外信号类型（止盈专用，不开仓）：
                #   - TP_BOTTOM: 止盈专用底部信号
                #   - TP_TOP: 止盈专用顶部信号
                #   - TP_ORDER_BLOCK: 止盈专用订单块信号
                # ============================================================
                
                # 主仓信号类型（使用主仓位比例）
                PRIMARY_SIGNAL_TYPES = {'MAIN_TREND'}
                
                # 次仓信号类型（使用次仓位比例）
                SECONDARY_SIGNAL_TYPES = {'SUB_BOTTOM', 'SUB_TOP', 'SUB_ORDER_BLOCK'}
                
                # 止盈专用信号类型（不开仓，仅用于止盈判断）
                TP_ONLY_SIGNAL_TYPES = {'TP_BOTTOM', 'TP_TOP', 'TP_ORDER_BLOCK'}
                
                # 默认信号类型（当策略返回的信号缺少 type 字段时使用）
                if strategy_id == 'strategy_v1':
                    default_signal_type = 'MAIN_TREND'
                elif strategy_id == 'strategy_v2':
                    default_signal_type = 'MAIN_TREND'  # V2 也默认为主趋势
                else:
                    default_signal_type = 'CUSTOM'
                
                # 🔥 打印当前策略身份（仅在策略变更时打印，避免刷屏）
                if 'last_strategy_id' not in dir() or last_strategy_id != strategy_id:
                    last_strategy_id = strategy_id
                    logger.info(f"[STRATEGY] 策略切换: {strategy_display_name} ({strategy_class_name}) | 默认信号类型: {default_signal_type}")
                    print(f"🎯 [STRATEGY] 正在使用策略: {strategy_display_name} ({strategy_class_name})")
                
                # 🔥 preloaded_data 已在并行拉取阶段准备完成
                # 数据已去除最后一根未收线K线，策略里取 iloc[-1] 就是"刚收线的那根"
                # 无需重复处理，直接使用
                
                # 扫描统计
                scan_new_closed = 0
                scan_signals = 0
                scan_orders = 0
                
                # 🔥 遍历每个币种，调用策略引擎分析
                for symbol, ticker in tickers.items():
                    if not ticker or ticker.get("last", 0) <= 0:
                        continue
                    
                    if symbol not in preloaded_data:
                        continue
                    
                    # 🔥 检查 K线数据是否滞后（关键校验）
                    # 注意：ohlcv_lag_dict 现在是嵌套字典 {symbol: {timeframe: bool}}
                    is_lag = ohlcv_lag_dict.get(symbol, {}).get(timeframe, False)
                    if is_lag:
                        # 🔥 数据滞后：交易所还没推送当前分钟的K线，禁止触发信号
                        # 防止重复使用上一分钟的K线下单
                        continue
                    
                    # 🔥 检查 K线数据是否为 stale（陈旧）
                    # 注意：ohlcv_stale_dict 现在是嵌套字典 {symbol: {timeframe: bool}}
                    is_stale = ohlcv_stale_dict.get(symbol, {}).get(timeframe, False)
                    if is_stale:
                        # 🔥 stale 数据禁止触发信号/下单
                        logger.debug(f"[scan-skip] reason=ohlcv_stale symbol={symbol} tf={timeframe}")
                        continue
                    
                    curr_price = ticker.get("last")
                    
                    # 在调用策略前做一次 DataFrame 列校验并打印列信息
                    try:
                        dfs_map = preloaded_data.get(symbol, {})
                        for tf_name, df in dfs_map.items():
                            cols = list(df.columns) if hasattr(df, 'columns') else []
                            logger.debug(f"[DEBUG] {symbol} {tf_name} df.columns = {cols}")
                            required = {'open', 'high', 'low', 'close', 'volume'}
                            if not required.issubset(set([c.lower() for c in cols])):
                                logger.error(f"数据列不完整或大小写不匹配: symbol={symbol} tf={tf_name} cols={cols}")
                                raise ValueError(f"Missing required columns for {symbol} {tf_name}")

                    except Exception as e:
                        logger.error(f"{symbol} 数据校验失败: {e}")
                        continue

                    # 🔥 调用策略引擎分析
                    try:
                        scan_results = strategy_engine.run_analysis_with_data(
                            symbol,
                            preloaded_data[symbol],
                            [timeframe]
                        )
                    except Exception as e:
                        logger.debug(f"{symbol} 策略分析失败: {e}")
                        continue
                    
                    # ============================================================
                    # 🔥 信号标准化 (Signal Normalization)
                    # 确保所有信号都包含 'action', 'type', 'symbol' 等必要字段
                    # ============================================================
                    target_signal = None
                    target_tf = None
                    target_result = None
                    
                    for result in scan_results:
                        tf = result.get('tf')
                        sig = result.get('signal')
                        
                        if sig is None or result.get('action') == 'ERROR':
                            continue
                        
                        # 🔥 信号标准化：确保 type 字段存在
                        signal_type = result.get('type')
                        if not signal_type or signal_type == 'NONE':
                            # 使用策略默认类型补全
                            signal_type = default_signal_type
                            result['type'] = signal_type
                        
                        action = result.get('action')
                        
                        # 🔥 标准化信号字典：确保包含所有必要字段
                        if sig and isinstance(sig, dict):
                            if 'type' not in sig:
                                sig['type'] = signal_type
                            if 'symbol' not in sig:
                                sig['symbol'] = symbol
                            if 'strategy_id' not in sig:
                                sig['strategy_id'] = strategy_id
                        
                        # 🔥 过滤止盈专用信号（TP_* 类型不开仓）
                        if signal_type in TP_ONLY_SIGNAL_TYPES:
                            logger.debug(f"[scan-skip] {symbol} {tf} 止盈专用信号: {signal_type}")
                            continue
                        
                        # 🔥 1m周期的顶底信号只用于止盈，不用于开仓
                        if tf == '1m' and ('TOP' in signal_type.upper() or 'BOTTOM' in signal_type.upper()):
                            continue
                        
                        # 找到有效信号
                        if action != 'HOLD':
                            # 🔥 主信号判断：使用信号类型映射表
                            # PRIMARY_SIGNAL_TYPES 中的信号使用主仓位比例
                            # SECONDARY_SIGNAL_TYPES 中的信号使用次仓位比例
                            is_primary = signal_type in PRIMARY_SIGNAL_TYPES and tf in ['1m', '3m', '5m']
                            
                            # 确定仓位比例
                            if signal_type in PRIMARY_SIGNAL_TYPES:
                                sig['weight_pct'] = main_position_pct
                            elif signal_type in SECONDARY_SIGNAL_TYPES:
                                sig['weight_pct'] = sub_position_pct
                            else:
                                # 未知类型，使用次仓位比例（保守）
                                sig['weight_pct'] = sub_position_pct
                            
                            sig['timeframe'] = tf
                            sig['is_primary'] = is_primary
                            sig['signal_category'] = 'PRIMARY' if is_primary else 'SECONDARY'
                            target_signal = sig
                            target_tf = tf
                            target_result = result
                            break
                    
                    if not target_signal:
                        continue  # 无有效信号
                    
                    action = target_signal.get('action')
                    signal_type = target_result.get('type', default_signal_type)  # 使用策略默认类型作为兜底
                    candle_time = target_result.get('candle_time')
                    
                    # 🔥 日志增强：打印最终采纳的信号详情
                    logger.debug(f"[SIGNAL] 策略生效: {strategy_id} | 信号类型: {signal_type} | 方向: {action} | 币种: {symbol} | 周期: {target_tf}")
                    
                    # 🔥 K线去重检查
                    if candle_time:
                        candle_key = (symbol, target_tf, action)
                        if not should_execute_signal(symbol, target_tf, action, candle_time):
                            logger.debug(f"信号去重: {symbol} {target_tf} {action} 已在K线 {candle_time} 处理过")
                            continue
                    
                    scan_signals += 1
                    
                    # 🔥 收集发现的信号（统一输出）
                    scan_collected_signals.append({
                        'symbol': symbol, 'tf': target_tf, 'action': action, 'type': signal_type
                    })
                    
                    # 🔥 检查顺势解对冲
                    main_pos = get_paper_position(symbol, 'long' if action == 'LONG' else 'short')
                    hedge_list = get_hedge_positions(symbol)
                    signal_action = action
                    
                    if main_pos and hedge_list:
                        should_unhook, unhook_reason = hedge_manager.check_smart_unhook(symbol, signal_action)
                        if should_unhook:
                            # 平掉所有对冲仓
                            for hedge_pos in hedge_list:
                                hedge_id = hedge_pos.get('id')
                                if hedge_id:
                                    delete_hedge_position(hedge_id)
                            scan_collected_orders.append({
                                'symbol': symbol, 'action': 'UNHOOK', 'price': curr_price,
                                'type': unhook_reason, 'is_hedge': False
                            })
                            continue
                    
                    # 🔥 检查对冲转正
                    if not main_pos and hedge_list:
                        should_inherit, inherit_pos, inherit_reason = hedge_manager.check_hedge_inheritance(symbol, signal_action)
                        if should_inherit:
                            # 将对冲仓转为主仓
                            update_paper_position(
                                symbol=symbol,
                                pos_side=inherit_pos.get('pos_side'),
                                qty=inherit_pos.get('qty'),
                                entry_price=inherit_pos.get('entry_price')
                            )
                            delete_hedge_position(inherit_pos.get('id'))
                            scan_collected_orders.append({
                                'symbol': symbol, 'action': 'INHERIT', 'price': curr_price,
                                'type': inherit_reason, 'is_hedge': False
                            })
                            continue
                    
                    # 🔥 判断是否为对冲单
                    is_hedge_order = False
                    if main_pos:
                        main_side = main_pos.get('pos_side', 'long').upper()
                        if signal_action.upper() != main_side:
                            can_hedge, hedge_reason = hedge_manager.can_open_hedge(symbol)
                            if not can_hedge:
                                logger.debug(f"{symbol} 无法开对冲仓: {hedge_reason}")
                                continue
                            is_hedge_order = True
                    
                    # 🔥 构建计划订单
                    position_pct = sub_position_pct if is_hedge_order else main_position_pct
                    # 使用预检查缓存的权益（零延迟）
                    _cached_equity = preflight_status['equity']
                    position_size = _cached_equity * position_pct if _cached_equity > 0 else base_position_size
                    
                    order_type_str = "对冲单" if is_hedge_order else "主仓单"
                    
                    plan_order = {
                        "symbol": symbol,
                        "side": "buy" if signal_action == "LONG" else "sell",
                        "amount": position_size / curr_price,
                        "order_type": "market",
                        "posSide": "long" if signal_action == "LONG" else "short",
                        "tdMode": OKX_TD_MODE,
                        "leverage": max_lev,
                        "candle_time": candle_time,
                        "is_hedge": is_hedge_order,
                        "signal_type": signal_type
                    }
                    
                    # 🔥 将信号写入数据库（持久化）
                    # 使用K线时间戳而不是当前时间戳，便于与TradingView对标
                    signal_ts = candle_time if candle_time else int(time.time() * 1000)
                    insert_signal_event(
                        symbol=symbol,
                        timeframe=target_tf,
                        ts=signal_ts,
                        signal_type=action,
                        price=curr_price,
                        reason=target_result.get('reason', signal_type)
                    )
                    
                    logger.debug(f"发现信号: {symbol} {signal_action} ({order_type_str}) | 周期: {target_tf}")
                    
                    # 🔥 预风控检查（使用预检查缓存，零延迟）
                    if not preflight_status['can_open_new'] and not is_hedge_order:
                        logger.debug(f"{symbol} 预风控拦截: 仅允许对冲仓 ({preflight_status['check_reason']})")
                        plan_order = None
                        continue
                    
                    # 跳出循环，处理第一个有效信号
                    break
                
                # 扫描摘要记录到DEBUG（统一输出在循环结束后）
                logger.debug(f"[scan-tf] {timeframe} signals={scan_signals} orders={scan_orders}")
            
                # 🔥 首次扫描跳过交易（预热后的第一次扫描只计算信号，不执行下单）
                if is_first_scan_after_warmup and plan_order:
                    logger.info(f"[scan] 首次扫描跳过交易 | {plan_order.get('symbol')} {plan_order.get('side')} | 原因: 预热后首次扫描")
                    print(f"   ⚠️ 首次扫描跳过交易: {plan_order.get('symbol')} {plan_order.get('side')} (预热后首次扫描)")
                    plan_order = None  # 清除订单，不执行
            
                # 执行下单
                if plan_order:
                    # 根据RUN_MODE和allow_live判断是否执行真实下单
                    # 注意: can_execute_real_order, can_execute_paper_order, blocked_reasons 已在上方初始化
                    
                    # P1修复: 日损失限制检查（使用预检查缓存的权益）
                    if preflight_status['equity'] > 0:
                        can_trade, reason = risk_control.can_trade(preflight_status['equity'])
                        if not can_trade:
                            blocked_reasons.append(f"daily_loss_limit: {reason}")
                            logger.warning(f"🚨 日损失限制触发: {reason}")
                    
                    if run_mode == "live":
                        # 实盘交易需要满足严格条件
                        if pause_trading != 0:
                            blocked_reasons.append("trading_paused")
                        if control.get("allow_live", 0) != 1:
                            blocked_reasons.append("live_trading_not_allowed")
                        if "posSide" not in plan_order:
                            blocked_reasons.append("missing_pos_side")
                        if enable_trading != 1:
                            blocked_reasons.append("trading_disabled")
                        
                        can_execute_real_order = len(blocked_reasons) == 0
                    elif run_mode == "paper":
                        # 实盘测试不需要allow_live，但需要满足其他条件
                        if pause_trading != 0:
                            blocked_reasons.append("trading_paused")
                        if "posSide" not in plan_order:
                            blocked_reasons.append("missing_pos_side")
                        if enable_trading != 1:
                            blocked_reasons.append("trading_disabled")
                        
                        can_execute_paper_order = len(blocked_reasons) == 0
                    else:  # sim模式
                        blocked_reasons.append("simulation_mode")
                        can_execute_real_order = False
                        can_execute_paper_order = False
                
                if can_execute_real_order:
                    try:
                        # P1修复: 价格偏离保护（滑点检查）
                        symbol = plan_order["symbol"]
                        signal_price = tickers.get(symbol, {}).get("last", 0)
                        if signal_price > 0:
                            # 重新获取最新价格
                            try:
                                fresh_ticker = provider.get_ticker(symbol)
                                current_price = fresh_ticker.get("last", signal_price)
                                price_deviation = abs(current_price - signal_price) / signal_price
                                MAX_PRICE_DEVIATION = 0.02  # 2% 最大价格偏离
                                
                                if price_deviation > MAX_PRICE_DEVIATION:
                                    logger.warning(f"价格偏离过大: {symbol} 信号价={signal_price:.2f} 当前价={current_price:.2f} 偏离={price_deviation*100:.2f}%")
                                    blocked_reasons.append(f"price_deviation_{price_deviation*100:.1f}%")
                                    can_execute_real_order = False
                            except Exception as e:
                                logger.warning(f"获取最新价格失败: {e}，继续执行")
                        
                        if not can_execute_real_order:
                            raise ValueError(f"订单被拦截: {blocked_reasons}")
                        
                        # P1修复: 确保仓位模式正确（双向持仓）
                        if hasattr(exchange, 'ensure_position_mode'):
                            exchange.ensure_position_mode(hedged=True)
                        
                        # P1修复: 下单前设置杠杆
                        if 'leverage' in plan_order and hasattr(exchange, 'ensure_leverage'):
                            exchange.ensure_leverage(plan_order["symbol"], plan_order["leverage"])
                        
                        # P0修复: 生成唯一订单ID (clOrdId)
                        import uuid
                        cl_ord_id = f"b_{plan_order['symbol'].split('/')[0][:4]}_{int(time.time()*1000) % 10000000000}_{uuid.uuid4().hex[:6]}"
                        
                        # 执行真实订单
                        order_result = exchange.create_order(
                            symbol=plan_order["symbol"],
                            side=plan_order["side"],
                            amount=plan_order["amount"],
                            order_type=plan_order["order_type"],
                            params={
                                "posSide": plan_order["posSide"],
                                "tdMode": plan_order["tdMode"],
                                "clOrdId": cl_ord_id  # P0修复: 幂等性保护
                            }
                        )
                        
                        # 记录订单发送日志
                        extra = {
                            'symbol': plan_order["symbol"],
                            'cycle_id': cycle_id,
                            'latency_ms': int((time.time() - cycle_start_time) * 1000),
                            'mode': run_mode
                        }
                        order_id = order_result.get('id') or order_result.get('order_id', 'unknown')
                        logger.debug(f"订单发送成功: order_id={order_id} clOrdId={cl_ord_id} | 周期: {timeframe}", extra=extra)
                        
                        # P0修复: 订单状态确认（最多重试3次，每次间隔0.5秒）
                        order_confirmed = False
                        for retry in range(3):
                            try:
                                time.sleep(0.5)
                                # 查询订单状态
                                order_status = exchange.exchange.fetch_order(order_id, plan_order["symbol"])
                                status = order_status.get('status', 'unknown')
                                filled = order_status.get('filled', 0)
                                
                                if status in ['closed', 'filled']:
                                    logger.debug(f"订单确认成功: {order_id} status={status} filled={filled}")
                                    order_confirmed = True
                                    break
                                elif status in ['canceled', 'rejected', 'expired']:
                                    logger.warning(f"订单被拒绝/取消: {order_id} status={status}")
                                    break
                                else:
                                    logger.debug(f"订单状态: {order_id} status={status} (重试 {retry+1}/3)")
                            except Exception as e:
                                logger.debug(f"查询订单状态失败 (重试 {retry+1}/3): {e}")
                        
                        if not order_confirmed:
                            logger.warning(f"订单状态未确认: {order_id}，请手动检查")
                        
                        # 订单执行成功后，使持仓、余额和相关行情缓存失效
                        symbol = plan_order["symbol"]
                        provider.invalidate_positions()
                        provider.invalidate_balance()
                        provider.invalidate_ohlcv(symbol)
                        provider.invalidate_ticker(symbol)
                        
                        # 🔥 收集订单信息（统一输出）
                        action = 'LONG' if plan_order['posSide'] == 'long' else 'SHORT'
                        scan_collected_orders.append({
                            'symbol': symbol, 'action': action, 'price': signal_price,
                            'type': plan_order.get('signal_type', 'UNKNOWN'), 'is_hedge': plan_order.get('is_hedge', False)
                        })
                        scan_orders += 1
                    except Exception as e:
                        logger.error(f"真实订单执行失败: {e}")
                        update_engine_status(last_error=str(e))
                        cycle_error_count += 1
                elif can_execute_paper_order:
                    try:
                        # 执行模拟订单（paper模式）
                        symbol = plan_order["symbol"]
                        last_price = tickers.get(symbol, {}).get("last", 0)
                        is_hedge = plan_order.get("is_hedge", False)
                        
                        if last_price <= 0:
                            logger.error(f"行情不可用，无法执行模拟订单: {symbol}")
                            continue
                        
                        # 🔥 对冲单特殊处理：直接写入对冲仓位表
                        if is_hedge:
                            success, msg = hedge_manager.open_hedge_position(
                                symbol=symbol,
                                pos_side=plan_order["posSide"],
                                qty=plan_order["amount"],
                                entry_price=last_price,
                                signal_type=plan_order.get("signal_type", "HEDGE")
                            )
                            
                            if success:
                                # 添加模拟成交记录
                                add_paper_fill(
                                    ts=int(time.time() * 1000),
                                    symbol=symbol,
                                    side=plan_order["side"],
                                    pos_side=plan_order["posSide"],
                                    qty=plan_order["amount"],
                                    price=last_price,
                                    fee=0,
                                    note=f"对冲开仓: {plan_order.get('signal_type', 'HEDGE')}"
                                )
                                
                                signal_type = plan_order.get('signal_type', 'HEDGE')
                                action = 'LONG' if plan_order['posSide'] == 'long' else 'SHORT'
                                
                                # 🔥 收集订单信息（统一输出）
                                scan_collected_orders.append({
                                    'symbol': symbol, 'action': action, 'price': last_price,
                                    'type': signal_type, 'is_hedge': True
                                })
                                scan_orders += 1
                            else:
                                logger.debug(f"对冲单被拒: {msg}")
                        else:
                            # 🔥 主仓单：使用原有的模拟撮合逻辑
                            result = simulate_fill(plan_order, last_price)
                            
                            # 更新模拟余额
                            update_paper_balance(
                                equity=result['balance']['equity'],
                                available=result['balance']['available'],
                                updated_at=result['balance']['updated_at']
                            )
                            
                            # 更新模拟持仓
                            for pos_key, pos_data in result['positions'].items():
                                update_paper_position(
                                    pos_data['symbol'],
                                    pos_data['pos_side'],
                                    qty=pos_data['qty'],
                                    entry_price=pos_data['entry_price'],
                                    unrealized_pnl=pos_data['unrealized_pnl'],
                                    updated_at=int(time.time())
                                )
                            
                            # 添加模拟成交记录
                            fill_data = result['fill']
                            add_paper_fill(
                                ts=fill_data['ts'],
                                symbol=fill_data['symbol'],
                                side=fill_data['side'],
                                pos_side=fill_data['pos_side'],
                                qty=fill_data['qty'],
                                price=fill_data['price'],
                                fee=fill_data['fee'],
                                note=fill_data['note']
                            )
                            
                            # 🔥 收集订单信息（统一输出）
                            signal_type = plan_order.get('signal_type', 'UNKNOWN')
                            action = 'LONG' if plan_order['posSide'] == 'long' else 'SHORT'
                            scan_collected_orders.append({
                                'symbol': symbol, 'action': action, 'price': last_price,
                                'type': signal_type, 'is_hedge': False
                            })
                        
                        scan_orders += 1
                        
                        # 使模拟持仓和余额缓存失效（如果有的话）
                        # 注意：这里不需要使交易所的缓存失效，因为paper模式不与交易所交互
                    except Exception as e:
                        logger.error(f"模拟订单执行失败: {e}")
                        update_engine_status(last_error=str(e))
                        cycle_error_count += 1
                elif plan_order is not None:
                    # 订单被拦截，记录拦截原因（只有当plan_order存在时才记录）
                    extra = {
                        'symbol': plan_order.get("symbol", "-"),
                        'cycle_id': cycle_id,
                        'latency_ms': int((time.time() - cycle_start_time) * 1000),
                        'mode': run_mode
                    }
                    logger.debug(f"订单被拦截: 原因={','.join(blocked_reasons)} | 周期: {timeframe}", extra=extra)
                    
                    # 记录模拟订单（仅日志）
                    logger.debug(f"模拟订单: {json.dumps(plan_order)} (run_mode: {run_mode}, pause_trading: {pause_trading}, allow_live: {control.get('allow_live')}) | 周期: {timeframe}")
            
            # 计算循环耗时
            cycle_time = int((time.time() - cycle_start_time) * 1000)
            cycle_elapsed = time.time() - cycle_start_time
            
            # 获取性能指标
            metrics = provider.get_metrics() if provider else {}
            metrics["cycle_ms"] = cycle_time
            
            # 更新引擎状态
            # 【B】修复: 安全处理 plan_order，确保不会因为未定义而报错
            try:
                plan_order_json = json.dumps(plan_order) if plan_order else "{}"
            except Exception:
                plan_order_json = "{}"
            
            update_engine_status(
                ts=int(time.time() * 1000),
                alive=1,
                cycle_ms=cycle_time,
                last_error="",
                run_mode=run_mode,
                pause_trading=pause_trading,
                last_plan_order_json=plan_order_json
            )
            
            try:
                # 记录性能指标
                insert_performance_metrics(metrics)
                
                # 重置错误计数
                cycle_error_count = 0
                
                # 🔥 重置首次扫描标记（预热后的第一次扫描已完成）
                if is_first_scan_after_warmup:
                    is_first_scan_after_warmup = False
                    logger.info("[scan] 首次扫描完成，后续扫描将正常执行交易")
                
                # 🔥 统一输出扫描块状摘要
                render_scan_block(
                    time_str=scan_time_str,
                    timeframes=due_timeframes,
                    symbols_count=len(TRADE_SYMBOLS),
                    price_ok=scan_price_ok,
                    risk_status=scan_risk_status,
                    equity=preflight_status['equity'],
                    remaining_base=preflight_status['remaining_base'],
                    signals=scan_collected_signals,
                    orders=scan_collected_orders,
                    elapsed_sec=cycle_elapsed,
                    logger=logger
                )
                
            except Exception as e:
                cycle_error_count += 1
                extra = {
                    'symbol': '-',
                    'cycle_id': cycle_id,
                    'latency_ms': 0,
                    'mode': run_mode
                }
                logger.error(f"循环执行错误: {e}", extra=extra)
                update_engine_status(
                    alive=1,
                    last_error=str(e),
                    run_mode=run_mode
                )
                
                # 检查最大错误数
                if cycle_error_count >= MAX_CYCLE_ERRORS:
                    logger.error(f"连续错误数达到上限 ({MAX_CYCLE_ERRORS})，引擎将停止", extra=extra)
                    update_engine_status(alive=0)
                    if EXIT_ON_FATAL:
                        sys.exit(1)
                    break
                
                # 错误后延迟更长时间
                time.sleep(SCAN_INTERVAL_SEC * 2)
                continue
        else:
            # 未触发扫描时，低延迟空转
            time.sleep(0.01)  # 10ms空转，提高扫描精度
    
    print(f"\n{'='*70}")
    print("🛑 交易引擎已停止")
    print(f"{'='*70}")
    logger.debug("交易引擎已停止")

if __name__ == "__main__":
    main()
