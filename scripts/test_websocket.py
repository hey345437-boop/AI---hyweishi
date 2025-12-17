#!/usr/bin/env python3
"""
WebSocket 功能测试脚本

测试 OKX WebSocket 客户端的基本功能：
1. 连接建立
2. K线订阅
3. 数据接收
4. 缓存读取
"""

import sys
import time
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()


def test_websocket_availability():
    """测试 WebSocket 是否可用"""
    print("\n" + "=" * 60)
    print("🔍 测试 1: WebSocket 可用性检查")
    print("=" * 60)
    
    try:
        from okx_websocket import is_ws_available, WEBSOCKET_AVAILABLE
        
        if is_ws_available():
            print("✅ WebSocket 功能可用")
            print(f"   WEBSOCKET_AVAILABLE = {WEBSOCKET_AVAILABLE}")
            return True
        else:
            print("❌ WebSocket 功能不可用")
            print("   请安装: pip install websocket-client")
            return False
    except ImportError as e:
        print(f"❌ 导入失败: {e}")
        return False


def test_websocket_connection():
    """测试 WebSocket 连接"""
    print("\n" + "=" * 60)
    print("🔍 测试 2: WebSocket 连接测试")
    print("=" * 60)
    
    try:
        from okx_websocket import OKXWebSocketClient
        
        client = OKXWebSocketClient(use_aws=False)
        print(f"   WebSocket URL: {client.ws_url}")
        
        print("   正在连接...")
        success = client.start()
        
        if success:
            print("✅ 连接成功")
            print(f"   connected = {client.connected}")
            return client
        else:
            print("❌ 连接失败")
            return None
    except Exception as e:
        print(f"❌ 连接异常: {e}")
        return None


def test_candle_subscription(client):
    """测试 K线订阅"""
    print("\n" + "=" * 60)
    print("🔍 测试 3: K线订阅测试")
    print("=" * 60)
    
    if client is None:
        print("⚠️ 跳过（无连接）")
        return False
    
    try:
        symbol = "BTC/USDT:USDT"
        timeframe = "1m"
        
        print(f"   订阅: {symbol} {timeframe}")
        success = client.subscribe_candles(symbol, timeframe)
        
        if success:
            print("✅ 订阅成功")
            print(f"   订阅数: {client.get_subscription_count()}")
            return True
        else:
            print("❌ 订阅失败")
            return False
    except Exception as e:
        print(f"❌ 订阅异常: {e}")
        return False


def test_data_reception(client):
    """测试数据接收"""
    print("\n" + "=" * 60)
    print("🔍 测试 4: 数据接收测试")
    print("=" * 60)
    
    if client is None:
        print("⚠️ 跳过（无连接）")
        return False
    
    try:
        symbol = "BTC/USDT:USDT"
        timeframe = "1m"
        
        print(f"   等待数据推送（最多 10 秒）...")
        
        for i in range(10):
            time.sleep(1)
            data = client.get_candles(symbol, timeframe, limit=10)
            
            if data and len(data) > 0:
                print(f"✅ 收到数据: {len(data)} 根 K线")
                
                # 显示最新一根
                latest = data[-1]
                print(f"   最新 K线:")
                print(f"     时间戳: {latest[0]}")
                print(f"     开盘: {latest[1]}")
                print(f"     最高: {latest[2]}")
                print(f"     最低: {latest[3]}")
                print(f"     收盘: {latest[4]}")
                print(f"     成交量: {latest[5]}")
                return True
            
            print(f"   等待中... ({i+1}/10)")
        
        print("❌ 超时未收到数据")
        return False
    except Exception as e:
        print(f"❌ 数据接收异常: {e}")
        return False


def test_cache_stats(client):
    """测试缓存统计"""
    print("\n" + "=" * 60)
    print("🔍 测试 5: 缓存统计")
    print("=" * 60)
    
    if client is None:
        print("⚠️ 跳过（无连接）")
        return
    
    try:
        stats = client.get_cache_stats()
        print("✅ 缓存统计:")
        print(f"   connected: {stats.get('connected')}")
        print(f"   subscriptions: {stats.get('subscriptions')}")
        print(f"   candle_cache: {stats.get('candle_cache')}")
        print(f"   ticker_cache: {stats.get('ticker_cache')}")
        print(f"   reconnect_attempts: {stats.get('reconnect_attempts')}")
    except Exception as e:
        print(f"❌ 统计异常: {e}")


def test_cleanup(client):
    """测试清理"""
    print("\n" + "=" * 60)
    print("🔍 测试 6: 清理测试")
    print("=" * 60)
    
    if client is None:
        print("⚠️ 跳过（无连接）")
        return
    
    try:
        client.stop()
        print("✅ WebSocket 已停止")
        print(f"   connected = {client.connected}")
    except Exception as e:
        print(f"❌ 清理异常: {e}")


def main():
    """主测试函数"""
    print("\n" + "=" * 60)
    print("🚀 OKX WebSocket 功能测试")
    print("=" * 60)
    
    # 测试 1: 可用性
    if not test_websocket_availability():
        print("\n❌ WebSocket 不可用，测试终止")
        return
    
    # 测试 2: 连接
    client = test_websocket_connection()
    
    # 测试 3: 订阅
    test_candle_subscription(client)
    
    # 测试 4: 数据接收
    test_data_reception(client)
    
    # 测试 5: 缓存统计
    test_cache_stats(client)
    
    # 测试 6: 清理
    test_cleanup(client)
    
    print("\n" + "=" * 60)
    print("✅ 测试完成")
    print("=" * 60)


if __name__ == "__main__":
    main()
