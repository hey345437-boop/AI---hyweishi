#!/usr/bin/env python
"""
WebSocket 订阅测试脚本

测试 OKX WebSocket K线订阅是否正常工作
"""
import sys
import os
import time

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 🔥 加载 .env 文件（必须在导入 okx_websocket 之前）
from dotenv import load_dotenv
load_dotenv()

from okx_websocket import OKXWebSocketClient, WEBSOCKET_AVAILABLE

def test_websocket():
    if not WEBSOCKET_AVAILABLE:
        print("❌ websocket-client 未安装")
        return
    
    print("=" * 60)
    print("OKX WebSocket 订阅测试")
    print("=" * 60)
    
    # 创建客户端
    client = OKXWebSocketClient(use_aws=False)
    print(f"[1] WebSocket URL: {client.ws_url}")
    print(f"    代理配置: {client.https_proxy or client.http_proxy or '无'}")
    
    # 启动连接
    print("\n[2] 正在连接...")
    if not client.start():
        print("❌ 连接失败")
        return
    
    print("✅ 连接成功")
    print(f"   connected = {client.connected}")
    
    # 测试订阅
    test_symbols = ["BTC/USDT:USDT", "ETH/USDT:USDT"]
    test_timeframes = ["1m", "5m"]
    
    print("\n[3] 测试订阅...")
    for symbol in test_symbols:
        for tf in test_timeframes:
            # 转换格式
            inst_id = client._convert_symbol(symbol)
            tf_normalized = client._normalize_timeframe(tf)
            channel = f"candle{tf_normalized}"
            
            print(f"\n   订阅: {symbol} {tf}")
            print(f"   -> instId: {inst_id}")
            print(f"   -> channel: {channel}")
            
            result = client.subscribe_candles(symbol, tf)
            print(f"   -> 结果: {'✅ 成功' if result else '❌ 失败'}")
    
    # 等待数据
    print("\n[4] 等待数据推送 (30秒)...")
    print("   如果 30 秒内没有数据，OKX 会断开连接")
    
    for i in range(30):
        time.sleep(1)
        
        # 检查连接状态
        if not client.connected:
            print(f"\n❌ 连接已断开 (第 {i+1} 秒)")
            break
        
        # 检查缓存数据
        stats = client.get_cache_stats()
        candle_cache = stats.get('candle_cache', {})
        # candle_cache 可能是 {key: count} 或 {key: [data]}
        if candle_cache:
            first_val = next(iter(candle_cache.values()), 0)
            if isinstance(first_val, int):
                candle_count = sum(candle_cache.values())
            else:
                candle_count = sum(len(v) for v in candle_cache.values())
        else:
            candle_count = 0
        
        if i % 5 == 0:
            print(f"   [{i+1}s] 订阅数: {stats.get('subscriptions', 0)}, K线缓存: {candle_count}")
        
        if candle_count > 0:
            print(f"\n✅ 收到数据！(第 {i+1} 秒)")
            print(f"   缓存统计: {stats}")
            break
    
    # 最终状态
    print("\n[5] 最终状态:")
    print(f"   connected: {client.connected}")
    print(f"   subscriptions: {client.subscriptions}")
    
    stats = client.get_cache_stats()
    print(f"   candle_cache: {stats.get('candle_cache', {})}")
    
    # 停止
    print("\n[6] 停止客户端...")
    client.stop()
    print("✅ 测试完成")

if __name__ == "__main__":
    test_websocket()
