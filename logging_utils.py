import logging
import os
import sys
import io
from logging.handlers import RotatingFileHandler
from config import LOG_DIR, RUNNER_LOG_FILE


# ============ Windows UTF-8 编码修复 ============
def fix_windows_encoding():
    """修复 Windows 控制台 GBK 编码问题，强制使用 UTF-8"""
    if sys.platform.startswith('win'):
        try:
            # Python 3.7+ 推荐方式
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
            sys.stderr.reconfigure(encoding='utf-8', errors='replace')
        except AttributeError:
            # Python 3.6 兼容方式
            sys.stdout = io.TextIOWrapper(
                sys.stdout.buffer, encoding='utf-8', errors='replace', line_buffering=True
            )
            sys.stderr = io.TextIOWrapper(
                sys.stderr.buffer, encoding='utf-8', errors='replace', line_buffering=True
            )

# 在模块加载时立即执行
fix_windows_encoding()

# ============ Logger 单例缓存 ============
# 防止重复添加 handler（Streamlit rerun 常见问题）
_logger_cache = {}


class SafeStreamHandler(logging.StreamHandler):
    """安全的流处理器，确保 Unicode 字符不会导致崩溃"""
    
    def emit(self, record):
        try:
            msg = self.format(record)
            stream = self.stream
            # 尝试安全写入，无法编码的字符用 replace 处理
            try:
                stream.write(msg + self.terminator)
            except UnicodeEncodeError:
                # 回退：将无法编码的字符替换为 ?
                safe_msg = msg.encode('utf-8', errors='replace').decode('utf-8', errors='replace')
                stream.write(safe_msg + self.terminator)
            self.flush()
        except Exception:
            self.handleError(record)


class CustomFormatter(logging.Formatter):
    """自定义日志格式化器，为缺失的字段提供默认值，并确保消息安全"""
    
    def format(self, record):
        # 为缺失的字段提供默认值
        if not hasattr(record, 'symbol'):
            record.symbol = '-'
        if not hasattr(record, 'cycle_id'):
            record.cycle_id = '-'
        if not hasattr(record, 'latency_ms'):
            record.latency_ms = 0
        if not hasattr(record, 'mode'):
            record.mode = 'unknown'
        
        # 确保消息可以安全编码
        try:
            result = super().format(record)
            # 额外保险：确保结果可以被 GBK 编码（Windows 默认）
            # 如果不能，则替换问题字符
            result.encode('gbk', errors='replace')
            return result
        except Exception:
            # 如果格式化失败，返回安全的消息
            return f"[LOG FORMAT ERROR] {record.getMessage()}"

