# -*- coding: utf-8 -*-
"""
Pytest 配置文件

提供测试 fixtures 和通用配置
"""
import os
import sys
import pytest

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture
def sample_ohlcv():
    """示例 K 线数据"""
    return [
        [1704067200000, 42000.0, 42500.0, 41800.0, 42300.0, 1000.0],
        [1704070800000, 42300.0, 42800.0, 42100.0, 42600.0, 1200.0],
        [1704074400000, 42600.0, 43000.0, 42400.0, 42900.0, 1100.0],
        [1704078000000, 42900.0, 43200.0, 42700.0, 43100.0, 900.0],
        [1704081600000, 43100.0, 43500.0, 43000.0, 43400.0, 1300.0],
    ]


@pytest.fixture
def sample_indicators():
    """示例技术指标"""
    return {
        "rsi": 55.0,
        "macd": 150.0,
        "macd_signal": 120.0,
        "macd_hist": 30.0,
        "ema_20": 42500.0,
        "ema_50": 42000.0,
        "atr": 500.0,
        "adx": 25.0,
    }


@pytest.fixture
def mock_env(monkeypatch):
    """模拟环境变量"""
    monkeypatch.setenv("RUN_MODE", "paper")
    monkeypatch.setenv("OKX_API_KEY", "test_key")
    monkeypatch.setenv("OKX_API_SECRET", "test_secret")
    monkeypatch.setenv("OKX_API_PASSPHRASE", "test_pass")
