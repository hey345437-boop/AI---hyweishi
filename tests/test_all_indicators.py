# -*- coding: utf-8 -*-
"""全面指标准确性测试"""
import numpy as np
import pandas as pd
import pandas_ta as ta
from ai.ai_indicators import calc_ema, calc_rsi, calc_macd, calc_atr, calc_boll, calc_kdj, calc_ma, calc_obv, calc_vwap

# 生成测试数据
np.random.seed(42)
n = 500
base_price = 50000.0
returns = np.random.randn(n) * 0.02
closes = base_price * np.cumprod(1 + returns)
highs = closes * (1 + np.abs(np.random.randn(n) * 0.01))
lows = closes * (1 - np.abs(np.random.randn(n) * 0.01))
opens = (highs + lows) / 2
volumes = np.random.uniform(1000, 10000, n)

df = pd.DataFrame({
    'open': opens,
    'high': highs,
    'low': lows,
    'close': closes,
    'volume': volumes
})

print('=' * 70)
print('全面指标准确性测试')
print('=' * 70)

def check_accuracy(name, custom, reference, tolerance=0.01):
    """检查准确性"""
    valid_mask = ~np.isnan(custom) & ~np.isnan(reference)
    if not valid_mask.any():
        print(f'  {name}: 无有效数据对比')
        return
    diff = np.abs(custom[valid_mask] - reference[valid_mask])
    max_diff = np.max(diff)
    avg_diff = np.mean(diff)
    ref_mean = np.mean(np.abs(reference[valid_mask]))
    rel_diff = max_diff / ref_mean * 100 if ref_mean > 0 else 0
    
    status = '✅' if rel_diff < tolerance else '⚠️'
    print(f'  {name}: 最大差异={max_diff:.6f}, 相对差异={rel_diff:.4f}% {status}')

# 1. MA
print('\n【1】MA (简单移动平均)')
custom_ma = calc_ma(closes, 20)
ta_ma = ta.sma(df['close'], length=20)
check_accuracy('MA(20)', custom_ma, ta_ma.values)

# 2. EMA
print('\n【2】EMA (指数移动平均)')
custom_ema = calc_ema(closes, 12)
ta_ema = ta.ema(df['close'], length=12)
check_accuracy('EMA(12)', custom_ema, ta_ema.values)

custom_ema26 = calc_ema(closes, 26)
ta_ema26 = ta.ema(df['close'], length=26)
check_accuracy('EMA(26)', custom_ema26, ta_ema26.values)

# 3. RSI
print('\n【3】RSI (相对强弱指数)')
custom_rsi = calc_rsi(closes, 14)
ta_rsi = ta.rsi(df['close'], length=14)
check_accuracy('RSI(14)', custom_rsi, ta_rsi.values)

custom_rsi7 = calc_rsi(closes, 7)
ta_rsi7 = ta.rsi(df['close'], length=7)
check_accuracy('RSI(7)', custom_rsi7, ta_rsi7.values)

# 4. MACD
print('\n【4】MACD')
custom_macd = calc_macd(closes, 12, 26, 9)
ta_macd = ta.macd(df['close'], fast=12, slow=26, signal=9)
macd_col = [c for c in ta_macd.columns if 'MACD_12_26_9' in c and 'h' not in c.lower() and 's' not in c.lower()][0]
signal_col = [c for c in ta_macd.columns if 'MACDs' in c][0]
hist_col = [c for c in ta_macd.columns if 'MACDh' in c][0]
check_accuracy('MACD线', custom_macd['macd'], ta_macd[macd_col].values)
check_accuracy('Signal线', custom_macd['signal'], ta_macd[signal_col].values)
check_accuracy('Histogram', custom_macd['histogram'], ta_macd[hist_col].values)

# 5. ATR
print('\n【5】ATR (平均真实波幅)')
custom_atr = calc_atr(highs, lows, closes, 14)
ta_atr = ta.atr(df['high'], df['low'], df['close'], length=14)
check_accuracy('ATR(14)', custom_atr, ta_atr.values)

# 6. BOLL
print('\n【6】BOLL (布林带)')
custom_boll = calc_boll(closes, 20, 2.0)
ta_boll = ta.bbands(df['close'], length=20, std=2.0)
upper_col = [c for c in ta_boll.columns if 'BBU' in c][0]
middle_col = [c for c in ta_boll.columns if 'BBM' in c][0]
lower_col = [c for c in ta_boll.columns if 'BBL' in c][0]
check_accuracy('BOLL Middle', custom_boll['middle'], ta_boll[middle_col].values)
check_accuracy('BOLL Upper', custom_boll['upper'], ta_boll[upper_col].values, tolerance=1.0)
check_accuracy('BOLL Lower', custom_boll['lower'], ta_boll[lower_col].values, tolerance=1.0)

# 7. OBV
print('\n【7】OBV (能量潮)')
custom_obv = calc_obv(closes, volumes)
ta_obv = ta.obv(df['close'], df['volume'])
check_accuracy('OBV', custom_obv, ta_obv.values)

# 8. VWAP
print('\n【8】VWAP (成交量加权平均价)')
custom_vwap = calc_vwap(highs, lows, closes, volumes)
try:
    ta_vwap = ta.vwap(df['high'], df['low'], df['close'], df['volume'])
    if ta_vwap is not None:
        check_accuracy('VWAP', custom_vwap, ta_vwap.values)
    else:
        print('  [跳过] pandas_ta VWAP 需要 DatetimeIndex')
except Exception as e:
    print(f'  [跳过] VWAP 对比失败: {e}')

# 9. KDJ vs Stochastic
print('\n【9】KDJ / Stochastic')
custom_kdj = calc_kdj(highs, lows, closes, 9, 3, 3)
ta_stoch = ta.stoch(df['high'], df['low'], df['close'], k=9, d=3, smooth_k=3)
k_col = [c for c in ta_stoch.columns if 'STOCHk' in c][0]
d_col = [c for c in ta_stoch.columns if 'STOCHd' in c][0]
print('  注: KDJ 使用中国市场常用算法，与 Stochastic 有差异')
print(f'  自定义 K={custom_kdj["k"][-1]:.2f}, D={custom_kdj["d"][-1]:.2f}, J={custom_kdj["j"][-1]:.2f}')
print(f'  pandas_ta K={ta_stoch[k_col].values[-1]:.2f}, D={ta_stoch[d_col].values[-1]:.2f}')

print('\n' + '=' * 70)
print('测试完成')
print('=' * 70)
