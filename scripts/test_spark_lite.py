#!/usr/bin/env python3
"""
测试讯飞星火 Spark Lite Agent 接入

使用方法:
1. 在 .env 中配置 SPARK_API_PASSWORD
2. 运行: python scripts/test_spark_lite.py
"""

import asyncio
import os
import sys

# 添加项目根目录到 path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()


async def test_spark_lite():
    """测试 SparkLite Agent"""
    from ai_brain import create_agent, MarketContext, get_available_agents
    
    print("=" * 60)
    print("讯飞星火 Spark Lite Agent 测试")
    print("=" * 60)
    
    # 1. 检查 agent 是否已注册
    agents = get_available_agents()
    print(f"\n✅ 可用 Agents: {agents}")
    
    if "spark_lite" not in agents:
        print("❌ spark_lite 未注册到 AGENT_CLASSES")
        return False
    
    # 2. 检查 API Key
    api_key = os.getenv("SPARK_API_PASSWORD", "")
    if not api_key:
        print("\n⚠️  SPARK_API_PASSWORD 未配置")
        print("请在 .env 文件中添加:")
        print("SPARK_API_PASSWORD=your_api_password_here")
        print("\n跳过 API 调用测试...")
        return True  # 配置检查通过，只是没有 key
    
    print(f"\n✅ SPARK_API_PASSWORD 已配置 (长度: {len(api_key)})")
    
    # 3. 创建 agent 实例
    try:
        agent = create_agent("spark_lite", api_key)
        print(f"✅ Agent 创建成功: {agent.name}")
        print(f"   - API Base: {agent.api_base}")
        print(f"   - Model: {agent.model}")
    except Exception as e:
        print(f"❌ Agent 创建失败: {e}")
        return False
    
    # 4. 构造测试数据
    context = MarketContext(
        symbol="BTC/USDT:USDT",
        timeframe="5m",
        current_price=67500.0,
        ohlcv=[
            [1703001600000, 67400, 67600, 67300, 67500, 1000],
            [1703001900000, 67500, 67700, 67400, 67600, 1200],
            [1703002200000, 67600, 67800, 67500, 67700, 1100],
            [1703002500000, 67700, 67900, 67600, 67800, 1300],
            [1703002800000, 67800, 68000, 67700, 67500, 1400],
        ],
        indicators={
            "rsi": 55.5,
            "macd": {"macd": 50, "signal": 45, "histogram": 5},
            "ma20": 67200,
            "ma50": 66800
        },
        formatted_indicators="""
RSI(14): 55.5 (中性)
MACD: 50 / Signal: 45 / Histogram: 5 (多头)
MA20: 67200 (价格在上方)
MA50: 66800 (价格在上方)
"""
    )
    
    # 5. 调用 API 获取决策
    print("\n📡 调用 SparkLite API...")
    try:
        result = await agent.get_decision(context, user_prompt="均衡策略，追求稳定收益")
        
        print(f"\n✅ API 调用成功!")
        print(f"   - Agent: {result.agent_name}")
        print(f"   - Signal: {result.signal}")
        print(f"   - Confidence: {result.confidence}")
        print(f"   - Reasoning: {result.reasoning[:100]}...")
        print(f"   - Latency: {result.latency_ms:.0f}ms")
        
        if result.error:
            print(f"   - Error: {result.error}")
            return False
        
        # 验证输出格式
        valid_signals = ["open_long", "open_short", "close_long", "close_short", "hold", "wait"]
        if result.signal not in valid_signals:
            print(f"❌ 无效的 signal: {result.signal}")
            return False
        
        if not 0 <= result.confidence <= 100:
            print(f"❌ 无效的 confidence: {result.confidence}")
            return False
        
        print("\n✅ 输出格式验证通过!")
        return True
        
    except Exception as e:
        print(f"\n❌ API 调用失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    success = await test_spark_lite()
    print("\n" + "=" * 60)
    if success:
        print("🎉 SparkLite Agent 测试通过!")
    else:
        print("❌ SparkLite Agent 测试失败")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
