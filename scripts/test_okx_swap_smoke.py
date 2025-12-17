# scripts/test_okx_swap_smoke.py
# OKX Swap 冒烟测试脚本

import argparse
import time
import os
import sys

# 将项目根目录添加到 Python 路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from trade_engine import initialize_exchange, fetch_ohlcv, fetch_balance, fetch_positions, close


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


def test_okx_swap_smoke(env: str):
    """
    测试 OKX Swap 冒烟
    
    参数:
    - env: 环境，'demo' 或 'real'
    """
    print(f"\n{'='*60}")
    print(f"🔥 OKX Swap 冒烟测试 - {env.upper()} 环境")
    print(f"{'='*60}\n")
    
    # 加载配置
    config = load_config(env)
    print(f"配置: {config}\n")
    
    # 初始化交易所
    start_time = time.time()
    adapter = initialize_exchange(config)
    init_time = time.time() - start_time
    print(f"✅ 初始化交易所: {init_time:.2f} 秒\n")
    
    # 测试 load_markets
    start_time = time.time()
    markets = adapter.exchange.load_markets()
    load_markets_time = time.time() - start_time
    print(f"✅ load_markets: {load_markets_time:.2f} 秒\n")
    
    # 测试 fetch_ohlcv
    symbol = 'BTC/USDT:USDT'
    timeframe = '1m'
    limit = 50
    start_time = time.time()
    ohlcv = fetch_ohlcv(adapter, symbol, timeframe, limit)
    fetch_ohlcv_time = time.time() - start_time
    print(f"✅ fetch_ohlcv: {fetch_ohlcv_time:.2f} 秒")
    print(f"   交易对: {symbol}")
    print(f"   时间周期: {timeframe}")
    print(f"   数量: {limit}")
    print(f"   数据点数: {len(ohlcv)}\n")
    
    # 测试 fetch_balance（如果配置了 API Key）
    if config['api_key'] and config['secret']:
        start_time = time.time()
        balance = fetch_balance(adapter)
        fetch_balance_time = time.time() - start_time
        print(f"✅ fetch_balance: {fetch_balance_time:.2f} 秒")
        print(f"   余额: {balance}\n")
        
        # 测试 fetch_positions
        start_time = time.time()
        positions = fetch_positions(adapter)
        fetch_positions_time = time.time() - start_time
        print(f"✅ fetch_positions: {fetch_positions_time:.2f} 秒")
        print(f"   持仓: {positions}\n")
    else:
        print("⚠️ 未配置 API Key，跳过 fetch_balance 和 fetch_positions\n")
    
    # 关闭连接
    close(adapter)
    print(f"✅ 关闭连接\n")
    
    # 打印总耗时
    total_time = time.time() - start_time
    print(f"{'='*60}")
    print(f"🎯 冒烟测试完成 - 总耗时: {total_time:.2f} 秒")
    print(f"{'='*60}\n")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='OKX Swap 冒烟测试脚本')
    parser.add_argument('--env', type=str, default='demo', choices=['demo', 'real'], help='环境，demo 或 real')
    args = parser.parse_args()
    
    test_okx_swap_smoke(args.env)