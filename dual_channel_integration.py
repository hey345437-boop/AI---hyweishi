# dual_channel_integration.py
# 双通道信号系统集成模块 - 简化交易引擎的集成
#
# 使用方法：
# 1. 在 trade_engine.py 中导入此模块
# 2. 调用 process_dual_channel_scan() 替代原有的信号计算逻辑
# 3. 使用 DualChannelLogger 输出日志

from typing import Dict, List, Optional, Any
from datetime import datetime
import logging

# 导入双通道组件
from dual_channel_ohlcv import DualChannelOHLCV, get_incremental_fetcher
from dual_channel_tracker import Signal, get_intrabar_tracker, get_confirmed_tracker
from dual_channel_engine import DualChannelSignalEngine, ScanResult, get_dual_channel_engine
from dual_channel_logger import DualChannelLogger, get_dual_channel_logger
from beijing_time_converter import BeijingTimeConverter

logger = logging.getLogger(__name__)


class DualChannelIntegration:
    """
    双通道信号系统集成类
    
    提供简化的接口，用于在交易引擎中集成双通道信号计算
    """
    
    def __init__(
        self,
        strategy: Any,
        execution_mode: str = "intrabar",
        use_print: bool = True
    ):
        """
        初始化集成模块
        
        Args:
            strategy: 策略引擎实例
            execution_mode: 执行模式 "intrabar" | "confirmed" | "both"
            use_print: 是否使用 print 输出日志
        """
        self.engine = DualChannelSignalEngine(strategy, execution_mode)
        self.logger = DualChannelLogger(use_print=use_print)
        self.incremental_fetcher = get_incremental_fetcher()
    
    def process_scan(
        self,
        provider: Any,
        symbol: str,
        timeframe: str,
        scan_time: str = None
    ) -> Optional[ScanResult]:
        """
        处理单个交易对的扫描
        
        Args:
            provider: MarketDataProvider 实例
            symbol: 交易对
            timeframe: 时间周期
            scan_time: 扫描时间 HH:MM:SS
        
        Returns:
            ScanResult 或 None（如果数据不足）
        """
        if scan_time is None:
            scan_time = datetime.now().strftime('%H:%M:%S')
        
        # 获取双通道K线数据
        dual_channel = provider.get_dual_channel_ohlcv(symbol, timeframe)
        
        if dual_channel is None:
            logger.warning(f"No dual channel data for {symbol}/{timeframe}")
            return None
        
        # 计算信号
        result = self.engine.process_scan(dual_channel, scan_time)
        
        return result
    
    def process_multi_symbol_scan(
        self,
        provider: Any,
        symbols: List[str],
        timeframe: str,
        scan_time: str = None
    ) -> Dict[str, ScanResult]:
        """
        处理多个交易对的扫描
        
        Args:
            provider: MarketDataProvider 实例
            symbols: 交易对列表
            timeframe: 时间周期
            scan_time: 扫描时间 HH:MM:SS
        
        Returns:
            {symbol: ScanResult} 字典
        """
        if scan_time is None:
            scan_time = datetime.now().strftime('%H:%M:%S')
        
        results = {}
        total_intrabar_fired = 0
        total_confirmed_new = 0
        
        # 获取第一个有效的 forming_ts 和 closed_ts（用于摘要日志）
        first_forming_ts = 0
        first_closed_ts = 0
        
        for symbol in symbols:
            result = self.process_scan(provider, symbol, timeframe, scan_time)
            if result:
                results[symbol] = result
                total_intrabar_fired += result.intrabar_fired_count
                total_confirmed_new += result.confirmed_new_count
                
                if first_forming_ts == 0:
                    first_forming_ts = result.forming_ts
                    first_closed_ts = result.closed_ts
        
        # 输出聚合摘要日志
        if first_forming_ts > 0:
            self.logger.log_scan_summary(
                tf=timeframe,
                scan_time=scan_time,
                forming_ts=first_forming_ts,
                closed_ts=first_closed_ts,
                intrabar_fired=total_intrabar_fired,
                confirmed_new=total_confirmed_new
            )
        
        # 输出各个信号的详细日志
        for symbol, result in results.items():
            for signal in result.intrabar_signals:
                self.logger.log_intrabar_trade(
                    action=signal.action,
                    symbol=signal.symbol,
                    price=signal.price,
                    forming_ts=signal.candle_ts
                )
            
            for signal in result.confirmed_signals:
                # 只输出没有对应盘中信号的收线信号
                has_intrabar = any(
                    s.symbol == signal.symbol and s.action == signal.action
                    for s in result.intrabar_signals
                )
                if not has_intrabar:
                    self.logger.log_confirmed_signal(
                        action=signal.action,
                        symbol=signal.symbol,
                        closed_ts=signal.candle_ts
                    )
        
        return results
    
    def get_execution_signals(
        self,
        results: Dict[str, ScanResult]
    ) -> List[Signal]:
        """
        从扫描结果中获取用于执行的信号
        
        Args:
            results: {symbol: ScanResult} 字典
        
        Returns:
            用于执行的 Signal 列表
        """
        signals = []
        
        for symbol, result in results.items():
            signal = self.engine.get_execution_signal(result)
            if signal:
                signals.append(signal)
        
        return signals
    
    def set_execution_mode(self, mode: str) -> None:
        """设置执行模式"""
        self.engine.set_execution_mode(mode)
    
    def clear_trackers(self) -> None:
        """清除所有追踪器记录"""
        self.engine.clear_trackers()


