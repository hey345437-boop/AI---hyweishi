# -*- coding: utf-8 -*-
"""
全面指标准确性测试

注意：此测试需要 pandas_ta 库，该库是可选依赖。
如果未安装 pandas_ta，测试将被跳过。
"""
import pytest
import numpy as np
import pandas as pd

# 检查 pandas_ta 是否可用
try:
    import pandas_ta as ta
    HAS_PANDAS_TA = True
except ImportError:
    HAS_PANDAS_TA = False

pytestmark = pytest.mark.skipif(not HAS_PANDAS_TA, reason="pandas_ta not installed")

from ai.ai_indicators import calc_ema, calc_rsi, calc_macd, calc_atr, calc_boll, calc_kdj, calc_ma, calc_obv, calc_vwap


@pytest.fixture
def test_data():
    """生成测试数据"""
    np.random.seed(42)
    n = 500
    base_price = 50000.0
    returns = np.random.randn(n) * 0.02
    closes = base_price * np.cumprod(1 + returns)
    highs = closes * (1 + np.abs(np.random.randn(n) * 0.01))
    lows = closes * (1 - np.abs(np.random.randn(n) * 0.01))
    opens = (highs + lows) / 2
    volumes = np.random.uniform(1000, 10000, n)
    
    df = pd.DataFrame({
        'open': opens,
        'high': highs,
        'low': lows,
        'close': closes,
        'volume': volumes
    })
    return df, closes, highs, lows, volumes


def check_accuracy(custom, reference, tolerance=1.0):
    """检查准确性，返回相对差异百分比"""
    valid_mask = ~np.isnan(custom) & ~np.isnan(reference)
    if not valid_mask.any():
        return None
    diff = np.abs(custom[valid_mask] - reference[valid_mask])
    max_diff = np.max(diff)
    ref_mean = np.mean(np.abs(reference[valid_mask]))
    rel_diff = max_diff / ref_mean * 100 if ref_mean > 0 else 0
    return rel_diff


class TestIndicatorAccuracy:
    """指标准确性测试"""
    
    def test_ma(self, test_data):
        """测试 MA"""
        df, closes, _, _, _ = test_data
        custom_ma = calc_ma(closes, 20)
        ta_ma = ta.sma(df['close'], length=20)
        rel_diff = check_accuracy(custom_ma, ta_ma.values)
        assert rel_diff is not None and rel_diff < 1.0
    
    def test_ema(self, test_data):
        """测试 EMA"""
        df, closes, _, _, _ = test_data
        custom_ema = calc_ema(closes, 12)
        ta_ema = ta.ema(df['close'], length=12)
        rel_diff = check_accuracy(custom_ema, ta_ema.values)
        assert rel_diff is not None and rel_diff < 1.0
    
    def test_rsi(self, test_data):
        """测试 RSI"""
        df, closes, _, _, _ = test_data
        custom_rsi = calc_rsi(closes, 14)
        ta_rsi = ta.rsi(df['close'], length=14)
        rel_diff = check_accuracy(custom_rsi, ta_rsi.values)
        assert rel_diff is not None and rel_diff < 1.0
    
    def test_atr(self, test_data):
        """测试 ATR"""
        df, _, highs, lows, _ = test_data
        closes = df['close'].values
        custom_atr = calc_atr(highs, lows, closes, 14)
        ta_atr = ta.atr(df['high'], df['low'], df['close'], length=14)
        rel_diff = check_accuracy(custom_atr, ta_atr.values)
        assert rel_diff is not None and rel_diff < 1.0
    
    def test_obv(self, test_data):
        """测试 OBV"""
        df, closes, _, _, volumes = test_data
        custom_obv = calc_obv(closes, volumes)
        ta_obv = ta.obv(df['close'], df['volume'])
        rel_diff = check_accuracy(custom_obv, ta_obv.values)
        assert rel_diff is not None and rel_diff < 1.0
