# candle_time_utils.py
# K线时间处理工具 - 计算层与展示层分离
#
# 核心原则：
# 1. 计算层（信号、回测、下单）统一使用 UTC 毫秒时间戳
# 2. 所有 candle_time 以 OKX/CCXT 返回的 timestamp(ms) 为准
# 3. 禁止用本地 time.time() 推断K线归属
# 4. 只允许使用"已收线K线"计算信号
# 5. 展示层（Streamlit K线图）必须转成北京时间

import pandas as pd
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Tuple, Dict
import logging

logger = logging.getLogger(__name__)

# 北京时区 (UTC+8)
BEIJING_TZ = timezone(timedelta(hours=8))

# 时间周期到毫秒的映射
TIMEFRAME_MS: Dict[str, int] = {
    '1m': 60 * 1000,
    '3m': 3 * 60 * 1000,
    '5m': 5 * 60 * 1000,
    '15m': 15 * 60 * 1000,
    '30m': 30 * 60 * 1000,
    '1h': 60 * 60 * 1000,
    '2h': 2 * 60 * 60 * 1000,
    '4h': 4 * 60 * 60 * 1000,
    '6h': 6 * 60 * 60 * 1000,
    '12h': 12 * 60 * 60 * 1000,
    # 日线周期说明：
    # - OKX 的 '1D' 使用 UTC+8 边界（北京时间 00:00）
    # - OKX 的 '1Dutc' 使用 UTC 边界（UTC 00:00）
    # - TradingView 默认使用 UTC 边界
    # - 为与 TradingView 对齐，建议使用 '1Dutc'
    '1d': 24 * 60 * 60 * 1000,
    '1D': 24 * 60 * 60 * 1000,
    '1Dutc': 24 * 60 * 60 * 1000,  # 推荐：与 TradingView 对齐
    '1w': 7 * 24 * 60 * 60 * 1000,
    '1W': 7 * 24 * 60 * 60 * 1000,
}

# OKX 日线周期配置
# 重要：选择与 TradingView 对齐的周期
# - '1D': OKX 默认日线，使用 UTC+8 边界
# - '1Dutc': UTC 边界日线，与 TradingView 对齐
OKX_DAILY_TIMEFRAME = '1Dutc'  # 推荐使用 UTC 边界


def get_timeframe_ms(timeframe: str) -> int:
    """获取时间周期的毫秒数"""
    return TIMEFRAME_MS.get(timeframe, 60 * 1000)


def normalize_daily_timeframe(timeframe: str) -> str:
    """
    规范化日线周期
    
    为与 TradingView 对齐，日线统一使用 UTC 边界
    
    Args:
        timeframe: 原始时间周期
    
    Returns:
        规范化后的时间周期
    """
    if timeframe in ('1d', '1D'):
        return OKX_DAILY_TIMEFRAME
    return timeframe


def is_candle_closed(candle_ts: int, timeframe: str, server_time: int) -> bool:
    """
    判断K线是否已收线
    
    K线收线条件: server_time >= candle_ts + timeframe_duration
    
    Args:
        candle_ts: K线开始时间戳 (UTC ms) - 必须来自 OKX/CCXT
        timeframe: 时间周期
        server_time: 服务器当前时间 (UTC ms) - 必须来自 OKX/CCXT
    
    Returns:
        True 如果K线已收线
    """
    duration_ms = get_timeframe_ms(timeframe)
    candle_close_time = candle_ts + duration_ms
    return server_time >= candle_close_time


def get_closed_candles(
    ohlcv: List[List],
    timeframe: str,
    server_time: int
) -> List[List]:
    """
    从 OHLCV 数据中筛选已收线K线
    
    重要：只有已收线的K线才能用于信号计算
    
    Args:
        ohlcv: OHLCV 数据列表 [[ts, o, h, l, c, v], ...]
        timeframe: 时间周期
        server_time: 服务器当前时间 (UTC ms)
    
    Returns:
        只包含已收线K线的列表
    """
    if not ohlcv:
        return []
    
    closed = []
    for candle in ohlcv:
        candle_ts = candle[0]
        if is_candle_closed(candle_ts, timeframe, server_time):
            closed.append(candle)
    
    return closed


