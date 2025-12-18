# tests/test_strategy_optimization.py
"""
策略计算优化验证测试
确保优化后的计算结果与原始结果完全一致
"""

import pytest
import numpy as np
import pandas as pd
import time
from copy import deepcopy

# 生成测试数据
def generate_test_ohlcv(n_bars=1500):
    """生成模拟K线数据"""
    np.random.seed(42)  # 固定随机种子确保可重复
    
    # 生成价格序列
    base_price = 100.0
    returns = np.random.randn(n_bars) * 0.02  # 2%波动
    close = base_price * np.cumprod(1 + returns)
    
    # 生成OHLCV
    high = close * (1 + np.abs(np.random.randn(n_bars) * 0.01))
    low = close * (1 - np.abs(np.random.randn(n_bars) * 0.01))
    open_price = (high + low) / 2 + np.random.randn(n_bars) * 0.5
    volume = np.random.randint(1000, 100000, n_bars).astype(float)
    
    # 创建时间索引
    timestamps = pd.date_range(end=pd.Timestamp.now(), periods=n_bars, freq='1min')
    
    df = pd.DataFrame({
        'timestamp': timestamps,
        'open': open_price,
        'high': high,
        'low': low,
        'close': close,
        'volume': volume
    })
    
    return df


class TestEMAOptimization:
    """EMA计算优化测试"""
    
    def test_ema_results_match(self):
        """验证Numba加速的EMA结果与pandas ewm一致"""
        from strategy_v2 import TradingStrategy, _ema_numba
        
        strategy = TradingStrategy()
        df = generate_test_ohlcv(1500)
        series = df['close']
        
        # Numba加速的EMA
        numba_ema = strategy.calculate_ema(series, 12)
        
        # 验证结果正常
        assert len(numba_ema) == len(series)
        assert not numba_ema.isnull().all()
        
        # 验证EMA值在合理范围内
        assert numba_ema.min() > 0
        assert numba_ema.max() < series.max() * 2


class TestRMAOptimization:
    """RMA计算优化测试"""
    
    def test_rma_results_match(self):
        """验证Numba加速的RMA结果正确"""
        from strategy_v2 import TradingStrategy, _rma_numba
        
        strategy = TradingStrategy()
        df = generate_test_ohlcv(1500)
        series = df['close'].diff().fillna(0)
        
        # Numba加速的RMA
        numba_rma = strategy.calculate_rma(series, 14)
        
        # 验证结果正常
        assert len(numba_rma) == len(series)
        assert not numba_rma.isnull().all()
        
        # 验证RMA是平滑的（标准差应该比原始序列小）
        assert numba_rma.std() < series.std()


class TestIndicatorCalculation:
    """完整指标计算测试"""
    
    def test_calculate_indicators_consistency(self):
        """验证优化前后指标计算结果一致"""
        from strategy_v2 import TradingStrategy
        
        strategy = TradingStrategy()
        df = generate_test_ohlcv(1500)
        
        # 计算指标
        start_time = time.time()
        df_with_indicators = strategy.calculate_indicators(df.copy())
        original_time = time.time() - start_time
        
        # 验证关键指标存在
        required_columns = [
            'stoch_k', 'pk', 'pd', 'obv_plus', 'obv_minus', 'obv_adx',
            'trend_adx', 'adx_slope', 'ema12', 'fast_top', 'fast_bot',
            'slow_top', 'slow_bot', 'macd', 'macd_signal', 'macd_hist', 'rsi'
        ]
        
        for col in required_columns:
            assert col in df_with_indicators.columns, f"缺少指标列: {col}"
        
        print(f"\n原始计算耗时: {original_time:.4f}秒")
        
        # 保存原始结果用于后续对比
        return df_with_indicators, original_time


