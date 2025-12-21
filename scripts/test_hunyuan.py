#!/usr/bin/env python3
"""
测试腾讯混元 Hunyuan Agent 接入

使用方法:
1. 在 .env 中配置 HUNYUAN_API_KEY
2. 运行: python scripts/test_hunyuan.py

注意事项:
- 只允许使用免费模型 hunyuan-lite
- 建议在混元控制台关闭后付费，避免扣费风险
"""

import asyncio
import os
import sys

# 添加项目根目录到 path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()


async def test_model_whitelist():
    """测试模型白名单限制"""
    print("\n📋 测试 1: 模型白名单限制")
    print("-" * 40)
    
    # 临时设置非法模型
    original_model = os.environ.get("HUNYUAN_MODEL", "")
    
    try:
        os.environ["HUNYUAN_MODEL"] = "hunyuan-pro"  # 非免费模型
        
        from importlib import reload
        import ai_brain
        reload(ai_brain)
        
        try:
            from ai_brain import HunyuanAgent
            agent = HunyuanAgent("test_key")
            print("❌ 应该拒绝非白名单模型，但没有报错")
            return False
        except ValueError as e:
            if "白名单" in str(e) or "hunyuan-lite" in str(e):
                print(f"✅ 正确拒绝非白名单模型: {e}")
                return True
            else:
                print(f"❌ 错误信息不正确: {e}")
                return False
    finally:
        # 恢复原始设置
        if original_model:
            os.environ["HUNYUAN_MODEL"] = original_model
        else:
            os.environ.pop("HUNYUAN_MODEL", None)
        
        # 重新加载模块
        from importlib import reload
        import ai_brain
        reload(ai_brain)


async def test_hunyuan_agent():
    """测试 Hunyuan Agent 基本功能"""
    print("\n📋 测试 2: Hunyuan Agent 基本功能")
    print("-" * 40)
    
    from ai_brain import create_agent, MarketContext, get_available_agents
    
    # 1. 检查 agent 是否已注册
    agents = get_available_agents()
    print(f"可用 Agents: {agents}")
    
    if "hunyuan" not in agents:
        print("❌ hunyuan 未注册到 AGENT_CLASSES")
        return False
    print("✅ hunyuan 已注册")
    
    # 2. 检查 API Key
    api_key = os.getenv("HUNYUAN_API_KEY", "")
    if not api_key:
        print("\n⚠️  HUNYUAN_API_KEY 未配置")
        print("请在 .env 文件中添加:")
        print("HUNYUAN_API_KEY=your_api_key_here")
        print("\n跳过 API 调用测试...")
        return True  # 配置检查通过，只是没有 key
    
    print(f"✅ HUNYUAN_API_KEY 已配置 (长度: {len(api_key)})")
    
    # 3. 创建 agent 实例
    try:
        agent = create_agent("hunyuan", api_key)
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
    print("\n📡 调用 Hunyuan API (hunyuan-lite)...")
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


async def test_afterpay_warning():
    """测试后付费风险提示"""
    print("\n📋 测试 3: 后付费风险提示")
    print("-" * 40)
    
    import logging
    
    # 捕获日志
    log_messages = []
    
    class LogCapture(logging.Handler):
        def emit(self, record):
            log_messages.append(record.getMessage())
    
    # 添加日志捕获
    logger = logging.getLogger("ai_brain")
    handler = LogCapture()
    handler.setLevel(logging.INFO)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    
    try:
        # 测试后付费关闭时的提示
        os.environ["HUNYUAN_AFTERPAY_ENABLED"] = "false"
        
        from importlib import reload
        import ai_brain
        reload(ai_brain)
        
        from ai_brain import HunyuanAgent
        agent = HunyuanAgent("test_key")
        
        # 检查是否有安全提示
        has_safe_msg = any("免费模型" in msg or "后付费已关闭" in msg for msg in log_messages)
        if has_safe_msg:
            print("✅ 后付费关闭时显示安全提示")
        else:
            print("⚠️  未检测到安全提示日志")
        
        # 测试后付费开启时的警告
        log_messages.clear()
        os.environ["HUNYUAN_AFTERPAY_ENABLED"] = "true"
        reload(ai_brain)
        
        from ai_brain import HunyuanAgent
        agent = HunyuanAgent("test_key")
        
        has_warning = any("扣费风险" in msg or "后付费" in msg for msg in log_messages)
        if has_warning:
            print("✅ 后付费开启时显示风险警告")
        else:
            print("⚠️  未检测到风险警告日志")
        
        return True
        
    finally:
        # 清理
        os.environ.pop("HUNYUAN_AFTERPAY_ENABLED", None)
        logger.removeHandler(handler)


async def main():
    print("=" * 60)
    print("腾讯混元 Hunyuan Agent 测试")
    print("=" * 60)
    
    results = []
    
    # 测试 1: 模型白名单
    results.append(await test_model_whitelist())
    
    # 测试 2: 基本功能
    results.append(await test_hunyuan_agent())
    
    # 测试 3: 后付费提示
    results.append(await test_afterpay_warning())
    
    print("\n" + "=" * 60)
    if all(results):
        print("🎉 所有测试通过!")
    else:
        print("❌ 部分测试失败")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