def get_latest_closed_candle(
    ohlcv: List[List],
    timeframe: str,
    server_time: int
) -> Optional[List]:
    """
    获取最新的已收线K线
    
    Args:
        ohlcv: OHLCV 数据列表
        timeframe: 时间周期
        server_time: 服务器当前时间 (UTC ms)
    
    Returns:
        最新的已收线K线，或 None
    """
    closed = get_closed_candles(ohlcv, timeframe, server_time)
    if closed:
        return closed[-1]
    return None


def get_server_time_from_ohlcv(ohlcv: List[List], timeframe: str) -> int:
    """
    从 OHLCV 数据推断服务器时间
    
    使用最新K线的收盘时间作为服务器时间的近似值
    这比使用本地 time.time() 更准确
    
    Args:
        ohlcv: OHLCV 数据列表
        timeframe: 时间周期
    
    Returns:
        推断的服务器时间 (UTC ms)
    """
    if not ohlcv:
        return 0
    
    latest_candle_ts = ohlcv[-1][0]
    duration_ms = get_timeframe_ms(timeframe)
    
    # 假设最新K线是当前正在形成的K线
    # 服务器时间 ≈ 最新K线开始时间 + 一些偏移
    # 保守估计：使用最新K线的开始时间
    return latest_candle_ts


# ============ 展示层：UTC 转北京时间 ============

def utc_ms_to_beijing(ts_ms: int) -> datetime:
    """
    将 UTC 毫秒时间戳转换为北京时间 datetime
    
    Args:
        ts_ms: UTC 毫秒时间戳
    
    Returns:
        北京时间 datetime 对象
    """
    utc_dt = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc)
    return utc_dt.astimezone(BEIJING_TZ)


def utc_ms_to_beijing_str(ts_ms: int, fmt: str = '%Y-%m-%d %H:%M:%S') -> str:
    """
    将 UTC 毫秒时间戳转换为北京时间字符串
    
    Args:
        ts_ms: UTC 毫秒时间戳
        fmt: 时间格式字符串
    
    Returns:
        北京时间字符串
    """
    beijing_dt = utc_ms_to_beijing(ts_ms)
    return beijing_dt.strftime(fmt)


def convert_ohlcv_to_beijing_df(ohlcv: List[List]) -> pd.DataFrame:
    """
    将 OHLCV 数据转换为带北京时间的 DataFrame
    
    用于 Streamlit UI 展示
    
    Args:
        ohlcv: OHLCV 数据列表 [[ts, o, h, l, c, v], ...]
    
    Returns:
        DataFrame with columns: ts, open, high, low, close, volume, dt_utc, dt_bj
    """
    if not ohlcv:
        return pd.DataFrame()
    
    df = pd.DataFrame(ohlcv, columns=['ts', 'open', 'high', 'low', 'close', 'volume'])
    
    # UTC 时间（计算层使用）
    df['dt_utc'] = pd.to_datetime(df['ts'], unit='ms', utc=True)
    
    # 北京时间（展示层使用）
    df['dt_bj'] = df['dt_utc'].dt.tz_convert('Asia/Shanghai')
    
    return df


def format_scan_summary(
    timeframe: str,
    symbols_count: int,
    new_closed_count: int,
    signals_count: int,
    orders_count: int
) -> str:
    """
    格式化扫描摘要（单行输出）
    
    Args:
        timeframe: 时间周期
        symbols_count: 扫描的币种数量
        new_closed_count: 新收线K线数量
        signals_count: 检测到的信号数量
        orders_count: 生成的订单数量
    
    Returns:
        格式化的摘要字符串
    """
    return (
        f"[scan] tf={timeframe} symbols={symbols_count} "
        f"newClosed={new_closed_count} signals={signals_count} orders={orders_count}"
    )


# ============ 信号去重追踪器 ============

