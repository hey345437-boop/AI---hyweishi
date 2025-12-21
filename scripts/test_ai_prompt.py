"""
测试 AI 是否正确应用了提示词
"""
import sys
sys.path.insert(0, '.')

import asyncio
from ai_brain import (
    SparkLiteAgent, HunyuanAgent, DeepSeekAgent,
    MarketContext, BATCH_SYSTEM_PROMPT_TEMPLATE
)

def test_prompt_building():
    """测试提示词构建"""
    print("=" * 60)
    print("测试提示词构建")
    print("=" * 60)
    
    # 创建测试上下文
    test_context = MarketContext(
        symbol="BTC/USDT:USDT",
        timeframe="5m",
        current_price=98000.0,
        ohlcv=[
            [1, 97800, 98100, 97700, 98000, 1000],
            [2, 98000, 98200, 97900, 98100, 1100],
            [3, 98100, 98300, 98000, 98200, 1200],
        ],
        indicators={"RSI": 55, "MACD": "正向"},
        formatted_indicators="RSI: 55, MACD: 正向"
    )
    
    # 测试用户提示词
    user_prompt = "均衡策略，追求稳定收益"
    
    # 测试余额信息
    balance_info = {
        'initial': 10000,
        'realized_pnl': 0,
        'position_used': 0,
        'available': 10000
    }
    
    # 创建各个 Agent 并测试
    agents = [
        ("DeepSeek", DeepSeekAgent(api_key="test")),
        ("SparkLite", SparkLiteAgent(api_key="test")),
        ("Hunyuan", HunyuanAgent(api_key="test")),
    ]
    
    for name, agent in agents:
        print(f"\n--- {name} ---")
        
        # 调用 _build_batch_messages
        messages = agent._build_batch_messages(
            contexts=[test_context],
            user_prompt=user_prompt,
            arena_context=None,
            sentiment=None,
            positions=[],
            balance_info=balance_info
        )
        
        # 检查 system prompt
        system_msg = messages[0]["content"]
        user_msg = messages[1]["content"]
        
        # 检查关键内容
        checks = [
            ("账户信息", "初始资金" in system_msg),
            ("用户风格", user_prompt in system_msg or "均衡策略" in system_msg),
            ("输出格式", "JSON" in system_msg),
            ("action 选项", "open_long" in system_msg and "open_short" in system_msg),
            ("账户状态", "可用余额" in user_msg),
            ("市场数据", "BTC" in user_msg),
        ]
        
        all_pass = True
        for check_name, result in checks:
            status = "✓" if result else "✗"
            print(f"  {status} {check_name}")
            if not result:
                all_pass = False
        
        if all_pass:
            print(f"  ✅ {name} 提示词构建正确")
        else:
            print(f"  ❌ {name} 提示词有问题")
            # 打印部分内容用于调试
            print(f"\n  System prompt 前500字符:")
            print(f"  {system_msg[:500]}...")

if __name__ == "__main__":
    test_prompt_building()