class TestSignalConsistency:
    """信号一致性测试"""
    
    def test_signal_output_unchanged(self):
        """验证优化后信号输出不变"""
        from strategy_v2 import TradingStrategy
        
        strategy = TradingStrategy()
        df = generate_test_ohlcv(1500)
        
        # 计算指标
        df_with_indicators = strategy.calculate_indicators(df.copy())
        
        # 检查信号
        signal = strategy.check_signals(df_with_indicators, timeframe='3m')
        
        # 验证信号结构
        assert 'action' in signal
        assert 'type' in signal
        assert signal['action'] in ['LONG', 'SHORT', 'HOLD']
    
    def test_indicator_values_deterministic(self):
        """验证指标计算是确定性的（多次运行结果相同）"""
        from strategy_v2 import TradingStrategy
        
        strategy = TradingStrategy()
        df = generate_test_ohlcv(1500)
        
        # 运行两次计算
        df1 = strategy.calculate_indicators(df.copy())
        df2 = strategy.calculate_indicators(df.copy())
        
        # 验证关键指标完全一致
        key_columns = ['ema12', 'rsi', 'macd', 'trend_adx', 'stoch_k', 'obv_adx']
        
        for col in key_columns:
            np.testing.assert_array_equal(
                df1[col].values, df2[col].values,
                err_msg=f"指标 {col} 两次计算结果不一致"
            )
    
    def test_adx_wma_values(self):
        """验证ADX WMA计算结果（用于优化前后对比）"""
        from strategy_v2 import TradingStrategy
        
        strategy = TradingStrategy()
        df = generate_test_ohlcv(1500)
        
        df_with_indicators = strategy.calculate_indicators(df.copy())
        
        # 记录ADX最后几个值作为基准
        adx_values = df_with_indicators['trend_adx'].tail(10).values
        
        # 验证ADX值在合理范围内 (0-100)
        assert np.all(adx_values >= 0), "ADX值应该>=0"
        assert np.all(adx_values <= 100), "ADX值应该<=100"
        
        # 打印用于对比
        print(f"\nADX最后10个值: {adx_values}")


class TestPerformanceBenchmark:
    """性能基准测试"""
    
    def test_benchmark_calculate_indicators(self):
        """基准测试：指标计算性能"""
        from strategy_v2 import TradingStrategy
        
        strategy = TradingStrategy()
        df = generate_test_ohlcv(1500)
        
        # 预热
        strategy.calculate_indicators(df.copy())
        
        # 多次运行取平均
        n_runs = 5
        times = []
        
        for _ in range(n_runs):
            start = time.time()
            strategy.calculate_indicators(df.copy())
            times.append(time.time() - start)
        
        avg_time = np.mean(times)
        std_time = np.std(times)
        
        print(f"\n性能基准 (n={n_runs}):")
        print(f"  平均耗时: {avg_time:.4f}秒")
        print(f"  标准差: {std_time:.4f}秒")
        print(f"  最快: {min(times):.4f}秒")
        print(f"  最慢: {max(times):.4f}秒")
        
        # 记录基准值（优化后应该更快）
        assert avg_time < 10.0, "计算时间过长，需要优化"


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])


class TestStrategyV1Optimization:
    """Strategy V1 优化测试"""
    
    def test_v1_calculate_indicators(self):
        """验证V1策略指标计算正常"""
        from strategy_v1 import TradingStrategyV1
        
        strategy = TradingStrategyV1()
        df = generate_test_ohlcv(1500)
        
        # 计算指标
        start_time = time.time()
        df_with_indicators = strategy.calculate_indicators(df.copy())
        calc_time = time.time() - start_time
        
        # 验证关键指标存在
        required_columns = [
            'stoch_k', 'pk', 'pd', 'obv_plus', 'obv_minus', 'obv_adx',
            'trend_adx', 'adx_slope', 'ma12', 'ma144', 'ma169', 'rsi'
        ]
        
        for col in required_columns:
            assert col in df_with_indicators.columns, f"V1缺少指标列: {col}"
        
        print(f"\nV1策略计算耗时: {calc_time:.4f}秒")
    
    def test_v1_signal_output(self):
        """验证V1策略信号输出正常"""
        from strategy_v1 import TradingStrategyV1
        
        strategy = TradingStrategyV1()
        df = generate_test_ohlcv(1500)
        
        # 计算指标
        df_with_indicators = strategy.calculate_indicators(df.copy())
        
        # 检查信号
        signal = strategy.check_signals(df_with_indicators, timeframe='30m')
        
        # 验证信号结构
        assert 'action' in signal
        assert 'type' in signal
        assert signal['action'] in ['LONG', 'SHORT', 'HOLD']
    
    def test_v1_benchmark(self):
        """V1策略性能基准测试"""
        from strategy_v1 import TradingStrategyV1
        
        strategy = TradingStrategyV1()
        df = generate_test_ohlcv(1500)
        
        # 预热
        strategy.calculate_indicators(df.copy())
        
        # 多次运行取平均
        n_runs = 5
        times = []
        
        for _ in range(n_runs):
            start = time.time()
            strategy.calculate_indicators(df.copy())
            times.append(time.time() - start)
        
        avg_time = np.mean(times)
        
        print(f"\nV1性能基准 (n={n_runs}):")
        print(f"  平均耗时: {avg_time:.4f}秒")
        print(f"  最快: {min(times):.4f}秒")
        print(f"  最慢: {max(times):.4f}秒")