class ClosedCandleSignalTracker:
    """
    已收线K线信号追踪器
    
    核心原则：
    1. 只使用已收线K线计算信号
    2. 同一根K线只触发一次信号
    3. 没有新收线K线时不重复触发
    """
    
    def __init__(self):
        # {(symbol, timeframe): last_closed_candle_ts}
        self._last_closed: Dict[Tuple[str, str], int] = {}
        
        # {(symbol, timeframe, candle_ts): signal_type}
        self._triggered_signals: Dict[Tuple[str, str, int], str] = {}
    
    def check_new_closed_candle(
        self,
        symbol: str,
        timeframe: str,
        ohlcv: List[List],
        server_time: int
    ) -> Tuple[bool, Optional[List], str]:
        """
        检查是否有新的已收线K线
        
        Args:
            symbol: 交易对
            timeframe: 时间周期
            ohlcv: OHLCV 数据
            server_time: 服务器时间 (UTC ms)
        
        Returns:
            (has_new_closed, latest_closed_candle, reason)
        """
        # 获取已收线K线
        closed_candles = get_closed_candles(ohlcv, timeframe, server_time)
        
        if not closed_candles:
            return False, None, "no_closed_candles"
        
        latest_closed = closed_candles[-1]
        latest_closed_ts = latest_closed[0]
        
        # 检查是否有新的收线K线
        key = (symbol, timeframe)
        last_ts = self._last_closed.get(key, 0)
        
        if latest_closed_ts <= last_ts:
            return False, latest_closed, "no_new_candle"
        
        return True, latest_closed, "new_candle"
    
    def update_last_closed(
        self,
        symbol: str,
        timeframe: str,
        closed_ts: int
    ) -> None:
        """更新最后收线时间戳"""
        key = (symbol, timeframe)
        self._last_closed[key] = closed_ts
    
    def get_last_closed_ts(
        self,
        symbol: str,
        timeframe: str
    ) -> int:
        """获取最后收线时间戳"""
        key = (symbol, timeframe)
        return self._last_closed.get(key, 0)
    
    def has_signal_triggered(
        self,
        symbol: str,
        timeframe: str,
        candle_ts: int
    ) -> bool:
        """检查该K线是否已触发过信号"""
        key = (symbol, timeframe, candle_ts)
        return key in self._triggered_signals
    
    def record_signal(
        self,
        symbol: str,
        timeframe: str,
        candle_ts: int,
        signal_type: str
    ) -> None:
        """记录信号触发"""
        key = (symbol, timeframe, candle_ts)
        self._triggered_signals[key] = signal_type
        
        # 清理过期记录（保留最近 100 条）
        if len(self._triggered_signals) > 100:
            sorted_keys = sorted(
                self._triggered_signals.keys(),
                key=lambda k: k[2]
            )
            for k in sorted_keys[:-100]:
                del self._triggered_signals[k]
    
    def should_calculate_signal(
        self,
        symbol: str,
        timeframe: str,
        ohlcv: List[List],
        server_time: int
    ) -> Tuple[bool, Optional[List], str]:
        """
        判断是否应该计算信号
        
        综合判断：
        1. 是否有新的已收线K线
        2. 该K线是否已触发过信号
        
        Args:
            symbol: 交易对
            timeframe: 时间周期
            ohlcv: OHLCV 数据
            server_time: 服务器时间 (UTC ms)
        
        Returns:
            (should_calculate, latest_closed_candle, reason)
        """
        # 检查是否有新的已收线K线
        has_new, latest_closed, reason = self.check_new_closed_candle(
            symbol, timeframe, ohlcv, server_time
        )
        
        if not has_new:
            return False, latest_closed, reason
        
        latest_closed_ts = latest_closed[0]
        
        # 检查是否已触发过信号
        if self.has_signal_triggered(symbol, timeframe, latest_closed_ts):
            return False, latest_closed, "already_triggered"
        
        return True, latest_closed, "new_candle"
    
    def clear(self, symbol: str = None, timeframe: str = None) -> None:
        """清除追踪记录"""
        if symbol is None and timeframe is None:
            self._last_closed.clear()
            self._triggered_signals.clear()
        else:
            # 清除 _last_closed
            keys_to_remove = [
                k for k in self._last_closed
                if (symbol is None or k[0] == symbol) and
                   (timeframe is None or k[1] == timeframe)
            ]
            for k in keys_to_remove:
                del self._last_closed[k]
            
            # 清除 _triggered_signals
            keys_to_remove = [
                k for k in self._triggered_signals
                if (symbol is None or k[0] == symbol) and
                   (timeframe is None or k[1] == timeframe)
            ]
            for k in keys_to_remove:
                del self._triggered_signals[k]


# 全局单例
_closed_candle_tracker: Optional[ClosedCandleSignalTracker] = None


def get_closed_candle_tracker() -> ClosedCandleSignalTracker:
    """获取全局 ClosedCandleSignalTracker 实例"""
    global _closed_candle_tracker
    if _closed_candle_tracker is None:
        _closed_candle_tracker = ClosedCandleSignalTracker()
    return _closed_candle_tracker
