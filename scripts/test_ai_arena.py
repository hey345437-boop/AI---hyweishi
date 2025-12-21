"""
AI 竞技场测试脚本

直接测试 DeepSeek 和 Perplexity 是否能正常工作
"""

import asyncio
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()


def test_api_keys():
    """测试 API Key 是否配置"""
    print("\n" + "="*60)
    print("1. 检查 API Key 配置")
    print("="*60)
    
    try:
        from ai_config_manager import get_ai_config_manager
        config_mgr = get_ai_config_manager()
        configs = config_mgr.get_all_ai_api_configs()
        
        print(f"\n已配置的 AI:")
        for ai_id, config in configs.items():
            enabled = config.get('enabled', False)
            verified = config.get('verified', False)
            has_key = bool(config.get('api_key'))
            key_tail = config.get('api_key', '')[-4:] if config.get('api_key') else 'N/A'
            
            status = "OK" if enabled and verified else ("未验证" if has_key else "未配置")
            print(f"  - {ai_id}: {status} (key: ****{key_tail})")
        
        return configs
    except Exception as e:
        print(f"  错误: {e}")
        return {}


def test_market_data():
    """测试市场数据获取"""
    print("\n" + "="*60)
    print("2. 测试市场数据获取")
    print("="*60)
    
    try:
        from ai_indicators import get_data_source, IndicatorCalculator
        
        data_source = get_data_source()
        calculator = IndicatorCalculator()
        
        symbol = "BTC/USDT:USDT"
        timeframe = "5m"
        
        print(f"\n获取 {symbol} {timeframe} K线数据...")
        ohlcv = data_source.fetch_ohlcv(symbol, timeframe, 100)
        
        if ohlcv and len(ohlcv) > 0:
            print(f"  OK: 获取到 {len(ohlcv)} 根 K 线")
            current_price = ohlcv[-1][4]
            print(f"  当前价格: ${current_price:,.2f}")
            
            # 计算指标
            print(f"\n计算技术指标...")
            indicators = ['RSI', 'MACD', 'ATR']
            latest_values = calculator.get_latest_values(indicators, ohlcv)
            formatted = calculator.format_for_ai(latest_values, symbol, timeframe)
            
            print(f"  指标数据:\n{formatted[:500]}...")
            
            return {
                'symbol': symbol,
                'timeframe': timeframe,
                'current_price': current_price,
                'ohlcv': ohlcv,
                'indicators': latest_values,
                'formatted_indicators': formatted
            }
        else:
            print(f"  错误: 未获取到 K 线数据")
            return None
    except Exception as e:
        print(f"  错误: {e}")
        import traceback
        traceback.print_exc()
        return None


async def test_single_ai(ai_id: str, api_key: str, market_data: dict):
    """测试单个 AI"""
    print(f"\n--- 测试 {ai_id} ---")
    
    try:
        from ai_brain import create_agent, MarketContext
        
        agent = create_agent(ai_id, api_key)
        
        context = MarketContext(
            symbol=market_data['symbol'],
            timeframe=market_data['timeframe'],
            current_price=market_data['current_price'],
            ohlcv=market_data['ohlcv'],
            indicators=market_data['indicators'],
            formatted_indicators=market_data['formatted_indicators']
        )
        
        print(f"  调用 {ai_id} API...")
        result = await agent.get_decision(context, "")
        
        print(f"  信号: {result.signal}")
        print(f"  置信度: {result.confidence}%")
        print(f"  推理: {result.reasoning[:100]}..." if result.reasoning else "  推理: (无)")
        print(f"  延迟: {result.latency_ms:.0f}ms")
        
        if result.error:
            print(f"  错误: {result.error}")
        
        return result
    except Exception as e:
        print(f"  错误: {e}")
        import traceback
        traceback.print_exc()
        return None


async def test_all_ais(configs: dict, market_data: dict):
    """测试所有已配置的 AI"""
    print("\n" + "="*60)
    print("3. 测试 AI 决策")
    print("="*60)
    
    results = {}
    
    for ai_id, config in configs.items():
        if config.get('enabled') and config.get('api_key'):
            result = await test_single_ai(ai_id, config['api_key'], market_data)
            results[ai_id] = result
    
    return results


def test_scheduler_status():
    """测试调度器状态"""
    print("\n" + "="*60)
    print("4. 检查调度器状态")
    print("="*60)
    
    try:
        from arena_scheduler import is_scheduler_running, get_latest_battle_result
        
        running = is_scheduler_running()
        print(f"\n调度器运行中: {running}")
        
        if running:
            result = get_latest_battle_result()
            if result:
                print(f"  最新对战时间: {result.timestamp}")
                print(f"  币种: {result.symbol}")
                print(f"  共识: {result.consensus}")
                print(f"  决策数: {len(result.decisions)}")
                for d in result.decisions:
                    print(f"    - {d.get('agent_name')}: {d.get('signal')} ({d.get('confidence')}%)")
            else:
                print("  暂无对战结果")
        
        return running
    except Exception as e:
        print(f"  错误: {e}")
        return False


def test_database():
    """测试数据库中的决策记录"""
    print("\n" + "="*60)
    print("5. 检查数据库决策记录")
    print("="*60)
    
    try:
        from ai_db_manager import get_ai_db_manager
        
        db = get_ai_db_manager()
        
        # 获取最新决策
        decisions = db.get_latest_decisions(limit=5)
        
        print(f"\n最近 5 条决策记录:")
        if decisions:
            for d in decisions:
                # confidence 已经是 0-100，不需要再乘 100
                print(f"  [{d.created_at}] {d.agent_name}: {d.signal} ({d.confidence:.0f}%) - {d.symbol}")
        else:
            print("  (无记录)")
        
        # 获取统计
        stats = db.get_all_stats()
        print(f"\nAI 统计:")
        if stats:
            for s in stats:
                print(f"  {s.agent_name}: 胜率 {s.win_rate*100:.0f}%, 总盈亏 ${s.total_pnl:.2f}")
        else:
            print("  (无统计)")
        
        return True
    except Exception as e:
        print(f"  错误: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    print("\n" + "="*60)
    print("AI 竞技场诊断测试")
    print("="*60)
    
    # 1. 检查 API Key
    configs = test_api_keys()
    
    if not configs:
        print("\n错误: 未找到任何 AI 配置")
        return
    
    enabled_ais = [k for k, v in configs.items() if v.get('enabled') and v.get('api_key')]
    if not enabled_ais:
        print("\n错误: 没有已启用的 AI")
        return
    
    print(f"\n已启用的 AI: {enabled_ais}")
    
    # 2. 测试市场数据
    market_data = test_market_data()
    
    if not market_data:
        print("\n错误: 无法获取市场数据")
        return
    
    # 3. 测试 AI 决策
    results = await test_all_ais(configs, market_data)
    
    # 4. 检查调度器
    test_scheduler_status()
    
    # 5. 检查数据库
    test_database()
    
    # 总结
    print("\n" + "="*60)
    print("测试总结")
    print("="*60)
    
    success_count = sum(1 for r in results.values() if r and not r.error)
    total_count = len(results)
    
    print(f"\nAI 测试: {success_count}/{total_count} 成功")
    
    if success_count == 0:
        print("\n可能的问题:")
        print("  1. API Key 无效或过期")
        print("  2. 网络连接问题（需要代理？）")
        print("  3. API 服务不可用")
    elif success_count < total_count:
        print("\n部分 AI 失败，请检查对应的 API Key")


if __name__ == "__main__":
    asyncio.run(main())
