#!/usr/bin/env python3
"""
WebSocket 调试脚本 - 测试不同的频道格式
"""

import sys
import time
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()


def test_raw_websocket():
    """直接测试 WebSocket 连接和订阅"""
    import websocket
    
    received_data = []
    
    def on_message(ws, message):
        print(f"收到消息: {message[:200]}")
        try:
            data = json.loads(message)
            received_data.append(data)
        except:
            pass
    
    def on_error(ws, error):
        print(f"错误: {error}")
    
    def on_close(ws, close_status_code, close_msg):
        print(f"连接关闭: {close_status_code} - {close_msg}")
    
    def on_open(ws):
        print("连接已建立")
        
        # 测试不同的订阅格式
        # 格式 1: 标准 K线频道
        subscribe_msg = {
            "op": "subscribe",
            "args": [{
                "channel": "candle1m",
                "instId": "BTC-USDT-SWAP"
            }]
        }
        print(f"发送订阅: {json.dumps(subscribe_msg)}")
        ws.send(json.dumps(subscribe_msg))
    
    # 连接
    ws_url = "wss://ws.okx.com:8443/ws/v5/public"
    print(f"连接到: {ws_url}")
    
    ws = websocket.WebSocketApp(
        ws_url,
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close
    )
    
    # 在后台线程运行
    import threading
    ws_thread = threading.Thread(target=ws.run_forever, daemon=True)
    ws_thread.start()
    
    # 等待数据
    print("\n等待数据（15秒）...")
    for i in range(15):
        time.sleep(1)
        if received_data:
            for data in received_data:
                if "data" in data:
                    print(f"\n✅ 收到 K线数据!")
                    print(f"   数据: {json.dumps(data, indent=2)[:500]}")
                    ws.close()
                    return True
        print(f"   等待中... ({i+1}/15)")
    
    ws.close()
    return False


def test_business_ws():
    """测试 Business WebSocket 端点"""
    import websocket
    
    received_data = []
    
    def on_message(ws, message):
        print(f"收到消息: {message[:200]}")
        try:
            data = json.loads(message)
            received_data.append(data)
        except:
            pass
    
    def on_error(ws, error):
        print(f"错误: {error}")
    
    def on_close(ws, close_status_code, close_msg):
        print(f"连接关闭: {close_status_code} - {close_msg}")
    
    def on_open(ws):
        print("连接已建立")
        
        # 使用 business 频道格式
        subscribe_msg = {
            "op": "subscribe",
            "args": [{
                "channel": "candle1m",
                "instId": "BTC-USDT-SWAP"
            }]
        }
        print(f"发送订阅: {json.dumps(subscribe_msg)}")
        ws.send(json.dumps(subscribe_msg))
    
    # 使用 business WebSocket 端点
    ws_url = "wss://ws.okx.com:8443/ws/v5/business"
    print(f"\n尝试 Business 端点: {ws_url}")
    
    ws = websocket.WebSocketApp(
        ws_url,
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close
    )
    
    import threading
    ws_thread = threading.Thread(target=ws.run_forever, daemon=True)
    ws_thread.start()
    
    print("等待数据（15秒）...")
    for i in range(15):
        time.sleep(1)
        if received_data:
            for data in received_data:
                if "data" in data:
                    print(f"\n✅ 收到 K线数据!")
                    print(f"   数据: {json.dumps(data, indent=2)[:500]}")
                    ws.close()
                    return True
        print(f"   等待中... ({i+1}/15)")
    
    ws.close()
    return False


if __name__ == "__main__":
    print("=" * 60)
    print("🔍 OKX WebSocket 调试")
    print("=" * 60)
    
    print("\n测试 1: Public WebSocket 端点")
    if test_raw_websocket():
        print("\n✅ Public 端点成功!")
    else:
        print("\n❌ Public 端点失败，尝试 Business 端点...")
        if test_business_ws():
            print("\n✅ Business 端点成功!")
        else:
            print("\n❌ 两个端点都失败")
