# tests/test_candle_time_utils.py
# K线时间处理工具测试

import pytest
from datetime import datetime, timezone, timedelta
import pandas as pd

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from candle_time_utils import (
    get_timeframe_ms,
    normalize_daily_timeframe,
    is_candle_closed,
    get_closed_candles,
    get_latest_closed_candle,
    utc_ms_to_beijing,
    utc_ms_to_beijing_str,
    convert_ohlcv_to_beijing_df,
    format_scan_summary,
    ClosedCandleSignalTracker,
    get_closed_candle_tracker,
    OKX_DAILY_TIMEFRAME,
    BEIJING_TZ
)


class TestTimeframeMs:
    """时间周期毫秒数测试"""
    
    def test_1m_timeframe(self):
        assert get_timeframe_ms('1m') == 60 * 1000
    
    def test_5m_timeframe(self):
        assert get_timeframe_ms('5m') == 5 * 60 * 1000
    
    def test_1h_timeframe(self):
        assert get_timeframe_ms('1h') == 60 * 60 * 1000
    
    def test_1d_timeframe(self):
        assert get_timeframe_ms('1d') == 24 * 60 * 60 * 1000
    
    def test_unknown_timeframe_defaults_to_1m(self):
        assert get_timeframe_ms('unknown') == 60 * 1000


class TestNormalizeDailyTimeframe:
    """日线周期规范化测试"""
    
    def test_1d_normalized_to_utc(self):
        """1d 应该被规范化为 UTC 边界"""
        result = normalize_daily_timeframe('1d')
        assert result == OKX_DAILY_TIMEFRAME
    
    def test_1D_normalized_to_utc(self):
        """1D 应该被规范化为 UTC 边界"""
        result = normalize_daily_timeframe('1D')
        assert result == OKX_DAILY_TIMEFRAME
    
    def test_other_timeframes_unchanged(self):
        """其他周期不变"""
        assert normalize_daily_timeframe('1m') == '1m'
        assert normalize_daily_timeframe('5m') == '5m'
        assert normalize_daily_timeframe('1h') == '1h'


class TestIsCandleClosed:
    """K线收线判断测试"""
    
    def test_candle_closed(self):
        """K线已收线"""
        candle_ts = 1000000000000  # 某个时间点
        timeframe = '1m'
        server_time = candle_ts + 60 * 1000  # 1分钟后
        
        assert is_candle_closed(candle_ts, timeframe, server_time) == True
    
    def test_candle_not_closed(self):
        """K线未收线"""
        candle_ts = 1000000000000
        timeframe = '1m'
        server_time = candle_ts + 30 * 1000  # 30秒后
        
        assert is_candle_closed(candle_ts, timeframe, server_time) == False
    
    def test_candle_just_closed(self):
        """K线刚好收线"""
        candle_ts = 1000000000000
        timeframe = '1m'
        server_time = candle_ts + 60 * 1000  # 刚好1分钟
        
        assert is_candle_closed(candle_ts, timeframe, server_time) == True


class TestGetClosedCandles:
    """获取已收线K线测试"""
    
    def test_filter_closed_candles(self):
        """筛选已收线K线"""
        # 创建测试数据：3根K线，间隔1分钟
        base_ts = 1000000000000
        ohlcv = [
            [base_ts, 100, 110, 90, 105, 1000],
            [base_ts + 60000, 105, 115, 95, 110, 1100],
            [base_ts + 120000, 110, 120, 100, 115, 1200],  # 最新K线
        ]
        
        # 服务器时间在第3根K线中间
        server_time = base_ts + 150000  # 2.5分钟后
        
        closed = get_closed_candles(ohlcv, '1m', server_time)
        
        # 应该只有前2根K线已收线
        assert len(closed) == 2
        assert closed[0][0] == base_ts
        assert closed[1][0] == base_ts + 60000
    
    def test_empty_ohlcv(self):
        """空数据"""
        assert get_closed_candles([], '1m', 1000000000000) == []


class TestUtcToBeijing:
    """UTC 转北京时间测试"""
    
    def test_utc_to_beijing_datetime(self):
        """UTC 毫秒转北京时间 datetime"""
        # 2024-01-01 00:00:00 UTC
        ts_ms = 1704067200000
        
        beijing_dt = utc_ms_to_beijing(ts_ms)
        
        # 北京时间应该是 2024-01-01 08:00:00
        assert beijing_dt.hour == 8
        assert beijing_dt.day == 1
        assert beijing_dt.month == 1
    
    def test_utc_to_beijing_str(self):
        """UTC 毫秒转北京时间字符串"""
        # 2024-01-01 00:00:00 UTC
        ts_ms = 1704067200000
        
        beijing_str = utc_ms_to_beijing_str(ts_ms)
        
        assert '08:00:00' in beijing_str
    
    def test_convert_ohlcv_to_beijing_df(self):
        """OHLCV 转北京时间 DataFrame"""
        ohlcv = [
            [1704067200000, 100, 110, 90, 105, 1000],
            [1704067260000, 105, 115, 95, 110, 1100],
        ]
        
        df = convert_ohlcv_to_beijing_df(ohlcv)
        
        assert 'dt_utc' in df.columns
        assert 'dt_bj' in df.columns
        assert len(df) == 2
        
        # 检查时区
        assert df['dt_utc'].dt.tz is not None
        assert df['dt_bj'].dt.tz is not None


