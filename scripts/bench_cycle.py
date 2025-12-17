# scripts/bench_cycle.py
# 扫描周期性能测试脚本

import argparse
import time
import os
import sys

# 将项目根目录添加到 Python 路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from trade_engine import initialize_exchange, initialize_market_data_provider, close


def load_config(env: str) -> dict:
    """
    加载配置
    
    参数:
    - env: 环境，'demo' 或 'real'
    
    返回:
    - 配置字典
    """
    config = {
        'exchange_type': 'okx',
        'env': env,
        'api_key': os.getenv(f'OKX_{env.upper()}_API_KEY'),
        'secret': os.getenv(f'OKX_{env.upper()}_SECRET'),
        'password': os.getenv(f'OKX_{env.upper()}_PASSWORD')
    }
    return config


def bench_cycle(env: str, symbols: list, timeframe: str, limit: int, iterations: int):
    """
    测试扫描周期性能
    
    参数:
    - env: 环境，'demo' 或 'real'
    - symbols: 交易对列表
    - timeframe: 时间周期
    - limit: K线数量
    - iterations: 迭代次数
    """
    print(f"\n{'='*80}")
    print(f"🔥 扫描周期性能测试")
    print(f"{'='*80}")
    print(f"环境: {env.upper()}")
    print(f"交易对: {symbols}")
    print(f"时间周期: {timeframe}")
    print(f"K线数量: {limit}")
    print(f"迭代次数: {iterations}")
    print(f"{'='*80}\n")
    
    # 加载配置
    config = load_config(env)
    
    # 初始化交易所
    start_time = time.time()
    adapter = initialize_exchange(config)
    init_time = time.time() - start_time
    print(f"✅ 初始化交易所: {init_time:.2f} 秒")
    
    # 初始化MarketDataProvider
    provider = initialize_market_data_provider(adapter, timeframe, limit)
    print(f"✅ 初始化MarketDataProvider: 完成")
    
    # 预热（第一次调用可能较慢）
    print(f"\n🔄 预热中...")
    for symbol in symbols:
        provider.get_ohlcv(symbol, timeframe, limit)
        provider.get_ticker(symbol)
    provider.get_balance()
    provider.get_positions()
    provider.reset_metrics()  # 重置指标，不统计预热数据
    
    # 测试循环
    cycle_times = []
    api_calls_list = []
    cache_hits_list = []
    cache_misses_list = []
    cache_hit_rates = []
    
    print(f"\n{'='*80}")
    print(f"开始性能测试...")
    print(f"{'='*80}")
    
    for i in range(iterations):
        print(f"\n🔄 迭代 {i+1}/{iterations}:")
        
        # 重置指标
        provider.reset_metrics()
        
        # 开始计时
        cycle_start = time.time()
        
        # 1. 获取所有交易对的K线数据
        print(f"   获取 {len(symbols)} 个交易对的K线数据...")
        for symbol in symbols:
            try:
                provider.get_ohlcv(symbol, timeframe, limit)
            except Exception as e:
                print(f"   ⚠️  获取K线失败 ({symbol}): {e}")
        
        # 2. 获取所有交易对的行情数据
        print(f"   获取 {len(symbols)} 个交易对的行情数据...")
        for symbol in symbols:
            try:
                provider.get_ticker(symbol)
            except Exception as e:
                print(f"   ⚠️  获取行情失败 ({symbol}): {e}")
        
        # 3. 获取余额（每个周期只查一次）
        print(f"   获取账户余额...")
        try:
            provider.get_balance()
        except Exception as e:
            print(f"   ⚠️  获取余额失败: {e}")
        
        # 4. 获取持仓（每个周期只查一次）
        print(f"   获取持仓信息...")
        try:
            provider.get_positions()
        except Exception as e:
            print(f"   ⚠️  获取持仓失败: {e}")
        
        # 结束计时
        cycle_end = time.time()
        cycle_time = (cycle_end - cycle_start) * 1000  # 转换为毫秒
        cycle_times.append(cycle_time)
        
        # 获取指标
        metrics = provider.get_metrics()
        api_calls_list.append(metrics["api_calls"])
        cache_hits_list.append(metrics["cache_hits"])
        cache_misses_list.append(metrics["cache_misses"])
        cache_hit_rates.append(metrics["cache_hit_rate"])
        
        # 打印当前迭代结果
        print(f"   {'-'*60}")
        print(f"   周期耗时: {cycle_time:.2f} ms")
        print(f"   API调用次数: {metrics['api_calls']}")
        print(f"   缓存命中: {metrics['cache_hits']}")
        print(f"   缓存未命中: {metrics['cache_misses']}")
        print(f"   缓存命中率: {metrics['cache_hit_rate']:.2%}")
        print(f"   平均API延迟: {metrics['avg_api_latency_ms']:.2f} ms")
        print(f"   错误次数: {metrics['errors']}")
        print(f"   熔断数量: {metrics['circuit_breakers']}")
    
    # 关闭连接
    close(adapter)
    
    # 计算统计结果
    if cycle_times:
        avg_cycle_time = sum(cycle_times) / len(cycle_times)
        min_cycle_time = min(cycle_times)
        max_cycle_time = max(cycle_times)
        
        avg_api_calls = sum(api_calls_list) / len(api_calls_list)
        avg_cache_hits = sum(cache_hits_list) / len(cache_hits_list)
        avg_cache_misses = sum(cache_misses_list) / len(cache_misses_list)
        avg_cache_hit_rate = sum(cache_hit_rates) / len(cache_hit_rates)
        
        print(f"\n{'='*80}")
        print(f"📊 性能测试报告")
        print(f"{'='*80}")
        print(f"周期耗时统计:")
        print(f"  平均: {avg_cycle_time:.2f} ms")
        print(f"  最小: {min_cycle_time:.2f} ms")
        print(f"  最大: {max_cycle_time:.2f} ms")
        print(f"API调用统计:")
        print(f"  平均每周期调用次数: {avg_api_calls:.1f}")
        print(f"  总调用次数: {sum(api_calls_list)}")
        print(f"缓存统计:")
        print(f"  平均每周期缓存命中: {avg_cache_hits:.1f}")
        print(f"  平均每周期缓存未命中: {avg_cache_misses:.1f}")
        print(f"  平均缓存命中率: {avg_cache_hit_rate:.2%}")
        print(f"{'='*80}")
    else:
        print(f"\n⚠️ 没有有效的测试结果")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='扫描周期性能测试脚本')
    parser.add_argument('--env', type=str, default='demo', choices=['demo', 'real'], help='环境，demo 或 real')
    parser.add_argument('--symbols', type=str, default='BTC/USDT:USDT,ETH/USDT:USDT,BNB/USDT:USDT,SOL/USDT:USDT,ADA/USDT:USDT', 
                        help='交易对列表，用逗号分隔')
    parser.add_argument('--timeframe', type=str, default='1m', help='时间周期')
    parser.add_argument('--limit', type=int, default=100, help='K线数量')
    parser.add_argument('--iterations', type=int, default=50, help='迭代次数')
    args = parser.parse_args()
    
    symbols = args.symbols.split(',')
    bench_cycle(args.env, symbols, args.timeframe, args.limit, args.iterations)