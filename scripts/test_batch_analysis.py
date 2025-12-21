"""
测试批量分析功能
"""
import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()


async def test_batch():
    from ai_brain import create_agent, MarketContext
    from ai_indicators import get_data_source, IndicatorCalculator
    
    print("=" * 60)
    print("批量分析测试")
    print("=" * 60)
    
    # 获取多个币种的数据
    symbols = ["BTC/USDT:USDT", "ETH/USDT:USDT", "SOL/USDT:USDT"]
    data_source = get_data_source()
    calculator = IndicatorCalculator()
    
    contexts = []
    for symbol in symbols:
        print(f"\n获取 {symbol} 数据...")
        ohlcv = data_source.fetch_ohlcv(symbol, "5m", 50)
        if ohlcv:
            indicators = ['RSI', 'MACD']
            latest_values = calculator.get_latest_values(indicators, ohlcv)
            formatted = calculator.format_for_ai(latest_values, symbol, "5m")
            
            ctx = MarketContext(
                symbol=symbol,
                timeframe="5m",
                current_price=ohlcv[-1][4],
                ohlcv=ohlcv,
                indicators=latest_values,
                formatted_indicators=formatted
            )
            contexts.append(ctx)
            print(f"  OK: 价格 ${ctx.current_price:,.2f}")
    
    print(f"\n共获取 {len(contexts)} 个币种数据")
    
    # 测试 DeepSeek 批量分析
    from ai_config_manager import get_ai_config_manager
    config_mgr = get_ai_config_manager()
    configs = config_mgr.get_all_ai_api_configs()
    
    for ai_id in ['deepseek', 'perplexity']:
        if ai_id not in configs or not configs[ai_id].get('api_key'):
            print(f"\n{ai_id}: 未配置，跳过")
            continue
        
        print(f"\n{'=' * 60}")
        print(f"测试 {ai_id} 批量分析")
        print("=" * 60)
        
        agent = create_agent(ai_id, configs[ai_id]['api_key'])
        
        print(f"调用 {ai_id} API（一次请求分析 {len(contexts)} 个币种）...")
        results = await agent.get_batch_decisions(contexts)
        
        print(f"\n结果（{len(results)} 个）:")
        for i, r in enumerate(results):
            symbol = contexts[i].symbol if i < len(contexts) else "?"
            print(f"  {symbol}: {r.signal} ({r.confidence:.0f}%) - {r.reasoning[:60]}...")
        
        print(f"\n总延迟: {sum(r.latency_ms for r in results):.0f}ms")


if __name__ == "__main__":
    asyncio.run(test_batch())
