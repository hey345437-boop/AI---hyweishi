#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
性能基准测试

测试核心模块的执行速度，用于性能回归检测。

用法:
    python scripts/benchmark.py
"""
import sys
import os
import time
import statistics

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def timeit(func, iterations=100):
    """测量函数执行时间"""
    times = []
    for _ in range(iterations):
        start = time.perf_counter()
        func()
        times.append((time.perf_counter() - start) * 1000)
    
    return {
        "mean": statistics.mean(times),
        "median": statistics.median(times),
        "stdev": statistics.stdev(times) if len(times) > 1 else 0,
        "min": min(times),
        "max": max(times)
    }


def benchmark_risk_control():
    """风控模块基准"""
    from core.risk_control import RiskControlModule, RiskControlConfig
    
    config = RiskControlConfig(max_order_size=1000.0, daily_loss_limit_pct=0.10)
    module = RiskControlModule(config)
    
    def test():
        module.validate_order(500.0, "BTC/USDT")
        module.record_trade_pnl(-10.0)
        module.can_trade(1000.0)
    
    return timeit(test, iterations=1000)


def benchmark_strategy_registry():
    """策略注册表基准"""
    from strategies.strategy_registry import (
        get_strategy_registry,
        list_all_strategies,
        validate_and_fallback_strategy
    )
    
    def test():
        registry = get_strategy_registry()
        registry.list_strategies()
        registry.get_strategy_meta("strategy_v2")
        list_all_strategies()
        validate_and_fallback_strategy("strategy_v2")
    
    return timeit(test, iterations=500)


def benchmark_ai_providers():
    """AI 服务商模块基准"""
    from ai.ai_providers import (
        get_available_providers,
        get_provider,
        get_provider_models,
        get_free_models,
        quick_validate_key_format
    )
    
    def test():
        get_available_providers()
        get_provider("deepseek")
        get_provider_models("qwen")
        get_free_models()
        quick_validate_key_format("deepseek", "sk-test123456789")
    
    return timeit(test, iterations=500)


def benchmark_indicators():
    """技术指标计算基准"""
    try:
        from ai.ai_indicators import calculate_indicators
    except ImportError:
        return None
    
    # 模拟 500 根 K 线
    import random
    base_price = 50000
    ohlcv = []
    for i in range(500):
        o = base_price + random.uniform(-500, 500)
        h = o + random.uniform(0, 200)
        l = o - random.uniform(0, 200)
        c = random.uniform(l, h)
        v = random.uniform(100, 1000)
        ohlcv.append([i * 60000, o, h, l, c, v])
        base_price = c
    
    def test():
        calculate_indicators(ohlcv)
    
    return timeit(test, iterations=50)


def main():
    print("=" * 60)
    print("何以为势 - 性能基准测试")
    print("=" * 60)
    print()
    
    benchmarks = [
        ("风控模块 (1000 次)", benchmark_risk_control),
        ("策略注册表 (500 次)", benchmark_strategy_registry),
        ("AI 服务商 (500 次)", benchmark_ai_providers),
        ("技术指标 (50 次)", benchmark_indicators),
    ]
    
    results = []
    
    for name, func in benchmarks:
        print(f"测试: {name}...", end=" ", flush=True)
        try:
            result = func()
            if result is None:
                print("跳过 (模块不可用)")
                continue
            
            print(f"完成")
            results.append((name, result))
        except Exception as e:
            print(f"失败: {e}")
    
    print()
    print("-" * 60)
    print(f"{'测试项':<25} {'平均(ms)':<10} {'中位数':<10} {'标准差':<10}")
    print("-" * 60)
    
    for name, r in results:
        short_name = name.split(" (")[0]
        print(f"{short_name:<25} {r['mean']:<10.3f} {r['median']:<10.3f} {r['stdev']:<10.3f}")
    
    print("-" * 60)
    print()
    
    # 性能阈值检查
    thresholds = {
        "风控模块": 0.5,      # 单次 < 0.5ms
        "策略注册表": 1.0,    # 单次 < 1ms
        "AI 服务商": 0.5,     # 单次 < 0.5ms
        "技术指标": 50.0,     # 单次 < 50ms
    }
    
    all_pass = True
    for name, r in results:
        short_name = name.split(" (")[0]
        threshold = thresholds.get(short_name, 100)
        if r["mean"] > threshold:
            print(f"⚠️  {short_name} 超过阈值: {r['mean']:.3f}ms > {threshold}ms")
            all_pass = False
    
    if all_pass:
        print("✅ 所有测试通过性能阈值")
    
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