# 全局单例
_dual_channel_integration: Optional[DualChannelIntegration] = None


def get_dual_channel_integration(
    strategy: Any = None,
    execution_mode: str = "intrabar",
    use_print: bool = True
) -> DualChannelIntegration:
    """
    获取全局 DualChannelIntegration 实例
    
    Args:
        strategy: 策略引擎实例（首次调用时必须提供）
        execution_mode: 执行模式
        use_print: 是否使用 print 输出
    
    Returns:
        DualChannelIntegration 实例
    """
    global _dual_channel_integration
    
    if _dual_channel_integration is None:
        if strategy is None:
            raise ValueError("Strategy must be provided for first initialization")
        _dual_channel_integration = DualChannelIntegration(
            strategy, execution_mode, use_print
        )
    elif strategy is not None:
        # 更新策略
        _dual_channel_integration.engine.strategy = strategy
    
    return _dual_channel_integration


def process_59_second_scan(
    provider: Any,
    strategy: Any,
    symbols: List[str],
    timeframes: List[str],
    execution_mode: str = "intrabar"
) -> Dict[str, Dict[str, ScanResult]]:
    """
    处理59秒扫描（便捷函数）
    
    Args:
        provider: MarketDataProvider 实例
        strategy: 策略引擎实例
        symbols: 交易对列表
        timeframes: 时间周期列表
        execution_mode: 执行模式
    
    Returns:
        {timeframe: {symbol: ScanResult}} 嵌套字典
    """
    integration = get_dual_channel_integration(strategy, execution_mode)
    scan_time = datetime.now().strftime('%H:%M:%S')
    
    all_results = {}
    
    for tf in timeframes:
        results = integration.process_multi_symbol_scan(
            provider, symbols, tf, scan_time
        )
        all_results[tf] = results
    
    return all_results


def get_all_execution_signals(
    all_results: Dict[str, Dict[str, ScanResult]]
) -> List[Signal]:
    """
    从所有扫描结果中获取执行信号
    
    Args:
        all_results: {timeframe: {symbol: ScanResult}} 嵌套字典
    
    Returns:
        所有用于执行的 Signal 列表
    """
    integration = get_dual_channel_integration()
    signals = []
    
    for tf, results in all_results.items():
        tf_signals = integration.get_execution_signals(results)
        signals.extend(tf_signals)
    
    return signals
