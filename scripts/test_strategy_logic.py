"""
测试策略逻辑（不需要网络）
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import numpy as np

def test_strategy_logic():
    """测试策略逻辑"""
    from strategy_v2 import TradingStrategy
    strategy = TradingStrategy()
    
    # 创建模拟数据（1000根K线）
    np.random.seed(42)
    n = 1000
    
    # 生成价格数据（模拟上涨趋势）
    base_price = 2.0
    returns = np.random.randn(n) * 0.01 + 0.0001  # 微小上涨趋势
    prices = base_price * np.cumprod(1 + returns)
    
    # 生成 OHLCV 数据
    df = pd.DataFrame({
        'timestamp': pd.date_range('2024-01-01', periods=n, freq='3min'),
        'open': prices * (1 + np.random.randn(n) * 0.001),
        'high': prices * (1 + np.abs(np.random.randn(n) * 0.005)),
        'low': prices * (1 - np.abs(np.random.randn(n) * 0.005)),
        'close': prices,
        'volume': np.random.randint(1000000, 10000000, n).astype(float)
    })
    
    print(f"生成 {len(df)} 根模拟K线数据")
    print(f"价格范围: {df['close'].min():.4f} - {df['close'].max():.4f}")
    
    # 计算指标
    print("\n计算技术指标...")
    try:
        df_with_indicators = strategy.calculate_indicators(df)
        print(f"指标计算成功，列数: {len(df_with_indicators.columns)}")
    except Exception as e:
        print(f"指标计算失败: {e}")
        return
    
    # 打印最新K线的关键指标
    curr = df_with_indicators.iloc[-2]
    prev = df_with_indicators.iloc[-3]
    
    print(f"\n=== 当前K线 (iloc[-2]) 关键指标 ===")
    print(f"收盘价: {curr['close']:.4f}")
    print(f"EMA12: {curr['ema12']:.4f}")
    print(f"快通道顶部: {curr['fast_top']:.4f}")
    print(f"快通道底部: {curr['fast_bot']:.4f}")
    print(f"慢通道顶部: {curr['slow_top']:.4f}")
    print(f"慢通道底部: {curr['slow_bot']:.4f}")
    print(f"MACD柱: {curr['macd_hist']:.6f}")
    print(f"RSI: {curr['rsi']:.2f}")
    print(f"Stoch K: {curr['stoch_k']:.2f}")
    
    # 检查趋势条件
    bullish_trend = (curr['ema12'] > curr['fast_top']) and (curr['ema12'] > curr['slow_top'])
    bearish_trend = (curr['ema12'] < curr['fast_bot']) and (curr['ema12'] < curr['slow_bot'])
    
    print(f"\n=== 趋势判断 ===")
    print(f"看涨趋势: {bullish_trend}")
    print(f"看跌趋势: {bearish_trend}")
    
    # 调用策略检查信号
    print(f"\n=== 调用策略 check_signals() ===")
    signal = strategy.check_signals(df_with_indicators, timeframe='3m')
    print(f"信号结果: {signal}")
    
    # 遍历所有K线检查信号
    print(f"\n=== 检查所有K线的信号 ===")
    signal_count = 0
    for i in range(800, len(df) - 2):
        sub_df = df_with_indicators.iloc[:i+3].copy()
        if len(sub_df) < 4:
            continue
        sig = strategy.check_signals(sub_df, timeframe='3m')
        if sig['action'] != 'HOLD':
            signal_count += 1
            if signal_count <= 10:  # 只打印前10个
                ts = df.iloc[i]['timestamp']
                print(f"  K线 {i} ({ts}): {sig['action']} - {sig['type']}")
    
    print(f"\n总共发现 {signal_count} 个信号")

if __name__ == "__main__":
    test_strategy_logic()
