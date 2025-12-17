# strategy_v1.py - 趋势1.3策略引擎（完整实现）

import pandas as pd
import numpy as np

class TradingStrategyV1:
    """
    趋势1.3策略引擎：包含双MACD策略 + 顶底系统 + SMC摆动订单块
    """
    def __init__(self):
        # === 顶底系统参数 ===
        self.bottom_mode = "平衡模式"
        self.k_period = 14
        self.k_smooth = 5
        self.kdj_ilong = 9
        self.kdj_isig = 3
        self.obv_len = 22
        self.obv_sig = 22
        
        # === 趋势1策略参数 ===
        self.osc_filter = True  # 启用震荡过滤器
        self.osc_len = 20
        self.rsi_len = 14
        self.swing_len = 50
        
        # 仓位与风控
        self.max_leverage = 50
        self.max_total_position_pct = 0.10
        self.main_signal_pct = 0.05
        self.sub_signal_pct = 0.025
        
        # 顶底模式参数
        self.more_bottom = True
        self.choose_bottom = 1
    
    def set_bottom_mode(self, mode):
        """设置顶底模式"""
        mode_config = {
            "保守模式": {"more_bottom": False, "choose_bottom": 0},
            "平衡模式": {"more_bottom": True, "choose_bottom": 1},
            "激进模式": {"more_bottom": True, "choose_bottom": 2},
            "恶魔模式": {"more_bottom": True, "choose_bottom": 3}
        }
        
        if mode in mode_config:
            self.bottom_mode = mode
            self.more_bottom = mode_config[mode]["more_bottom"]
            self.choose_bottom = mode_config[mode]["choose_bottom"]
            print(f"✅ 顶底模式已设置为: {mode}")
    
    def calculate_ema(self, series, period):
        """TradingView精确EMA计算 - 使用前N个点的SMA作为初始值"""
        alpha = 2.0 / (period + 1.0)
        result = np.zeros(len(series))
        
        # 使用前N个点的简单移动平均作为初始值
        result[period-1] = series.iloc[:period].mean()
    
        for i in range(period, len(series)):
            result[i] = alpha * series.iloc[i] + (1 - alpha) * result[i-1]
    
        return pd.Series(result, index=series.index)
    
    def calculate_rma(self, series, period):
        """RMA 计算（Wilder's smoothing）- 与 TradingView ta.rma 完全一致"""
        # 使用 Wilder's Smoothing 方法实现 RMA
        alpha = 1.0 / period
        result = np.zeros(len(series))
        
        # 处理 NaN 值，使用 nz 逻辑（将 NaN 替换为 0）
        clean_series = series.fillna(0)
        
        # 初始化：第一个有效值为前 N 个值的简单平均
        result[period-1] = clean_series.iloc[:period].mean()
        
        # 递归计算
        for i in range(period, len(series)):
            result[i] = alpha * clean_series.iloc[i] + (1 - alpha) * result[i-1]
        
        return pd.Series(result, index=series.index)
    
    def bcwsma(self, series, length, m):
        """自定义 bcwsma (用于 KDJ) - 正确处理 NaN 值"""
        # 处理 NaN 值，使用 nz 逻辑（将 NaN 替换为 0）
        clean_series = series.fillna(0)
        res = np.zeros(len(clean_series))
        res[0] = clean_series.iloc[0]
        arr = clean_series.values
        for i in range(1, len(clean_series)):
            prev = res[i-1]
            current = arr[i]
            res[i] = (m * current + (length - m) * prev) / length
        return pd.Series(res, index=series.index)
    
    def calculate_indicators(self, df):
        """
        计算所有技术指标
        """
        if len(df) < 1000:
            raise ValueError("数据不足，至少需要 1000 根 K 线")
        
        # === 1. Stochastic %K (顶底系统) ===
        lowest_low = df['low'].rolling(window=self.k_period).min()
        highest_high = df['high'].rolling(window=self.k_period).max()
        stoch_k_raw = 100 * (df['close'] - lowest_low) / (highest_high - lowest_low)
        df['stoch_k'] = stoch_k_raw.rolling(window=self.k_smooth).mean()
        
        # === 2. KDJ (GM_V2) ===
        rsv = 100 * (df['close'] - df['low'].rolling(self.kdj_ilong).min()) / \
              (df['high'].rolling(self.kdj_ilong).max() - df['low'].rolling(self.kdj_ilong).min())
        rsv = rsv.fillna(50)
        df['pk'] = self.bcwsma(rsv, self.kdj_isig, 1)
        df['pd'] = self.bcwsma(df['pk'], self.kdj_isig, 1)
        
        # === 3. OBV-ADX ===
        obv = (np.sign(df['close'].diff()) * df['volume']).fillna(0).cumsum()
        
        up_bottom = obv.diff()
        down_bottom = -obv.diff()
        
        plusDM_bottom = pd.Series(np.where(
            (up_bottom > down_bottom) & (up_bottom > 0), 
            up_bottom, 
            0
        ), index=df.index)
        
        minusDM_bottom = pd.Series(np.where(
            (down_bottom > up_bottom) & (down_bottom > 0), 
            down_bottom, 
            0
        ), index=df.index)
        
        tr_ur = self.calculate_rma(obv.rolling(self.obv_len).std(), self.obv_len).replace(0, 1e-10)
        
        # 修复：完全按照Pine Script的OBV-ADX计算
        plus_bottom = 100 * self.calculate_ema(plusDM_bottom, self.obv_len) / tr_ur
        minus_bottom = 100 * self.calculate_ema(minusDM_bottom, self.obv_len) / tr_ur
        
        # 处理NaN值 (对应fixnan)
        plus_bottom = plus_bottom.fillna(0)
        minus_bottom = minus_bottom.fillna(0)
        
        sum_bottom = plus_bottom + minus_bottom
        sum_bottom = sum_bottom.replace(0, 1)  # 避免除零
        adx_bottom = 100 * self.calculate_ema(abs(plus_bottom - minus_bottom) / sum_bottom, self.obv_sig)
        
        df['obv_plus'] = plus_bottom
        df['obv_minus'] = minus_bottom
        df['obv_adx'] = adx_bottom
        
        # === 4. ADX (Wilder's Smoothing) ===
        len_adx = 14
        
        tr1 = df['high'] - df['low']
        tr2 = abs(df['high'] - df['close'].shift(1))
        tr3 = abs(df['low'] - df['close'].shift(1))
        TrueRange = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        
        high_diff = df['high'].diff()
        low_diff = df['low'].diff()
        DirectionalMovementPlus = np.where(
            (high_diff > -low_diff) & (high_diff > 0),
            high_diff,
            0
        )
        DirectionalMovementMinus = np.where(
            (-low_diff > high_diff) & (-low_diff > 0),
            -low_diff,
            0
        )
        
        SmoothedTrueRange = np.zeros(len(df))
        SmoothedDirectionalMovementPlus = np.zeros(len(df))
        SmoothedDirectionalMovementMinus = np.zeros(len(df))
        
        SmoothedTrueRange[len_adx-1] = TrueRange[:len_adx].mean()
        SmoothedDirectionalMovementPlus[len_adx-1] = DirectionalMovementPlus[:len_adx].mean()
        SmoothedDirectionalMovementMinus[len_adx-1] = DirectionalMovementMinus[:len_adx].mean()
        
        for i in range(len_adx, len(df)):
            SmoothedTrueRange[i] = (SmoothedTrueRange[i-1] - 
                                    (SmoothedTrueRange[i-1] / len_adx) + 
                                    TrueRange.iloc[i])
            SmoothedDirectionalMovementPlus[i] = (SmoothedDirectionalMovementPlus[i-1] - 
                                                  (SmoothedDirectionalMovementPlus[i-1] / len_adx) + 
                                                  DirectionalMovementPlus[i])
            SmoothedDirectionalMovementMinus[i] = (SmoothedDirectionalMovementMinus[i-1] - 
                                                   (SmoothedDirectionalMovementMinus[i-1] / len_adx) + 
                                                   DirectionalMovementMinus[i])
        
        SmoothedTrueRange = pd.Series(SmoothedTrueRange, index=df.index).replace(0, 1e-10)
        DIPlus = 100 * SmoothedDirectionalMovementPlus / SmoothedTrueRange
        DIMinus = 100 * SmoothedDirectionalMovementMinus / SmoothedTrueRange
        
        DX = 100 * abs(DIPlus - DIMinus) / (DIPlus + DIMinus).replace(0, 1)
        
        df['trend_adx'] = DX.rolling(window=len_adx).apply(
            lambda x: np.average(x, weights=np.arange(1, len_adx + 1)), raw=True
        )
        df['adx_slope'] = df['trend_adx'].diff()
        
        atr = pd.Series(SmoothedTrueRange, index=df.index)
        
        # === 5. 趋势1策略指标 ===
        # 均线
        df['ma12'] = self.calculate_ema(df['close'], 12)
        df['ma144'] = self.calculate_ema(df['close'], 144)
        df['ma169'] = self.calculate_ema(df['close'], 169)
        
        # RSI - 使用RMA以匹配TradingView
        try:
            delta = df['close'].diff()
            gain = delta.clip(lower=0)
            loss = -delta.clip(upper=0)
            
            # 使用RMA计算平均增益和损失
            avg_gain = self.calculate_rma(gain.fillna(0), self.rsi_len)
            avg_loss = self.calculate_rma(loss.fillna(0), self.rsi_len)
            
            # 防止除零错误
            avg_loss = avg_loss.replace(0, 1e-10)
            
            rs = avg_gain / avg_loss
            rsi_values = 100 - (100 / (1 + rs))
            
            # 验证RSI值的合理性
            rsi_values = rsi_values.clip(lower=0, upper=100)
            
            # 填充NaN值
            rsi_values = rsi_values.fillna(50.0)
            
            df['rsi'] = rsi_values
        except Exception as e:
            print(f"❌ RSI计算错误: {e}，使用默认值 50")
            df['rsi'] = 50.0
        
        # MACD策略1 (12, 26, 9)
        exp12_1 = df['close'].ewm(span=12, adjust=False).mean()
        exp26_1 = df['close'].ewm(span=26, adjust=False).mean()
        df['macd_line_1'] = exp12_1 - exp26_1
        df['macd_signal_1'] = df['macd_line_1'].ewm(span=9, adjust=False).mean()
        
        # MACD策略2 (6, 13, 5)
        exp6_2 = df['close'].ewm(span=6, adjust=False).mean()
        exp13_2 = df['close'].ewm(span=13, adjust=False).mean()
        df['macd_line_2'] = exp6_2 - exp13_2
        df['macd_signal_2'] = df['macd_line_2'].ewm(span=5, adjust=False).mean()
        
        # CCI指标
        tp = (df['high'] + df['low'] + df['close']) / 3
        df['cci_55'] = (tp - tp.rolling(55).mean()) / (0.015 * tp.rolling(55).std())
        df['cci_144'] = (tp - tp.rolling(144).mean()) / (0.015 * tp.rolling(144).std())
        
        # === 6. SMC 摆动订单块检测 ===
        swing_length = self.swing_len
        
        atrMeasure = atr
        volatilityMeasure = atrMeasure
        highVolatilityBar = (df['high'] - df['low']) >= (2 * volatilityMeasure)
        
        parsedHigh = np.where(highVolatilityBar, df['low'], df['high'])
        parsedLow = np.where(highVolatilityBar, df['high'], df['low'])
        df['parsed_high'] = parsedHigh
        df['parsed_low'] = parsedLow
        
        # Leg函数
        leg = np.zeros(len(df), dtype=int)
        
        for i in range(swing_length, len(df)):
            recent_highs = parsedHigh[i-swing_length:i]
            recent_lows = parsedLow[i-swing_length:i]
            
            if parsedHigh[i-swing_length] > max(recent_highs):
                leg[i] = 0  # BEARISH_LEG
            elif parsedLow[i-swing_length] < min(recent_lows):
                leg[i] = 1  # BULLISH_LEG
            else:
                leg[i] = leg[i-1] if i > 0 else 0
        
        df['leg'] = leg
        
        # 摆动点检测
        df['swing_high_bar'] = False
        df['swing_low_bar'] = False
        df['swing_high_price'] = np.nan
        df['swing_low_price'] = np.nan
        df['swing_high_index'] = -1
        df['swing_low_index'] = -1
        
        for i in range(swing_length + 1, len(df)):
            leg_changed = leg[i] != leg[i-1]
            
            if leg_changed:
                if leg[i-1] == 1 and leg[i] == 0:
                    swing_idx = i - swing_length
                    if swing_idx >= 0:
                        df.loc[df.index[swing_idx], 'swing_high_bar'] = True
                        df.loc[df.index[swing_idx], 'swing_high_price'] = df['high'].iloc[swing_idx]
                        df.loc[df.index[swing_idx], 'swing_high_index'] = swing_idx
                
                elif leg[i-1] == 0 and leg[i] == 1:
                    swing_idx = i - swing_length
                    if swing_idx >= 0:
                        df.loc[df.index[swing_idx], 'swing_low_bar'] = True
                        df.loc[df.index[swing_idx], 'swing_low_price'] = df['low'].iloc[swing_idx]
                        df.loc[df.index[swing_idx], 'swing_low_index'] = swing_idx
        
        # 订单块检测
        df['bullish_ob'] = False
        df['bearish_ob'] = False
        df['ob_high'] = np.nan
        df['ob_low'] = np.nan
        
        order_blocks = []
        
        for i in range(swing_length + 2, len(df)):
            curr_close = df['close'].iloc[i]
            
            if not pd.isna(df['swing_high_price'].iloc[i]):
                swing_high_price = df['swing_high_price'].iloc[i]
                swing_high_idx = int(df['swing_high_index'].iloc[i])
                
                if curr_close > swing_high_price and swing_high_idx >= 0:
                    search_start = max(0, swing_high_idx - swing_length)
                    search_end = swing_high_idx + 1
                    
                    slice_parsed_highs = parsedHigh[search_start:search_end]
                    if len(slice_parsed_highs) > 0:
                        max_parsed_high_idx = search_start + np.argmax(slice_parsed_highs)
                        
                        ob_high_orig = df['high'].iloc[max_parsed_high_idx]
                        ob_low_orig = df['low'].iloc[max_parsed_high_idx]
                        
                        expansion = atrMeasure.iloc[max_parsed_high_idx] * 0.1
                        ob_high = ob_high_orig + expansion
                        ob_low = ob_low_orig - expansion
                        
                        df.loc[df.index[max_parsed_high_idx], 'bullish_ob'] = True
                        df.loc[df.index[max_parsed_high_idx], 'ob_high'] = ob_high
                        df.loc[df.index[max_parsed_high_idx], 'ob_low'] = ob_low
                        
                        order_blocks.append({
                            'type': 'BULLISH',
                            'high': ob_high,
                            'low': ob_low,
                            'index': max_parsed_high_idx,
                            'mitigated': False
                        })
            
            if not pd.isna(df['swing_low_price'].iloc[i]):
                swing_low_price = df['swing_low_price'].iloc[i]
                swing_low_idx = int(df['swing_low_index'].iloc[i])
                
                if curr_close < swing_low_price and swing_low_idx >= 0:
                    search_start = max(0, swing_low_idx - swing_length)
                    search_end = swing_low_idx + 1
                    
                    slice_parsed_lows = parsedLow[search_start:search_end]
                    if len(slice_parsed_lows) > 0:
                        min_parsed_low_idx = search_start + np.argmin(slice_parsed_lows)
                        
                        ob_high_orig = df['high'].iloc[min_parsed_low_idx]
                        ob_low_orig = df['low'].iloc[min_parsed_low_idx]
                        
                        expansion = atrMeasure.iloc[min_parsed_low_idx] * 0.1
                        ob_high = ob_high_orig + expansion
                        ob_low = ob_low_orig - expansion
                        
                        df.loc[df.index[min_parsed_low_idx], 'bearish_ob'] = True
                        df.loc[df.index[min_parsed_low_idx], 'ob_high'] = ob_high
                        df.loc[df.index[min_parsed_low_idx], 'ob_low'] = ob_low
                        
                        order_blocks.append({
                            'type': 'BEARISH',
                            'high': ob_high,
                            'low': ob_low,
                            'index': min_parsed_low_idx,
                            'mitigated': False
                        })
        
        # 订单块失效检测
        for i in range(len(df)):
            curr_high = df['high'].iloc[i]
            curr_low = df['low'].iloc[i]
            
            for ob in order_blocks:
                if ob['mitigated']:
                    continue
                
                if ob['type'] == 'BULLISH' and curr_low < ob['low']:
                    ob['mitigated'] = True
                    if ob['index'] < len(df):
                        df.loc[df.index[ob['index']], 'bullish_ob'] = False
                
                elif ob['type'] == 'BEARISH' and curr_high > ob['high']:
                    ob['mitigated'] = True
                    if ob['index'] < len(df):
                        df.loc[df.index[ob['index']], 'bearish_ob'] = False
        
        return df
    
    def check_signals(self, df, timeframe='30m'):
        """检查信号"""
        # 🔥 只在30分钟和1小时周期产生信号
        if timeframe not in ['30m', '1h']:
            return {"action": "HOLD", "reason": f"{timeframe}周期不交易", "type": "NONE"}
        
        if len(df) < 4:
            return {"action": "HOLD", "reason": "数据不足", "type": "NONE"}
        
        curr = df.iloc[-2]
        prev = df.iloc[-3]
        
        # === 顶底信号 ===
        stoch_os = curr['stoch_k'] < 20
        stoch_ob = curr['stoch_k'] > 80
        kdj_gold = (prev['pk'] < prev['pd']) and (curr['pk'] > curr['pd'])
        kdj_dead = (prev['pk'] > prev['pd']) and (curr['pk'] < curr['pd'])
        smi_kdj_buy = stoch_os and kdj_gold
        smi_kdj_sell = stoch_ob and kdj_dead
        
        obv_buy = (curr['obv_minus'] >= 22) and (curr['obv_adx'] >= 22) and (curr['obv_plus'] <= 18)
        obv_sell = (curr['obv_plus'] >= 22) and (curr['obv_adx'] >= 22) and (curr['obv_minus'] <= 18)
        
        bottom_buy = smi_kdj_buy and obv_buy
        bottom_sell = smi_kdj_sell and obv_sell
        
        # === 趋势1主信号 ===
        is_trending = (curr['trend_adx'] > self.osc_len) and (curr['adx_slope'] > 0)
        trend_filter = is_trending if self.osc_filter else True
        
        trend_up = curr['ma12'] > curr['ma144'] and curr['ma12'] > curr['ma169']
        trend_down = curr['ma12'] < curr['ma144'] and curr['ma12'] < curr['ma169']
        
        rsi_val = curr['rsi'] if not pd.isna(curr['rsi']) else 50.0
        is_rsi_neutral = rsi_val >= 45 and rsi_val <= 55
        
        # MACD策略1
        macd_golden_1 = (prev['macd_line_1'] <= prev['macd_signal_1']) and (curr['macd_line_1'] > curr['macd_signal_1'])
        macd_death_1 = (prev['macd_line_1'] >= prev['macd_signal_1']) and (curr['macd_line_1'] < curr['macd_signal_1'])
        cci_above_100_1 = curr['cci_55'] > 100
        cci_below_neg100_1 = curr['cci_55'] < -100
        
        buy_cond_1 = trend_filter and trend_up and macd_golden_1 and cci_above_100_1 and not is_rsi_neutral
        sell_cond_1 = trend_filter and trend_down and macd_death_1 and cci_below_neg100_1 and not is_rsi_neutral
        
        # MACD策略2
        macd_golden_2 = (prev['macd_line_2'] <= prev['macd_signal_2']) and (curr['macd_line_2'] > curr['macd_signal_2'])
        macd_death_2 = (prev['macd_line_2'] >= prev['macd_signal_2']) and (curr['macd_line_2'] < curr['macd_signal_2'])
        cci_above_100_2 = curr['cci_144'] > 100
        cci_below_neg100_2 = curr['cci_144'] < -100
        
        buy_cond_2 = trend_filter and trend_up and macd_golden_2 and cci_above_100_2 and not is_rsi_neutral
        sell_cond_2 = trend_filter and trend_down and macd_death_2 and cci_below_neg100_2 and not is_rsi_neutral
        
        trend_buy = buy_cond_1 or buy_cond_2
        trend_sell = sell_cond_1 or sell_cond_2
        
        # === 订单块信号 ===
        ob_long_signal = False
        ob_short_signal = False
        
        for i in range(min(50, len(df) - 1), 0, -1):
            check_candle = df.iloc[-i]
            
            if check_candle.get('bullish_ob', False):
                ob_high = check_candle.get('ob_high', 0)
                ob_low = check_candle.get('ob_low', 0)
                
                if curr['low'] <= ob_high and curr['low'] >= ob_low:
                    if curr['close'] > ob_low:
                        ob_long_signal = True
                        break
            
            if check_candle.get('bearish_ob', False):
                ob_high = check_candle.get('ob_high', 0)
                ob_low = check_candle.get('ob_low', 0)
                
                if curr['high'] >= ob_low and curr['high'] <= ob_high:
                    if curr['close'] < ob_high:
                        ob_short_signal = True
                        break
        
        # === 信号优先级 ===
        # 主信号：趋势1策略
        if trend_buy:
            return {
                "action": "LONG",
                "type": "MAIN_TREND",
                "position_pct": self.main_signal_pct,
                "leverage": 50,
                "reason": f"[{timeframe}]趋势1主做多 | MA12={curr['ma12']:.2f} | RSI={rsi_val:.1f}"
            }
        elif trend_sell:
            return {
                "action": "SHORT",
                "type": "MAIN_TREND",
                "position_pct": self.main_signal_pct,
                "leverage": 50,
                "reason": f"[{timeframe}]趋势1主做空 | MA12={curr['ma12']:.2f} | RSI={rsi_val:.1f}"
            }
        
        # 次信号：顶底系统
        if bottom_buy:
            return {
                "action": "LONG",
                "type": "SUB_BOTTOM",
                "position_pct": self.sub_signal_pct,
                "leverage": 50,
                "reason": f"[{timeframe}]抄底信号 | Stoch={curr['stoch_k']:.1f}"
            }
        elif bottom_sell:
            return {
                "action": "SHORT",
                "type": "SUB_TOP",
                "position_pct": self.sub_signal_pct,
                "leverage": 50,
                "reason": f"[{timeframe}]逃顶信号 | Stoch={curr['stoch_k']:.1f}"
            }
        
        # 订单块信号
        if timeframe in ['30m', '1h']:
            if ob_long_signal:
                return {
                    "action": "LONG",
                    "type": "SUB_ORDER_BLOCK",
                    "position_pct": self.sub_signal_pct,
                    "leverage": 50,
                    "reason": f"[{timeframe}]订单块支撑"
                }
            elif ob_short_signal:
                return {
                    "action": "SHORT",
                    "type": "SUB_ORDER_BLOCK",
                    "position_pct": self.sub_signal_pct,
                    "leverage": 50,
                    "reason": f"[{timeframe}]订单块压力"
                }
        
        return {"action": "HOLD", "reason": "无有效信号", "type": "NONE"}

    def run_analysis_with_data(self, symbol, preloaded_data, due_tfs):
        """
        🔥 数据解耦版本：使用预加载的K线数据进行分析
        
        参数：
        - symbol: 交易对（如 "BTC/USDT"）
        - preloaded_data: 字典 {tf: DataFrame} 预加载的K线数据
        - due_tfs: 需要分析的周期列表
        
        返回：
        [
            {
                "tf": "30m",
                "action": "LONG",
                "type": "MAIN_TREND",
                "rsi": 28.5,
                "signal": {...},
                "reason": "双MACD金叉",
                "candle_time": Timestamp(...)
            },
            ...
        ]
        """
        scan_results = []
        
        for tf in due_tfs:
            # 使用预加载的数据
            df = preloaded_data.get(tf)
            
            if df is None or len(df) < 1000:
                scan_results.append({
                    "tf": tf,
                    "action": "ERROR",
                    "type": "DATA_ERROR",
                    "rsi": 50.0,
                    "signal": None,
                    "reason": f"数据不足 {len(df) if df is not None else 0} < 1000",
                    "candle_time": None
                })
                continue
            
            try:
                # 计算技术指标
                df_with_indicators = self.calculate_indicators(df)
                
                # 检查信号
                sig = self.check_signals(df_with_indicators, timeframe=tf)
                
                # 获取 RSI 值（安全访问）
                if 'rsi' in df_with_indicators.columns and not df_with_indicators['rsi'].isnull().all():
                    rsi_val = df_with_indicators.iloc[-1]['rsi']
                    if pd.isna(rsi_val):
                        rsi_val = 50.0
                else:
                    rsi_val = 50.0
                
                # 🔥 获取K线时间戳（使用当前K线，与信号计算一致）
                candle_time = None
                if len(df_with_indicators) >= 1:
                    candle_time = df_with_indicators.iloc[-1]['timestamp']
                
                scan_results.append({
                    "tf": tf,
                    "action": sig['action'],
                    "type": sig.get('type', 'MAIN_TREND'),  # 默认为主趋势类型
                    "rsi": rsi_val,
                    "signal": sig,
                    "reason": sig.get('reason', ''),
                    "candle_time": candle_time
                })
                
            except Exception as e:
                scan_results.append({
                    "tf": tf,
                    "action": "ERROR",
                    "type": "CALC_ERROR",
                    "rsi": 50.0,
                    "signal": None,
                    "reason": f"计算失败: {str(e)}",
                    "candle_time": None
                })
        
        return scan_results
