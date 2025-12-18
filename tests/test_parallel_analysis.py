"""
测试并行策略分析功能
"""
import pytest
import time
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestParallelAnalysis:
    """测试并行分析功能"""
    
    def test_analyze_symbol_function_exists(self):
        """测试 _analyze_symbol 函数存在"""
        from separated_system.trade_engine import _analyze_symbol
        assert callable(_analyze_symbol)
    
    def test_get_strategy_executor_returns_executor(self):
        """测试线程池获取函数"""
        from separated_system.trade_engine import get_strategy_executor
        executor = get_strategy_executor()
        assert executor is not None
        # 验证是 ThreadPoolExecutor
        from concurrent.futures import ThreadPoolExecutor
        assert isinstance(executor, ThreadPoolExecutor)
    
    def test_executor_is_singleton(self):
        """测试线程池是单例模式"""
        from separated_system.trade_engine import get_strategy_executor
        executor1 = get_strategy_executor()
        executor2 = get_strategy_executor()
        assert executor1 is executor2
    
    def test_analyze_symbol_returns_none_for_invalid_input(self):
        """测试无效输入返回 None"""
        from separated_system.trade_engine import _analyze_symbol
        
        # 空 ticker
        result = _analyze_symbol((
            'BTC/USDT:USDT', None, {}, '1m', {}, {}, None
        ))
        assert result is None
        
        # ticker 价格为 0
        result = _analyze_symbol((
            'BTC/USDT:USDT', {'last': 0}, {}, '1m', {}, {}, None
        ))
        assert result is None
        
        # symbol_data 为 None
        result = _analyze_symbol((
            'BTC/USDT:USDT', {'last': 100}, None, '1m', {}, {}, None
        ))
        assert result is None
    
    def test_analyze_symbol_skips_lag_data(self):
        """测试跳过滞后数据"""
        from separated_system.trade_engine import _analyze_symbol
        import pandas as pd
        
        # 创建模拟数据
        df = pd.DataFrame({'close': [100, 101, 102]})
        symbol_data = {'1m': df}
        ohlcv_lag_dict = {'BTC/USDT:USDT': {'1m': True}}  # 标记为滞后
        
        result = _analyze_symbol((
            'BTC/USDT:USDT', {'last': 100}, symbol_data, '1m',
            ohlcv_lag_dict, {}, None
        ))
        assert result is None
    
    def test_analyze_symbol_skips_stale_data(self):
        """测试跳过陈旧数据"""
        from separated_system.trade_engine import _analyze_symbol
        import pandas as pd
        
        # 创建模拟数据
        df = pd.DataFrame({'close': [100, 101, 102]})
        symbol_data = {'1m': df}
        ohlcv_stale_dict = {'BTC/USDT:USDT': {'1m': True}}  # 标记为陈旧
        
        result = _analyze_symbol((
            'BTC/USDT:USDT', {'last': 100}, symbol_data, '1m',
            {}, ohlcv_stale_dict, None
        ))
        assert result is None


class TestParallelPerformance:
    """测试并行性能"""
    
    def test_parallel_execution_faster_than_serial(self):
        """测试并行执行比串行快（模拟场景）"""
        from concurrent.futures import ThreadPoolExecutor
        import time
        
        def slow_task(x):
            """模拟耗时任务"""
            time.sleep(0.05)  # 50ms
            return x * 2
        
        tasks = list(range(8))  # 8个任务
        
        # 串行执行
        serial_start = time.time()
        serial_results = [slow_task(x) for x in tasks]
        serial_time = time.time() - serial_start
        
        # 并行执行
        parallel_start = time.time()
        with ThreadPoolExecutor(max_workers=4) as executor:
            parallel_results = list(executor.map(slow_task, tasks))
        parallel_time = time.time() - parallel_start
        
        # 验证结果一致
        assert serial_results == parallel_results
        
        # 验证并行更快（至少快 2 倍）
        assert parallel_time < serial_time / 2, f"并行: {parallel_time:.3f}s, 串行: {serial_time:.3f}s"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
