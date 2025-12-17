"""
测试策略信号计算
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import ccxt
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

def test_strategy_signals():
    """测试策略信号"""
    # 初始化交易所
    http_proxy = os.getenv('HTTP_PROXY') or os.getenv('http_proxy')
    https_proxy = os.getenv('HTTPS_PROXY') or os.getenv('https_proxy')
    
    config = {
        'enableRateLimit': True,
        'options': {'defaultType': 'swap'}
    }
    
    if https_proxy:
        config['proxies'] = {'http': http_proxy or https_proxy, 'https': https_proxy}
        print(f"使用代理: {https_proxy}")
    
    exchange = ccxt.okx(config)
    
    # 拉取 K 线数据
    symbol = "XRP/USDT:USDT"
    timeframe = "3m"
    limit = 1000
    
    print(f"\n拉取 {symbol} {timeframe} K线数据 (limit={limit})...")
    ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
    print(f"获取到 {len(ohlcv)} 根 K线")
    
    # 转换为 DataFrame
    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    
    print(f"\n最新5根K线:")
    print(df.tail())
    
    # 加载策略
    from strategy_v2 import TradingStrategy
    strategy = TradingStrategy()
    
    # 计算指标
    print(f"\n计算技术指标...")
    df_with_indicators = strategy.calculate_indicators(df)
    
    # 打印最新K线的关键指标
    curr = df_with_indicators.iloc[-2]  # 00秒模式使用 iloc[-2]
    prev = df_with_indicators.iloc[-3]
    
    print(f"\n=== 当前K线 (iloc[-2]) 关键指标 ===")
    print(f"时间: {curr['timestamp']}")
    print(f"收盘价: {curr['close']:.4f}")
    print(f"EMA12: {curr['ema12']:.4f}")
    print(f"快通道顶部: {curr['fast_top']:.4f}")
    print(f"快通道底部: {curr['fast_bot']:.4f}")
    print(f"慢通道顶部: {curr['slow_top']:.4f}")
    print(f"慢通道底部: {curr['slow_bot']:.4f}")
    print(f"MACD柱: {curr['macd_hist']:.6f}")
    print(f"RSI: {curr['rsi']:.2f}")
    print(f"Stoch K: {curr['stoch_k']:.2f}")
    print(f"KDJ pk: {curr['pk']:.2f}")
    print(f"KDJ pd: {curr['pd']:.2f}")
    print(f"OBV plus: {curr['obv_plus']:.2f}")
    print(f"OBV minus: {curr['obv_minus']:.2f}")
    print(f"OBV ADX: {curr['obv_adx']:.2f}")
    
    # 检查趋势条件
    bullish_trend = (curr['ema12'] > curr['fast_top']) and (curr['ema12'] > curr['slow_top'])
    bearish_trend = (curr['ema12'] < curr['fast_bot']) and (curr['ema12'] < curr['slow_bot'])
    
    print(f"\n=== 趋势判断 ===")
    print(f"看涨趋势 (EMA12 > 快慢通道顶部): {bullish_trend}")
    print(f"  - EMA12 > fast_top: {curr['ema12'] > curr['fast_top']}")
    print(f"  - EMA12 > slow_top: {curr['ema12'] > curr['slow_top']}")
    print(f"看跌趋势 (EMA12 < 快慢通道底部): {bearish_trend}")
    print(f"  - EMA12 < fast_bot: {curr['ema12'] < curr['fast_bot']}")
    print(f"  - EMA12 < slow_bot: {curr['ema12'] < curr['slow_bot']}")
    
    # 检查 MACD 条件
    macd_below_rise = (curr['macd_hist'] < 0) and (curr['macd_hist'] > prev['macd_hist']) and \
                      (prev['macd_hist'] < df_with_indicators.iloc[-4]['macd_hist'])
    macd_above_fall = (curr['macd_hist'] > 0) and (curr['macd_hist'] < prev['macd_hist']) and \
                      (prev['macd_hist'] > df_with_indicators.iloc[-4]['macd_hist'])
    
    print(f"\n=== MACD 条件 ===")
    print(f"MACD柱 < 0 且上升: {macd_below_rise}")
    print(f"  - curr < 0: {curr['macd_hist'] < 0}")
    print(f"  - curr > prev: {curr['macd_hist'] > prev['macd_hist']}")
    print(f"MACD柱 > 0 且下降: {macd_above_fall}")
    
    # 检查 RSI 条件
    curr_rsi = curr['rsi']
    prev_rsi = prev['rsi']
    rsi_cross_up = (prev_rsi <= 30) and (curr_rsi > 30)
    rsi_cross_dn = (prev_rsi >= 70) and (curr_rsi < 70)
    
    print(f"\n=== RSI 条件 ===")
    print(f"RSI > 50: {curr_rsi > 50}")
    print(f"RSI 上穿 30: {rsi_cross_up}")
    print(f"RSI < 50: {curr_rsi < 50}")
    print(f"RSI 下穿 70: {rsi_cross_dn}")
    
    # 检查何以为底条件
    stoch_os = curr['stoch_k'] < 20
    stoch_ob = curr['stoch_k'] > 80
    kdj_gold = (prev['pk'] < prev['pd']) and (curr['pk'] > curr['pd'])
    kdj_dead = (prev['pk'] > prev['pd']) and (curr['pk'] < curr['pd'])
    
    obv_buy = (curr['obv_minus'] >= 22) and (curr['obv_adx'] >= 22) and (curr['obv_plus'] <= 18)
    obv_sell = (curr['obv_plus'] >= 22) and (curr['obv_adx'] >= 22) and (curr['obv_minus'] <= 18)
    
    print(f"\n=== 何以为底条件 ===")
    print(f"Stoch超卖 (<20): {stoch_os} (当前: {curr['stoch_k']:.2f})")
    print(f"Stoch超买 (>80): {stoch_ob}")
    print(f"KDJ金叉: {kdj_gold}")
    print(f"KDJ死叉: {kdj_dead}")
    print(f"OBV买入条件: {obv_buy}")
    print(f"  - minus >= 22: {curr['obv_minus'] >= 22}")
    print(f"  - adx >= 22: {curr['obv_adx'] >= 22}")
    print(f"  - plus <= 18: {curr['obv_plus'] <= 18}")
    print(f"OBV卖出条件: {obv_sell}")
    
    # 调用策略检查信号
    print(f"\n=== 调用策略 check_signals() ===")
    signal = strategy.check_signals(df_with_indicators, timeframe=timeframe)
    print(f"信号结果: {signal}")
    
    # 遍历最近 20 根 K线检查信号
    print(f"\n=== 检查最近 20 根 K线的信号 ===")
    for i in range(len(df) - 22, len(df) - 2):
        sub_df = df_with_indicators.iloc[:i+3].copy()
        if len(sub_df) < 4:
            continue
        sig = strategy.check_signals(sub_df, timeframe=timeframe)
        if sig['action'] != 'HOLD':
            ts = df.iloc[i]['timestamp']
            print(f"  K线 {i} ({ts}): {sig['action']} - {sig['type']} - {sig['reason'][:50]}")

if __name__ == "__main__":
    test_strategy_signals()
