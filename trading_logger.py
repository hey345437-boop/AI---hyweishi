# trading_logger.py
# 交易日志器 - 支持 INFO/DEBUG 分级，emoji 格式化输出

import logging
import time
from datetime import datetime
from typing import List, Optional


class TradingLogger:
    """
    交易日志器 - 支持 INFO/DEBUG 分级
    
    日志格式:
    - [HH:MM:SS] 触发扫描 | 周期：[timeframes] | 币种：N
    - ✅ 价格获取成功：M/N 个币种
    - ℹ️ 使用缓存的预风控结果：{result}
    - 🔔 [SYMBOL] 发现信号：[timeframe] DIRECTION (SIGNAL_TYPE)
    - 🔥 SYMBOL DIRECTION @ $PRICE (SIGNAL_TYPE)
    - ✅ 本轮扫描完成 | 耗时：X.XXs
    - 📊 模拟账户更新 | 净值：$XXX.XX
    - ✅ 预风控：已用 $X.XX / 限额 $XX.XX, 剩余 $XX.XX
    - ❌ {error_message}
    """
    
    def __init__(self, name: str = "trading", level: int = logging.INFO):
        """
        初始化交易日志器
        
        Args:
            name: 日志器名称
            level: 默认日志级别
        """
        self.logger = logging.getLogger(name)
        self.logger.setLevel(level)
        self._scan_start_time: float = 0
        self._debug_mode: bool = False
    
    def set_debug_mode(self, enabled: bool) -> None:
        """设置 DEBUG 模式"""
        self._debug_mode = enabled
        if enabled:
            self.logger.setLevel(logging.DEBUG)
        else:
            self.logger.setLevel(logging.INFO)
    
    def _get_time_str(self) -> str:
        """获取当前时间字符串 HH:MM:SS"""
        return datetime.now().strftime('%H:%M:%S')
    
    def scan_start(
        self,
        timeframes: List[str],
        symbols_count: int
    ) -> None:
        """
        记录扫描开始
        格式: [HH:MM:SS] 触发扫描 | 周期：[timeframes] | 币种：N
        """
        self._scan_start_time = time.time()
        tf_str = str(timeframes)
        self.logger.info(f"🔄 [{self._get_time_str()}] 触发扫描 | 周期：{tf_str} | 币种：{symbols_count}")
    
    def price_fetch_complete(
        self,
        success_count: int,
        total_count: int
    ) -> None:
        """
        记录价格获取完成
        格式: ✅ 价格获取成功：M/N 个币种
        """
        self.logger.info(f"✅ 价格获取成功：{success_count}/{total_count} 个币种")
    
    def risk_control_cached(self, result: str) -> None:
        """
        记录使用缓存的风控结果
        格式: ℹ️ 使用缓存的预风控结果：{result}
        """
        self.logger.info(f"ℹ️ 使用缓存的预风控结果：{result}")
    
    def signal_detected(
        self,
        symbol: str,
        timeframe: str,
        direction: str,
        signal_type: str
    ) -> None:
        """
        记录发现信号
        格式: 🔔 [SYMBOL] 发现信号：[timeframe] DIRECTION (SIGNAL_TYPE)
        """
        self.logger.info(f"🔔 [{symbol}] 发现信号：[{timeframe}] {direction} ({signal_type})")
    
    def order_triggered(
        self,
        symbol: str,
        direction: str,
        price: float,
        signal_type: str
    ) -> None:
        """
        记录触发下单
        格式: 🔥 SYMBOL DIRECTION @ $PRICE (SIGNAL_TYPE)
        """
        self.logger.info(f"🔥 {symbol} {direction} @ ${price:.4f} ({signal_type})")
    
    def scan_complete(self, extra_info: str = "") -> None:
        """
        记录扫描完成
        格式: ✅ 本轮扫描完成 | 耗时：X.XXs
        """
        duration = time.time() - self._scan_start_time if self._scan_start_time > 0 else 0
        msg = f"✅ 本轮扫描完成 | 耗时：{duration:.2f}秒"
        if extra_info:
            msg += f" | {extra_info}"
        self.logger.info(msg)
    
    def account_update(self, equity: float, mode: str = "模拟") -> None:
        """
        记录账户更新
        格式: 📊 模拟账户更新 | 净值：$XXX.XX
        """
        self.logger.info(f"📊 {mode}账户更新 | 净值：${equity:,.2f}")
    
    def risk_control_check(
        self,
        used: float,
        limit: float,
        remaining: float
    ) -> None:
        """
        记录风控检查
        格式: ✅ 预风控：已用 $X.XX / 限额 $XX.XX, 剩余 $XX.XX
        """
        self.logger.info(f"✅ 预风控：已用 ${used:.2f} / 限额 ${limit:.2f}, 剩余 ${remaining:.2f}")
    
    def close_position_start(self, symbol: str) -> None:
        """记录开始平仓"""
        self.logger.info(f"🔻 开始平仓：{symbol}")
    
    def close_position_result(
        self,
        symbol: str,
        pos_side: str,
        before_sz: float,
        after_sz: float,
        status: str
    ) -> None:
        """记录平仓结果"""
        emoji = "✅" if status == "success" else "❌"
        self.logger.info(
            f"{emoji} 平仓结果：{symbol} {pos_side} | "
            f"前：{before_sz} -> 后：{after_sz} | {status}"
        )
    
    def error(self, message: str) -> None:
        """
        记录错误
        格式: ❌ {message}
        """
        self.logger.error(f"❌ {message}")
    
    def warning(self, message: str) -> None:
        """记录警告"""
        self.logger.warning(f"⚠️ {message}")
    
    def debug(self, message: str) -> None:
        """DEBUG 级别日志"""
        self.logger.debug(f"🔍 {message}")
    
    def info(self, message: str) -> None:
        """INFO 级别日志"""
        self.logger.info(message)


# 全局单例
_trading_logger: Optional[TradingLogger] = None


def get_trading_logger() -> TradingLogger:
    """获取全局 TradingLogger 实例"""
    global _trading_logger
    if _trading_logger is None:
        _trading_logger = TradingLogger()
    return _trading_logger
