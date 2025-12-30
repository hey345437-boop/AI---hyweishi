"""
实时信号策略 v3: 布林带 + ADX

特点：
- 专为 WebSocket 实时数据设计
- 不等待K线收盘，实时触发信号
- 布林带突破 + ADX趋势强度过滤
- 适合突破/动量交易

信号逻辑：
- 做多：价格突破布林带上轨 + ADX > 25（趋势确认）
- 做空：价格跌破布林带下轨 + ADX > 25（趋势确认）
- 平仓：价格回归布林带中轨
"""

import pandas as pd
import numpy as np


class RealtimeStrategy:
    """
    实时信号策略：布林带突破 + ADX趋势过滤
    
    🔥 与收盘信号策略的区别：
    - 收盘信号：等待K线收盘后判断（使用 df.iloc[-2]）
    - 实时信号：使用当前未收盘K线实时判断（使用 df.iloc[-1]）
    """
    
    def __init__(self):
        # === 布林带参数 ===
        self.boll_period = 20       # 布林带周期
        self.boll_std = 2.0         # 标准差倍数
        
        # === ADX参数 ===
        self.adx_period = 14        # ADX周期
        self.adx_threshold = 25     # ADX阈值（>25表示趋势明确）
        
        # === 仓位与风控 ===
        self.max_leverage = 50
        self.position_pct = 0.02    # 单次开仓比例
        
        # === 实时信号模式标记 ===
        self.signal_mode = "realtime"  # 标记为实时信号策略
    
    def calculate_ema(self, series, period):
        """EMA计算 - 使用 pandas 内置方法"""
        return series.ewm(span=period, adjust=False).mean()
    
    def calculate_rma(self, series, period):
        """RMA计算 (Wilder's smoothing) - 使用 pandas"""
        # RMA = EMA with alpha = 1/period
        alpha = 1.0 / period
        return series.ewm(alpha=alpha, adjust=False).mean()
    
    def calculate_indicators(self, df):
        """计算布林带和ADX指标"""
        if len(df) < max(self.boll_period, self.adx_period) + 10:
            raise ValueError(f"数据不足，至少需要 {max(self.boll_period, self.adx_period) + 10} 根K线")
        
        # === 1. 布林带 ===
        df['boll_mid'] = df['close'].rolling(window=self.boll_period).mean()
        df['boll_std'] = df['close'].rolling(window=self.boll_period).std()
        df['boll_upper'] = df['boll_mid'] + self.boll_std * df['boll_std']
        df['boll_lower'] = df['boll_mid'] - self.boll_std * df['boll_std']
        
        # === 2. ADX ===
        # True Range
        tr1 = df['high'] - df['low']
        tr2 = abs(df['high'] - df['close'].shift(1))
        tr3 = abs(df['low'] - df['close'].shift(1))
        df['tr'] = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        
        # Directional Movement
        high_diff = df['high'].diff()
        low_diff = -df['low'].diff()
        
        df['dm_plus'] = np.where((high_diff > low_diff) & (high_diff > 0), high_diff, 0)
        df['dm_minus'] = np.where((low_diff > high_diff) & (low_diff > 0), low_diff, 0)
        
        # Smoothed values (RMA)
        df['atr'] = self.calculate_rma(df['tr'].fillna(0), self.adx_period)
        df['smoothed_dm_plus'] = self.calculate_rma(pd.Series(df['dm_plus']).fillna(0), self.adx_period)
        df['smoothed_dm_minus'] = self.calculate_rma(pd.Series(df['dm_minus']).fillna(0), self.adx_period)
        
        # DI+ and DI-
        df['di_plus'] = 100 * df['smoothed_dm_plus'] / df['atr'].replace(0, 1e-10)
        df['di_minus'] = 100 * df['smoothed_dm_minus'] / df['atr'].replace(0, 1e-10)
        
        # DX and ADX
        di_sum = df['di_plus'] + df['di_minus']
        di_sum = di_sum.replace(0, 1)
        df['dx'] = 100 * abs(df['di_plus'] - df['di_minus']) / di_sum
        df['adx'] = self.calculate_rma(df['dx'].fillna(0), self.adx_period)
        
        # === 3. 价格位置 ===
        df['price_vs_upper'] = df['close'] - df['boll_upper']
        df['price_vs_lower'] = df['close'] - df['boll_lower']
        df['price_vs_mid'] = df['close'] - df['boll_mid']
        
        return df
    
    def check_signals(self, df, timeframe='1m'):
        """
        🔥 实时信号检测 - 使用当前未收盘K线
        
        与收盘信号策略的关键区别：
        - 收盘策略：curr = df.iloc[-2]（已收盘K线）
        - 实时策略：curr = df.iloc[-1]（当前K线，未收盘）
        """
        if len(df) < 3:
            return {"action": "HOLD", "reason": "数据不足", "type": "NONE"}
        
        # 🔥 实时模式：使用当前未收盘的K线
        curr = df.iloc[-1]   # 当前K线（实时数据）
        prev = df.iloc[-2]   # 上一根已收盘K线
        
        # 获取指标值
        close = curr['close']
        boll_upper = curr['boll_upper']
        boll_lower = curr['boll_lower']
        boll_mid = curr['boll_mid']
        adx = curr['adx']
        di_plus = curr['di_plus']
        di_minus = curr['di_minus']
        atr = curr['atr']
        
        prev_close = prev['close']
        prev_boll_upper = prev['boll_upper']
        prev_boll_lower = prev['boll_lower']
        
        # === 信号条件 ===
        # ADX趋势过滤
        trend_confirmed = adx > self.adx_threshold
        
        # 布林带突破检测（实时）
        # 做多：价格从下方突破上轨
        breakout_up = (prev_close <= prev_boll_upper) and (close > boll_upper)
        # 做空：价格从上方跌破下轨  
        breakout_down = (prev_close >= prev_boll_lower) and (close < boll_lower)
        
        # DI方向确认
        di_bullish = di_plus > di_minus
        di_bearish = di_minus > di_plus
        
        # === 信号生成 ===
        # 做多信号：突破上轨 + ADX确认趋势 + DI+领先
        if breakout_up and trend_confirmed and di_bullish:
            return {
                "action": "LONG",
                "type": "REALTIME_BREAKOUT",
                "position_pct": self.position_pct,
                "leverage": self.max_leverage,
                "entry_price": close,
                "stop_loss": boll_mid - atr,
                "take_profit": close + atr * 2,
                "reason": f"[{timeframe}]⚡实时突破上轨 | 价格={close:.2f} > 上轨={boll_upper:.2f} | ADX={adx:.1f}"
            }
        
        # 做空信号：跌破下轨 + ADX确认趋势 + DI-领先
        if breakout_down and trend_confirmed and di_bearish:
            return {
                "action": "SHORT",
                "type": "REALTIME_BREAKOUT",
                "position_pct": self.position_pct,
                "leverage": self.max_leverage,
                "entry_price": close,
                "stop_loss": boll_mid + atr,
                "take_profit": close - atr * 2,
                "reason": f"[{timeframe}]⚡实时跌破下轨 | 价格={close:.2f} < 下轨={boll_lower:.2f} | ADX={adx:.1f}"
            }
        
        # 平仓信号：价格回归中轨
        # 多头平仓：价格从上方回落到中轨
        if prev_close > prev['boll_mid'] and close <= boll_mid:
            return {
                "action": "CLOSE_LONG",
                "type": "REALTIME_REVERT",
                "reason": f"[{timeframe}]⚡价格回归中轨（多头平仓）| 价格={close:.2f}"
            }
        
        # 空头平仓：价格从下方反弹到中轨
        if prev_close < prev['boll_mid'] and close >= boll_mid:
            return {
                "action": "CLOSE_SHORT",
                "type": "REALTIME_REVERT",
                "reason": f"[{timeframe}]⚡价格回归中轨（空头平仓）| 价格={close:.2f}"
            }
        
        return {
            "action": "HOLD",
            "type": "NONE",
            "reason": f"无信号 | 价格={close:.2f} | ADX={adx:.1f}"
        }
    
    def run_analysis_with_data(self, symbol, preloaded_data, due_tfs):
        """
        数据解耦版本：使用预加载的K线数据进行分析
        """
        scan_results = []
        
        for tf in due_tfs:
            df = preloaded_data.get(tf)
            
            if df is None or len(df) < 50:
                scan_results.append({
                    "tf": tf,
                    "action": "ERROR",
                    "type": "DATA_ERROR",
                    "signal": None,
                    "reason": "数据不足",
                    "candle_time": None
                })
                continue
            
            try:
                df_with_indicators = self.calculate_indicators(df)
                sig = self.check_signals(df_with_indicators, timeframe=tf)
                
                # 🔥 实时模式：使用当前K线时间戳
                candle_time = None
                if len(df_with_indicators) >= 1:
                    candle_time = df_with_indicators.iloc[-1].get('timestamp')
                
                scan_results.append({
                    "tf": tf,
                    "action": sig['action'],
                    "type": sig.get('type', 'NONE'),
                    "signal": sig,
                    "reason": sig.get('reason', ''),
                    "candle_time": candle_time
                })
                
            except Exception as e:
                scan_results.append({
                    "tf": tf,
                    "action": "ERROR",
                    "type": "CALC_ERROR",
                    "signal": None,
                    "reason": f"计算失败: {str(e)}",
                    "candle_time": None
                })
        
        return scan_results
    
    def risk_check(self, current_equity, current_position_notional, proposed_notional):
        """风控检查"""
        max_allowed = current_equity * 0.10  # 最大10%仓位
        new_total = current_position_notional + proposed_notional
        
        if new_total > max_allowed:
            return False, f"风控拒绝: 总仓位 {new_total:.2f} > 限额 {max_allowed:.2f}"
        return True, "通过"


# 全局实例
strategy_engine = RealtimeStrategy()
