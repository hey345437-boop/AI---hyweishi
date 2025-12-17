# tests/test_candle_tracker.py
# K线收线追踪器属性测试

import pytest
from hypothesis import given, strategies as st, settings, assume

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from candle_tracker import CandleClosureTracker, get_candle_tracker, format_timestamp_beijing


class TestCandleClosureTrackerProperties:
    """K线收线追踪器属性测试"""
    
    @given(
        candle_ts=st.integers(min_value=1600000000000, max_value=1800000000000),
        timeframe=st.sampled_from(['1m', '5m', '15m', '1h', '4h']),
        offset_ratio=st.floats(min_value=0.0, max_value=2.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=100)
    def test_signal_only_uses_closed_candles(self, candle_ts, timeframe, offset_ratio):
        """
        **Feature: trading-bot-v2-fixes, Property 5: Signal Only Uses Closed Candles**
        
        For any signal calculation, the candles used SHALL only include those
        where server_time >= candle_ts + timeframe_duration.
        
        **Validates: Requirements 2.2, 2.3**
        """
        tracker = CandleClosureTracker()
        duration_ms = tracker.get_timeframe_ms(timeframe)
        
        # 计算服务器时间（相对于K线收线时间的偏移）
        candle_close_time = candle_ts + duration_ms
        server_time = int(candle_ts + duration_ms * offset_ratio)
        
        # 判断K线是否收线
        is_closed = tracker.is_candle_closed(candle_ts, timeframe, server_time)
        
        # 验证：当 server_time >= candle_close_time 时，K线应该已收线
        expected_closed = server_time >= candle_close_time
        assert is_closed == expected_closed, \
            f"Expected is_closed={expected_closed}, got {is_closed} " \
            f"(server_time={server_time}, candle_close_time={candle_close_time})"
    
    @given(
        symbol=st.sampled_from(['BTC/USDT:USDT', 'ETH/USDT:USDT', 'SOL/USDT:USDT']),
        timeframe=st.sampled_from(['1m', '5m', '15m', '1h']),
        ts1=st.integers(min_value=1600000000000, max_value=1700000000000),
        ts2=st.integers(min_value=1700000000001, max_value=1800000000000)
    )
    @settings(max_examples=100)
    def test_no_duplicate_signal_for_same_candle(self, symbol, timeframe, ts1, ts2):
        """
        **Feature: trading-bot-v2-fixes, Property 6: No Duplicate Signal for Same Candle**
        
        For any symbol and timeframe, a signal SHALL NOT be triggered more than
        once for the same candle_ts.
        
        **Validates: Requirements 2.5**
        """
        tracker = CandleClosureTracker()
        
        # 确保 ts2 > ts1
        assume(ts2 > ts1)
        
        # 第一次检查：应该是新K线
        assert tracker.has_new_closed_candle(symbol, timeframe, ts1), \
            "First candle should be detected as new"
        
        # 更新追踪
        tracker.update_last_closed(symbol, timeframe, ts1)
        
        # 第二次检查同一时间戳：不应该是新K线
        assert not tracker.has_new_closed_candle(symbol, timeframe, ts1), \
            "Same candle should not be detected as new again"
        
        # 第三次检查更新的时间戳：应该是新K线
        assert tracker.has_new_closed_candle(symbol, timeframe, ts2), \
            "Newer candle should be detected as new"


class TestCandleClosureTrackerEdgeCases:
    """边界情况测试"""
    
    def test_get_closed_candles_filters_correctly(self):
        """验证 get_closed_candles 正确过滤"""
        tracker = CandleClosureTracker()
        
        # 创建测试数据：3根K线，间隔1分钟
        base_ts = 1700000000000
        ohlcv = [
            [base_ts, 100, 110, 90, 105, 1000],           # K线1
            [base_ts + 60000, 105, 115, 95, 110, 1100],   # K线2
            [base_ts + 120000, 110, 120, 100, 115, 1200], # K线3（正在形成）
        ]
        
        # 服务器时间在K线3开始后30秒（K线3未收线）
        server_time = base_ts + 120000 + 30000
        
        closed = tracker.get_closed_candles(ohlcv, '1m', server_time)
        
        # 应该只有前2根K线已收线
        assert len(closed) == 2
        assert closed[0][0] == base_ts
        assert closed[1][0] == base_ts + 60000
    
    def test_should_calculate_signal_new_candle(self):
        """验证 should_calculate_signal 检测新K线"""
        tracker = CandleClosureTracker()
        
        symbol = 'BTC/USDT:USDT'
        timeframe = '1m'
        base_ts = 1700000000000
        
        ohlcv = [
            [base_ts, 100, 110, 90, 105, 1000],
            [base_ts + 60000, 105, 115, 95, 110, 1100],
        ]
        
        # 服务器时间在K线2收线后
        server_time = base_ts + 120000 + 1000
        
        # 第一次检查：应该计算信号
        should_calc, candle, reason = tracker.should_calculate_signal(
            symbol, timeframe, ohlcv, server_time
        )
        assert should_calc
        assert reason == "new_candle"
        assert candle[0] == base_ts + 60000
        
        # 更新追踪
        tracker.update_last_closed(symbol, timeframe, candle[0])
        
        # 第二次检查：不应该计算信号（同一K线）
        should_calc, candle, reason = tracker.should_calculate_signal(
            symbol, timeframe, ohlcv, server_time
        )
        assert not should_calc
        assert reason == "no_new_candle"
    
    def test_timeframe_normalization(self):
        """验证日线时间周期规范化"""
        tracker = CandleClosureTracker()
        
        # 1d 和 1D 应该规范化为 1Dutc
        assert tracker.normalize_timeframe('1d') == '1Dutc'
        assert tracker.normalize_timeframe('1D') == '1Dutc'
        
        # 其他周期不变
        assert tracker.normalize_timeframe('1m') == '1m'
        assert tracker.normalize_timeframe('1h') == '1h'
    
    def test_format_timestamp_beijing(self):
        """验证北京时间转换"""
        # 2024-01-01 00:00:00 UTC
        ts_ms = 1704067200000
        
        beijing_str = format_timestamp_beijing(ts_ms)
        
        # 北京时间应该是 2024-01-01 08:00:00
        assert '2024-01-01 08:00:00' == beijing_str
    
    def test_clear_tracking(self):
        """验证清除追踪记录"""
        tracker = CandleClosureTracker()
        
        # 添加一些记录
        tracker.update_last_closed('BTC/USDT:USDT', '1m', 1700000000000)
        tracker.update_last_closed('ETH/USDT:USDT', '1m', 1700000000000)
        tracker.update_last_closed('BTC/USDT:USDT', '5m', 1700000000000)
        
        # 清除特定交易对
        tracker.clear(symbol='BTC/USDT:USDT')
        
        # BTC 记录应该被清除
        assert tracker.get_last_closed_ts('BTC/USDT:USDT', '1m') == 0
        assert tracker.get_last_closed_ts('BTC/USDT:USDT', '5m') == 0
        
        # ETH 记录应该保留
        assert tracker.get_last_closed_ts('ETH/USDT:USDT', '1m') == 1700000000000


class TestCandleSignalTrackerProperties:
    """K线信号追踪器属性测试"""
    
    @given(
        candle_ts=st.integers(min_value=1600000000000, max_value=1800000000000),
        timeframe=st.sampled_from(['1m', '5m', '15m', '1h', '4h']),
        offset_seconds=st.integers(min_value=0, max_value=59)
    )
    @settings(max_examples=100)
    def test_signal_uses_current_candle(self, candle_ts, timeframe, offset_seconds):
        """
        **Feature: trading-bot-v2-fixes, Property 5: Signal Uses Current Candle**
        
        For any signal calculation triggered at 59 seconds, the signal evaluation
        SHALL include the current incomplete candle (the candle where
        candle_open_ts <= current_time < candle_close_time).
        
        **Validates: Requirements 2.2, 2.3**
        """
        from candle_tracker import CandleSignalTracker
        
        tracker = CandleSignalTracker()
        duration_ms = tracker.get_timeframe_ms(timeframe)
        
        # 创建测试K线数据
        # 当前时间在 candle_ts 开始后 offset_seconds 秒
        current_time = candle_ts + offset_seconds * 1000
        
        # 确保 current_time 在 K 线周期内
        candle_close_time = candle_ts + duration_ms
        assume(current_time < candle_close_time)
        
        # 创建 OHLCV 数据
        ohlcv = [
            [candle_ts - duration_ms, 100, 110, 90, 105, 1000],  # 前一根K线
            [candle_ts, 105, 115, 95, 110, 1100],                 # 当前K线
        ]
        
        # 获取当前K线
        current_candle_ts = tracker.get_current_candle_ts(ohlcv, timeframe, current_time)
        
        # 验证：当前K线应该是 candle_ts（未收盘的K线）
        assert current_candle_ts == candle_ts, \
            f"Expected current candle ts={candle_ts}, got {current_candle_ts}"
    
    @given(
        symbol=st.sampled_from(['BTC/USDT:USDT', 'ETH/USDT:USDT', 'SOL/USDT:USDT']),
        timeframe=st.sampled_from(['1m', '5m', '15m', '1h']),
        candle_ts=st.integers(min_value=1600000000000, max_value=1800000000000)
    )
    @settings(max_examples=100)
    def test_no_duplicate_signal_for_same_candle_signal_tracker(self, symbol, timeframe, candle_ts):
        """
        **Feature: trading-bot-v2-fixes, Property 6: No Duplicate Signal for Same Candle**
        
        For any symbol and timeframe, a signal SHALL NOT be triggered more than
        once for the same candle_open_ts.
        
        **Validates: Requirements 2.4, 2.5**
        """
        from candle_tracker import CandleSignalTracker
        
        tracker = CandleSignalTracker()
        
        # 第一次检查：不应该已触发
        assert not tracker.has_signal_triggered(symbol, timeframe, candle_ts), \
            "Signal should not be triggered initially"
        
        # 记录信号
        tracker.record_signal(symbol, timeframe, candle_ts)
        
        # 第二次检查：应该已触发
        assert tracker.has_signal_triggered(symbol, timeframe, candle_ts), \
            "Signal should be marked as triggered after recording"
        
        # 不同的 candle_ts 不应该受影响
        different_ts = candle_ts + 60000
        assert not tracker.has_signal_triggered(symbol, timeframe, different_ts), \
            "Different candle should not be affected"


class TestCandleSignalTrackerEdgeCases:
    """CandleSignalTracker 边界情况测试"""
    
    def test_get_current_candle_at_59_seconds(self):
        """验证在 59 秒时获取当前 K 线"""
        from candle_tracker import CandleSignalTracker
        
        tracker = CandleSignalTracker()
        
        # 创建测试数据：当前时间是 K 线开始后 59 秒
        base_ts = 1700000000000
        ohlcv = [
            [base_ts - 60000, 100, 110, 90, 105, 1000],  # 前一根K线（已收盘）
            [base_ts, 105, 115, 95, 110, 1100],          # 当前K线（未收盘）
        ]
        
        # 当前时间：K 线开始后 59 秒
        current_time = base_ts + 59000
        
        # 获取当前 K 线
        current_candle = tracker.get_current_candle(ohlcv, '1m', current_time)
        
        # 应该返回当前未收盘的 K 线
        assert current_candle is not None
        assert current_candle[0] == base_ts
    
    def test_should_trigger_signal_prevents_duplicate(self):
        """验证 should_trigger_signal 防止重复触发"""
        from candle_tracker import CandleSignalTracker
        
        tracker = CandleSignalTracker()
        
        symbol = 'BTC/USDT:USDT'
        timeframe = '1m'
        base_ts = 1700000000000
        
        ohlcv = [
            [base_ts - 60000, 100, 110, 90, 105, 1000],
            [base_ts, 105, 115, 95, 110, 1100],
        ]
        
        current_time = base_ts + 59000
        
        # 第一次：应该触发
        should_trigger, candle_ts, reason = tracker.should_trigger_signal(
            symbol, timeframe, ohlcv, current_time, signal_detected=True
        )
        assert should_trigger
        assert reason == "new_signal"
        assert candle_ts == base_ts
        
        # 记录信号
        tracker.record_signal(symbol, timeframe, candle_ts)
        
        # 第二次：不应该触发（已触发过）
        should_trigger, candle_ts, reason = tracker.should_trigger_signal(
            symbol, timeframe, ohlcv, current_time, signal_detected=True
        )
        assert not should_trigger
        assert reason == "already_triggered"
    
    def test_cleanup_old_signals(self):
        """验证清理过期信号记录"""
        from candle_tracker import CandleSignalTracker
        
        tracker = CandleSignalTracker()
        tracker.MAX_SIGNAL_HISTORY = 5  # 设置较小的值便于测试
        
        # 添加超过限制的记录
        for i in range(10):
            tracker.record_signal('BTC/USDT:USDT', '1m', 1700000000000 + i * 60000)
        
        # 应该只保留最新的 5 条
        assert tracker.get_triggered_count() == 5
        
        # 最旧的记录应该被清理
        assert not tracker.has_signal_triggered('BTC/USDT:USDT', '1m', 1700000000000)
        
        # 最新的记录应该保留
        assert tracker.has_signal_triggered('BTC/USDT:USDT', '1m', 1700000000000 + 9 * 60000)
    
    def test_clear_signal_tracking(self):
        """验证清除信号追踪记录"""
        from candle_tracker import CandleSignalTracker
        
        tracker = CandleSignalTracker()
        
        # 添加记录
        tracker.record_signal('BTC/USDT:USDT', '1m', 1700000000000)
        tracker.record_signal('ETH/USDT:USDT', '1m', 1700000000000)
        
        # 清除特定交易对
        tracker.clear(symbol='BTC/USDT:USDT')
        
        # BTC 记录应该被清除
        assert not tracker.has_signal_triggered('BTC/USDT:USDT', '1m', 1700000000000)
        
        # ETH 记录应该保留
        assert tracker.has_signal_triggered('ETH/USDT:USDT', '1m', 1700000000000)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