class TestFormatScanSummary:
    """扫描摘要格式化测试"""
    
    def test_format_scan_summary(self):
        """格式化扫描摘要"""
        summary = format_scan_summary(
            timeframe='1m',
            symbols_count=3,
            new_closed_count=1,
            signals_count=0,
            orders_count=0
        )
        
        assert '[scan]' in summary
        assert 'tf=1m' in summary
        assert 'symbols=3' in summary
        assert 'newClosed=1' in summary
        assert 'signals=0' in summary
        assert 'orders=0' in summary


class TestClosedCandleSignalTracker:
    """已收线K线信号追踪器测试"""
    
    def test_check_new_closed_candle(self):
        """检查新收线K线"""
        tracker = ClosedCandleSignalTracker()
        
        base_ts = 1000000000000
        ohlcv = [
            [base_ts, 100, 110, 90, 105, 1000],
            [base_ts + 60000, 105, 115, 95, 110, 1100],
        ]
        server_time = base_ts + 120000  # 2分钟后
        
        has_new, candle, reason = tracker.check_new_closed_candle(
            'BTC/USDT:USDT', '1m', ohlcv, server_time
        )
        
        assert has_new == True
        assert candle is not None
        assert reason == 'new_candle'
    
    def test_no_new_candle_after_update(self):
        """更新后没有新K线"""
        tracker = ClosedCandleSignalTracker()
        
        base_ts = 1000000000000
        ohlcv = [
            [base_ts, 100, 110, 90, 105, 1000],
            [base_ts + 60000, 105, 115, 95, 110, 1100],
        ]
        server_time = base_ts + 120000
        
        # 第一次检查
        has_new, candle, _ = tracker.check_new_closed_candle(
            'BTC/USDT:USDT', '1m', ohlcv, server_time
        )
        assert has_new == True
        
        # 更新最后收线时间
        tracker.update_last_closed('BTC/USDT:USDT', '1m', candle[0])
        
        # 第二次检查（相同数据）
        has_new, _, reason = tracker.check_new_closed_candle(
            'BTC/USDT:USDT', '1m', ohlcv, server_time
        )
        assert has_new == False
        assert reason == 'no_new_candle'
    
    def test_signal_deduplication(self):
        """信号去重"""
        tracker = ClosedCandleSignalTracker()
        
        candle_ts = 1000000000000
        
        # 第一次检查
        assert tracker.has_signal_triggered('BTC/USDT:USDT', '1m', candle_ts) == False
        
        # 记录信号
        tracker.record_signal('BTC/USDT:USDT', '1m', candle_ts, 'BUY')
        
        # 第二次检查
        assert tracker.has_signal_triggered('BTC/USDT:USDT', '1m', candle_ts) == True
    
    def test_should_calculate_signal(self):
        """综合判断是否应该计算信号"""
        tracker = ClosedCandleSignalTracker()
        
        base_ts = 1000000000000
        ohlcv = [
            [base_ts, 100, 110, 90, 105, 1000],
            [base_ts + 60000, 105, 115, 95, 110, 1100],
        ]
        server_time = base_ts + 120000
        
        # 第一次应该计算
        should_calc, candle, reason = tracker.should_calculate_signal(
            'BTC/USDT:USDT', '1m', ohlcv, server_time
        )
        assert should_calc == True
        assert reason == 'new_candle'
        
        # 更新并记录信号
        tracker.update_last_closed('BTC/USDT:USDT', '1m', candle[0])
        tracker.record_signal('BTC/USDT:USDT', '1m', candle[0], 'BUY')
        
        # 第二次不应该计算
        should_calc, _, reason = tracker.should_calculate_signal(
            'BTC/USDT:USDT', '1m', ohlcv, server_time
        )
        assert should_calc == False
    
    def test_clear(self):
        """清除追踪记录"""
        tracker = ClosedCandleSignalTracker()
        
        tracker.update_last_closed('BTC/USDT:USDT', '1m', 1000000000000)
        tracker.record_signal('BTC/USDT:USDT', '1m', 1000000000000, 'BUY')
        
        tracker.clear()
        
        assert tracker.get_last_closed_ts('BTC/USDT:USDT', '1m') == 0
        assert tracker.has_signal_triggered('BTC/USDT:USDT', '1m', 1000000000000) == False


class TestGlobalTracker:
    """全局追踪器测试"""
    
    def test_get_closed_candle_tracker_singleton(self):
        """全局追踪器是单例"""
        tracker1 = get_closed_candle_tracker()
        tracker2 = get_closed_candle_tracker()
        
        assert tracker1 is tracker2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