def get_logger(name: str = "runner", level=logging.INFO) -> logging.Logger:
    """获取日志记录器（工厂函数，保证同名logger只初始化一次handler）
    
    参数:
    - name: 日志记录器名称
    - level: 日志级别
    
    返回:
    - 配置好的日志记录器
    """
    global _logger_cache
    
    # 如果已缓存，直接返回
    if name in _logger_cache:
        return _logger_cache[name]
    
    # 创建日志记录器
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # 🔥 关键：关闭日志传播，防止向 root logger 传播导致重复打印
    logger.propagate = False
    
    # 如果已有 handler，不再添加（防止 Streamlit rerun 重复添加）
    if not logger.handlers:
        # 确保日志目录存在
        if not os.path.exists(LOG_DIR):
            os.makedirs(LOG_DIR)
        
        # 创建文件处理器（使用 UTF-8 编码）
        log_file = f"{name}.log" if name != "runner" else RUNNER_LOG_FILE
        file_handler = RotatingFileHandler(
            os.path.join(LOG_DIR, log_file),
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setLevel(level)
        
        # 文件使用详细格式
        file_formatter = CustomFormatter(
            "%(asctime)s - %(levelname)s - [symbol=%(symbol)s] [cycle_id=%(cycle_id)s] [latency_ms=%(latency_ms)s] [mode=%(mode)s] - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
    
    # 缓存 logger
    _logger_cache[name] = logger
    return logger


def setup_logger(name="runner", log_file=RUNNER_LOG_FILE, level=logging.INFO):
    """配置日志记录器（兼容旧接口，内部调用 get_logger）
    
    参数:
    - name: 日志记录器名称
    - log_file: 日志文件路径（已废弃，使用 name 自动生成）
    - level: 日志级别
    
    返回:
    - 配置好的日志记录器
    """
    return get_logger(name, level)


# ============ 块状扫描摘要输出 ============
def render_scan_block(
    time_str: str,
    timeframes: list,
    symbols_count: int,
    price_ok: int = 0,
    risk_status: str = "",
    equity: float = 0.0,
    remaining_base: float = 0.0,
    total_base_used: float = 0.0,
    total_margin: float = 0.0,
    signals: list = None,
    orders: list = None,
    elapsed_sec: float = 0.0,
    logger: logging.Logger = None,
    debug_timing: dict = None
):
    """
    统一的扫描块状摘要输出函数
    
    所有 scan 相关输出只能由此函数负责，禁止同时 logger.info + print 两套输出
    
    输出格式示例：
    ======================================================================
    🚀 [21:30:59] 触发扫描 | 周期: ['1m'] | 币种: 3
       ✅ 价格获取成功: 3/3
       🛡️ 使用缓存的预风控结果: 可开新主仓
       💰 账户权益: $200.00 | 已用保证金: $1.74 | 剩余额度: $18.26
       🎯 [BTC/USDT:USDT] 发现信号: [1m] LONG (TREND_REVERSAL)
       ✅ BTC/USDT:USDT LONG @ $45000.00 (TREND_REVERSAL)
    ✅ 本轮扫描完成 | 耗时: 2.00s | 信号: 1 | 订单: 1
    ======================================================================
    
    参数:
    - time_str: 时间字符串 (HH:MM:SS)
    - timeframes: 扫描的周期列表
    - symbols_count: 币种数量
    - price_ok: 价格获取成功数量
    - risk_status: 风控状态描述
    - equity: 账户权益
    - remaining_base: 剩余可用保证金额度
    - total_base_used: 仓位总名义价值（已弃用，保留兼容）
    - total_margin: 已用保证金（🔥 核心字段，用于风控显示）
    - signals: 信号列表 [{'symbol': ..., 'tf': ..., 'action': ..., 'type': ...}, ...]
    - orders: 订单列表 [{'symbol': ..., 'action': ..., 'price': ..., 'type': ..., 'is_hedge': ...}, ...]
    - elapsed_sec: 扫描耗时（秒）
    - logger: 日志记录器（仅写入文件，不输出到控制台）
    """
    signals = signals or []
    orders = orders or []
    
    lines = []
    
    # 扫描开始块
    lines.append(f"\n{'='*70}")
    lines.append(f"🚀 [{time_str}] 触发扫描 | 周期: {timeframes} | 币种: {symbols_count}")
    
    # 关键步骤（2~4行）
    if price_ok > 0:
        lines.append(f"   ✅ 价格获取成功: {price_ok}/{symbols_count}")
    
    if risk_status:
        lines.append(f"   🛡️ 使用缓存的预风控结果: {risk_status}")
    
    # 🔥 账户权益已在30秒风控检查时打印，0秒扫描不再重复打印
    
    # 信号（只有发现信号时才显示）
    for sig in signals:
        symbol = sig.get('symbol', '-')
        tf = sig.get('tf', '-')
        action = sig.get('action', '-')
        sig_type = sig.get('type', '-')
        lines.append(f"   🎯 [{symbol}] 发现信号: [{tf}] {action} ({sig_type})")
    
    # 订单（只有下单时才显示）
    for order in orders:
        symbol = order.get('symbol', '-')
        action = order.get('action', '-')
        price = order.get('price', 0)
        order_type = order.get('type', '-')
        is_hedge = order.get('is_hedge', False)
        entry_time = order.get('entry_time', '')  # 🔥 入场时间（精确到毫秒）
        
        time_str_display = f" | 入场: {entry_time}" if entry_time else ""
        
        if is_hedge:
            lines.append(f"   🛡️ {symbol} HEDGE {action} @ ${price:.4f} ({order_type}){time_str_display}")
        else:
            lines.append(f"   ✅ {symbol} {action} @ ${price:.4f} ({order_type}){time_str_display}")
    
    # 扫描结束块（1行）
    lines.append(f"✅ 本轮扫描完成 | 耗时: {elapsed_sec:.2f}s | 信号: {len(signals)} | 订单: {len(orders)}")
    
    # DEBUG耗时信息（放在本轮扫描完成之后）
    if debug_timing:
        timing_parts = []
        if 'price_fetch' in debug_timing:
            timing_parts.append(f"价格: {debug_timing['price_fetch']:.2f}s")
        if 'data_fetch' in debug_timing:
            timing_parts.append(f"数据: {debug_timing['data_fetch']:.2f}s")
        if 'signal_calc' in debug_timing:
            timing_parts.append(f"信号: {debug_timing['signal_calc']:.2f}s")
        if timing_parts:
            lines.append(f"   ⏱️ [DEBUG] {' | '.join(timing_parts)}")
    
    lines.append(f"{'='*70}")
    
    # 输出到控制台（唯一出口）
    output = "\n".join(lines)
    print(output)
    
    # 写入日志文件（不输出到控制台）
    if logger:
        # 简化的日志格式，只记录关键信息
        log_msg = f"[scan] tf={timeframes} symbols={symbols_count} signals={len(signals)} orders={len(orders)} elapsed={elapsed_sec:.2f}s"
        logger.debug(log_msg)


def render_idle_block(time_str: str, message: str, logger: logging.Logger = None):
    """
    渲染待机/暂停状态块
    
    参数:
    - time_str: 时间字符串 (HH:MM:SS)
    - message: 状态消息
    - logger: 日志记录器
    """
    output = f"\n{'='*70}\n🚨 [{time_str}] {message}\n{'='*70}"
    print(output)
    
    if logger:
        logger.debug(f"[idle] {message}")


def render_risk_check(
    time_str: str,
    equity: float,
    total_used: float,
    max_allowed: float,
    can_open: bool,
    mode: str = "paper"
):
    """
    渲染预风控检查结果（15秒/45秒时调用）
    
    参数:
    - time_str: 时间字符串
    - equity: 账户权益
    - total_used: 已用本金
    - max_allowed: 最大允许本金
    - can_open: 是否可以开新主仓
    - mode: 运行模式
    """
    remaining = max_allowed - total_used
    
    if can_open:
        print(f"  ✅ 预风控：已用 ${total_used:.2f} / 限额 ${max_allowed:.2f}，剩余 ${remaining:.2f}")
    else:
        print(f"  ⚠️ 预风控：已用 ${total_used:.2f} ≥ 限额 ${max_allowed:.2f}")
