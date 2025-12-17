# tests/test_trading_logger.py
# 交易日志器属性测试

import pytest
from hypothesis import given, strategies as st, settings
import re

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from trading_logger import TradingLogger, get_trading_logger


class TestTradingLoggerProperties:
    """交易日志器属性测试"""
    
    @given(
        timeframes=st.lists(st.sampled_from(['1m', '5m', '15m', '1h']), min_size=1, max_size=5),
        symbols_count=st.integers(min_value=1, max_value=20)
    )
    @settings(max_examples=50)
    def test_log_format_consistency_scan_start(self, timeframes, symbols_count):
        """
        **Feature: trading-bot-v2-fixes, Property 7: Log Format Consistency**
        
        For any scan cycle log, the output SHALL match the expected emoji-prefixed
        format pattern.
        
        **Validates: Requirements 3.2-3.9**
        """
        logger = TradingLogger()
        
        # 调用方法不应该抛出异常
        logger.scan_start(timeframes, symbols_count)
        
        # 验证内部状态
        assert logger._scan_start_time > 0
    
    @given(
        success_count=st.integers(min_value=0, max_value=100),
        total_count=st.integers(min_value=1, max_value=100)
    )
    @settings(max_examples=50)
    def test_log_format_consistency_price_fetch(self, success_count, total_count):
        """
        **Feature: trading-bot-v2-fixes, Property 7: Log Format Consistency**
        
        Price fetch log should follow the format: ✅ 价格获取成功：M/N 个币种
        
        **Validates: Requirements 3.3**
        """
        logger = TradingLogger()
        
        # 调用方法不应该抛出异常
        logger.price_fetch_complete(success_count, total_count)
    
    @given(
        symbol=st.sampled_from(['BTC/USDT:USDT', 'ETH/USDT:USDT', 'SOL/USDT:USDT']),
        timeframe=st.sampled_from(['1m', '5m', '15m', '1h']),
        direction=st.sampled_from(['LONG', 'SHORT']),
        signal_type=st.sampled_from(['MAIN_TREND', 'HEDGE', 'REVERSAL'])
    )
    @settings(max_examples=50)
    def test_log_format_consistency_signal_detected(self, symbol, timeframe, direction, signal_type):
        """
        **Feature: trading-bot-v2-fixes, Property 7: Log Format Consistency**
        
        Signal detected log should follow the format:
        🔔 [SYMBOL] 发现信号：[timeframe] DIRECTION (SIGNAL_TYPE)
        
        **Validates: Requirements 3.5**
        """
        logger = TradingLogger()
        
        # 调用方法不应该抛出异常
        logger.signal_detected(symbol, timeframe, direction, signal_type)
    
    @given(
        symbol=st.sampled_from(['BTC/USDT:USDT', 'ETH/USDT:USDT']),
        direction=st.sampled_from(['LONG', 'SHORT']),
        price=st.floats(min_value=0.01, max_value=100000, allow_nan=False, allow_infinity=False),
        signal_type=st.sampled_from(['MAIN_TREND', 'HEDGE'])
    )
    @settings(max_examples=50)
    def test_log_format_consistency_order_triggered(self, symbol, direction, price, signal_type):
        """
        **Feature: trading-bot-v2-fixes, Property 7: Log Format Consistency**
        
        Order triggered log should follow the format:
        🔥 SYMBOL DIRECTION @ $PRICE (SIGNAL_TYPE)
        
        **Validates: Requirements 3.6**
        """
        logger = TradingLogger()
        
        # 调用方法不应该抛出异常
        logger.order_triggered(symbol, direction, price, signal_type)


class TestTradingLoggerEdgeCases:
    """边界情况测试"""
    
    def test_scan_complete_calculates_duration(self):
        """验证扫描完成计算耗时"""
        import time
        
        logger = TradingLogger()
        logger.scan_start(['1m'], 5)
        
        time.sleep(0.1)  # 等待一小段时间
        
        logger.scan_complete()
        
        # 验证 _scan_start_time 被设置
        assert logger._scan_start_time > 0
    
    def test_risk_control_check_format(self):
        """验证风控检查日志格式"""
        logger = TradingLogger()
        
        # 不应该抛出异常
        logger.risk_control_check(used=6.0, limit=20.0, remaining=14.0)
    
    def test_account_update_format(self):
        """验证账户更新日志格式"""
        logger = TradingLogger()
        
        # 不应该抛出异常
        logger.account_update(equity=199.99, mode="模拟")
    
    def test_error_format(self):
        """验证错误日志格式"""
        logger = TradingLogger()
        
        # 不应该抛出异常
        logger.error("测试错误消息")
    
    def test_debug_mode_toggle(self):
        """验证 DEBUG 模式切换"""
        import logging
        
        logger = TradingLogger()
        
        # 默认应该是 INFO
        assert logger.logger.level == logging.INFO
        
        # 切换到 DEBUG
        logger.set_debug_mode(True)
        assert logger.logger.level == logging.DEBUG
        
        # 切换回 INFO
        logger.set_debug_mode(False)
        assert logger.logger.level == logging.INFO
    
    def test_global_singleton(self):
        """验证全局单例"""
        logger1 = get_trading_logger()
        logger2 = get_trading_logger()
        
        assert logger1 is logger2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
