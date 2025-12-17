# strategy.py - 完整策略引擎

import pandas as pd
import numpy as np

class TradingStrategy:
    """
    综合策略引擎：趋势2.3 + 何以为底 + SMC
    """
    def __init__(self):
        # === 参数配置 ===
        self.bottom_mode = "平衡模式"  # 保守模式、平衡模式、激进模式、恶魔模式
        self.k_period = 14
        self.k_smooth = 5
        self.kdj_ilong = 9
        self.kdj_isig = 3
        self.obv_len = 22
        self.obv_sig = 22
        self.rsi_len = 14
        self.rsi_os = 30
        self.rsi_ob = 70
        self.osc_filter = False
        self.osc_len = 20
        self.swing_len = 50
        
        # 仓位与风控
        self.max_leverage = 50
        self.max_total_position_pct = 0.10
        self.main_signal_pct = 0.03
        self.sub_signal_pct = 0.01
        
        # 🔥 新增：何以为底模式参数
        self.more_bottom = True  # 平衡模式默认开启
        self.choose_bottom = 1   # 平衡模式对应的参数
    
    def set_bottom_mode(self, mode):
        """设置何以为底模式"""
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
            print(f"✅ 何以为底模式已设置为: {mode}")
        else:
            print(f"❌ 不支持的模式: {mode}")
    
    def calculate_ema(self, series, period):
        """TradingView精确EMA计算 - 使用SMA初始化"""
        alpha = 2.0 / (period + 1.0)
        result = np.zeros(len(series))
        
        # 🔥 关键修复：使用前N个点的SMA作为初始值（与TradingView一致）
        if len(series) < period:
            # 数据不足，使用简单平均
            result[0] = series.iloc[0]
        else:
            # 计算前period个点的SMA作为第一个EMA值
            result[period-1] = series.iloc[:period].mean()
            
            # 前period-1个点填充NaN或使用SMA递增计算
            for i in range(period):
                result[i] = series.iloc[:i+1].mean() if i < period-1 else result[period-1]
        
        # 从period开始递归计算EMA
        start_idx = period if len(series) >= period else 1
        for i in range(start_idx, len(series)):
            result[i] = alpha * series.iloc[i] + (1 - alpha) * result[i-1]
        
        return pd.Series(result, index=series.index)
    
    def calculate_rma(self, series, period):
        """RMA 计算（Wilder's smoothing）- 完全对齐TradingView ta.rma"""
        # 🔥 关键修复：完整实现Wilder's smoothing算法
        # RMA[i] = (RMA[i-1] * (period - 1) + value[i]) / period
        
        result = np.zeros(len(series))
        values = series.fillna(0).values  # 处理NaN
        
        # 初始化：前period个值的简单平均
        if len(series) < period:
            result[0] = values[0]
            for i in range(1, len(series)):
                result[i] = (result[i-1] * i + values[i]) / (i + 1)
        else:
            # 第一个RMA值 = 前period个值的平均
            result[period-1] = np.mean(values[:period])
            
            # 前period-1个值使用累积平均
            for i in range(period-1):
                result[i] = np.mean(values[:i+1])
            
            # 从period开始使用Wilder's smoothing递归公式
            for i in range(period, len(series)):
                result[i] = (result[i-1] * (period - 1) + values[i]) / period
        
        return pd.Series(result, index=series.index)
    
    def calculate_sma(self, series, period):
        """SMA 计算"""
        return series.rolling(window=period).mean()
    
    def bcwsma(self, series, length, m):
        """
        自定义 bcwsma (用于 KDJ)
        _bcwsma := (m * series + (length - m) * nz(_bcwsma[1])) / length
        """
        res = np.zeros(len(series))
        res[0] = series.iloc[0] if not pd.isna(series.iloc[0]) else 0
        arr = series.values
        for i in range(1, len(series)):
            prev = res[i-1] if not np.isnan(res[i-1]) else 0
            current = arr[i] if not np.isnan(arr[i]) else 0
            res[i] = (m * current + (length - m) * prev) / length
        return pd.Series(res, index=series.index)
    
    def calculate_indicators(self, df):
        """
        计算所有技术指标
        输入 df 必须包含: open, high, low, close, volume
        """
        # 🔥 修复：降低最小K线要求，支持新上线币种
        # 理想情况需要 1000 根以消除 EMA/RMA 初始化误差
        # 但对于新币种，接受最少 200 根（会有一定误差但可用）
        MIN_BARS_IDEAL = 1000
        MIN_BARS_ACCEPTABLE = 200
        
        if len(df) < MIN_BARS_ACCEPTABLE:
            raise ValueError(f"数据不足，至少需要 {MIN_BARS_ACCEPTABLE} 根 K 线（当前: {len(df)}）")
        
        if len(df) < MIN_BARS_IDEAL:
            # 数据不足理想值，打印警告但继续计算
            import logging
            logging.getLogger(__name__).warning(
                f"K线数量 ({len(df)}) 少于理想值 ({MIN_BARS_IDEAL})，指标可能存在初始化误差"
            )
        
        # === 1. Stochastic %K ===
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
        
        # === 3. OBV-ADX (完全按照Pine Script逻辑) ===
        # 🔥 TradingView: ta.obv 是内置的累积OBV
        # Pine Script: up_bottom = ta.change(ta.obv), down_bottom = -ta.change(ta.obv)
        obv = (np.sign(df['close'].diff()) * df['volume']).fillna(0).cumsum()
        
        # 🔥 修复：完全按照Pine Script的OBV-ADX计算
        # ta.change(ta.obv) = obv - obv[1]
        up_bottom = obv.diff()
        down_bottom = -obv.diff()
        
        # 处理plusDM和minusDM的逻辑
        # Pine: plusDM_bottom = na(up_bottom) ? na : up_bottom > down_bottom and up_bottom > 0 ? up_bottom : 0
        plusDM_bottom = pd.Series(np.where(
            (up_bottom > down_bottom) & (up_bottom > 0), 
            up_bottom, 
            0
        ), index=df.index)
        
        # Pine: minusDM_bottom = na(down_bottom) ? na : down_bottom > up_bottom and down_bottom > 0 ? down_bottom : 0
        minusDM_bottom = pd.Series(np.where(
            (down_bottom > up_bottom) & (down_bottom > 0), 
            down_bottom, 
            0
        ), index=df.index)
        
        # 🔥 计算trur: ta.rma(ta.stdev(ta.obv, len_bottom), len_bottom)
        # TradingView ta.stdev 使用样本标准差 (ddof=1)，pandas rolling().std() 默认也是 ddof=1
        obv_stdev = obv.rolling(self.obv_len).std(ddof=1)  # 显式指定 ddof=1
        tr_ur = self.calculate_rma(obv_stdev.fillna(0), self.obv_len).replace(0, 1e-10)
        
        # 🔥 计算plus和minus: 100 * ta.ema(plusDM_bottom, len_bottom) / trur_bottom
        plus_bottom = 100 * self.calculate_ema(plusDM_bottom, self.obv_len) / tr_ur
        minus_bottom = 100 * self.calculate_ema(minusDM_bottom, self.obv_len) / tr_ur
        
        # 🔥 处理NaN值 (对应 fixnan - 用前一个有效值填充)
        plus_bottom = plus_bottom.ffill().fillna(0)
        minus_bottom = minus_bottom.ffill().fillna(0)
        
        # 🔥 计算ADX: 100 * ta.ema(abs(plus - minus) / sum, lensig)
        sum_bottom = plus_bottom + minus_bottom
        sum_bottom = sum_bottom.replace(0, 1)  # 避免除零
        adx_bottom = 100 * self.calculate_ema(abs(plus_bottom - minus_bottom) / sum_bottom, self.obv_sig)
        
        df['obv_plus'] = plus_bottom
        df['obv_minus'] = minus_bottom
        df['obv_adx'] = adx_bottom
        
        # === 4. 趋势指标 (ADX) - 完全按 TradingView 逻辑 ===
        # 🔥 使用 Wilder's Smoothing 累积平滑，不是 RMA
        len_adx = 14
        
        # True Range
        tr1 = df['high'] - df['low']
        tr2 = abs(df['high'] - df['close'].shift(1))
        tr3 = abs(df['low'] - df['close'].shift(1))
        TrueRange = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        
        # Directional Movement
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
        
        # 🔥 Wilder's Smoothing （累积平滑）
        SmoothedTrueRange = np.zeros(len(df))
        SmoothedDirectionalMovementPlus = np.zeros(len(df))
        SmoothedDirectionalMovementMinus = np.zeros(len(df))
        
        # 初始化：前 N 个值的简单平均
        SmoothedTrueRange[len_adx-1] = TrueRange[:len_adx].mean()
        SmoothedDirectionalMovementPlus[len_adx-1] = DirectionalMovementPlus[:len_adx].mean()
        SmoothedDirectionalMovementMinus[len_adx-1] = DirectionalMovementMinus[:len_adx].mean()
        
        # 累积平滑公式： Smoothed[i] = Smoothed[i-1] - (Smoothed[i-1]/N) + Current[i]
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
        
        # 计算 DI+ 和 DI-
        SmoothedTrueRange = pd.Series(SmoothedTrueRange, index=df.index).replace(0, 1e-10)
        DIPlus = 100 * SmoothedDirectionalMovementPlus / SmoothedTrueRange
        DIMinus = 100 * SmoothedDirectionalMovementMinus / SmoothedTrueRange
        
        # 计算 DX
        DX = 100 * abs(DIPlus - DIMinus) / (DIPlus + DIMinus).replace(0, 1)
        
        # 🔥 ADX = WMA(DX, 14) （加权移动平均）
        df['trend_adx'] = DX.rolling(window=len_adx).apply(
            lambda x: np.average(x, weights=np.arange(1, len_adx + 1)), raw=True
        )
        df['adx_slope'] = df['trend_adx'].diff()
        
        # 保留 ATR 用于订单块
        atr = pd.Series(SmoothedTrueRange, index=df.index)
        
        # === 5. EMA 快慢通道 ===
        df['ema12'] = self.calculate_ema(df['close'], 12)
        fast_a = self.calculate_ema(df['close'], 144)
        fast_b = self.calculate_ema(df['close'], 169)
        df['fast_top'] = np.maximum(fast_a, fast_b)
        df['fast_bot'] = np.minimum(fast_a, fast_b)
        slow_a = self.calculate_ema(df['close'], 576)
        slow_b = self.calculate_ema(df['close'], 676)
        df['slow_top'] = np.maximum(slow_a, slow_b)
        df['slow_bot'] = np.minimum(slow_a, slow_b)
        
        # === 6. MACD ===
        ema_fast = self.calculate_ema(df['close'], 13)
        ema_slow = self.calculate_ema(df['close'], 34)
        df['macd'] = ema_fast - ema_slow
        df['macd_signal'] = self.calculate_ema(df['macd'], 9)
        df['macd_hist'] = df['macd'] - df['macd_signal']
        
        # === 7. RSI ===
        try:
            # 确保 RSI 列存在，初始化为默认值
            df['rsi'] = 50.0  # 默认中性值
            
            # 验证数据充足性
            if len(df) < self.rsi_len + 1:
                print(f"⚠️ RSI计算警告: 数据长度 {len(df)} 小于所需 {self.rsi_len + 1}，使用默认值 50")
                df['rsi'] = 50.0
            else:
                # 计算 RSI
                delta = df['close'].diff()
                gain = delta.clip(lower=0)
                loss = -delta.clip(upper=0)
                
                # 防止除零错误
                avg_gain = self.calculate_rma(gain.fillna(0), self.rsi_len)
                avg_loss = self.calculate_rma(loss.fillna(0), self.rsi_len)
                
                # 替换零值避免无穷大
                avg_loss = avg_loss.replace(0, 1e-10)
                
                rs = avg_gain / avg_loss
                rsi_values = 100 - (100 / (1 + rs))
                
                # 验证 RSI 值的合理性
                rsi_values = rsi_values.clip(lower=0, upper=100)
                
                # 填充 NaN 值
                rsi_values = rsi_values.fillna(50.0)
                
                df['rsi'] = rsi_values
                
                # 验证最终结果
                if df['rsi'].isnull().any():
                    print(f"⚠️ RSI计算警告: 检测到 NaN 值，已替换为默认值 50")
                    df['rsi'] = df['rsi'].fillna(50.0)
                    
        except Exception as e:
            print(f"❌ RSI计算错误: {e}，使用默认值 50")
            df['rsi'] = 50.0
        
        # === 8. SMC 摆动结构检测 (完全按 TradingView 逻辑) ===
        # 🔥 关键：实现 leg_trend 函数（识别趋势腿）
        
        # Step 1: 过滤高波动K线 (parsedHighs/parsedLows)
        atrMeasure = atr  # 使用上面计算的 ATR
        volatilityMeasure = atrMeasure  # 简化为 ATR
        highVolatilityBar = (df['high'] - df['low']) >= (2 * volatilityMeasure)
        
        # 🔥 高波动K线：交换 high 和 low
        parsedHigh = np.where(highVolatilityBar, df['low'], df['high'])
        parsedLow = np.where(highVolatilityBar, df['high'], df['low'])
        df['parsed_high'] = parsedHigh
        df['parsed_low'] = parsedLow
        
        # Step 2: 计算 Leg (趋势腿)
        swing_length = self.swing_len
        leg = np.zeros(len(df), dtype=int)
        
        for i in range(swing_length, len(df)):
            # 查找前 swing_length 个 K线的最高点和最低点
            recent_highs = parsedHigh[i-swing_length:i]
            recent_lows = parsedLow[i-swing_length:i]
            
            # 新的高点突破 -> 看跌腿 (BEARISH_LEG = 0)
            if parsedHigh[i-swing_length] > max(recent_highs):
                leg[i] = 0  # BEARISH_LEG
            # 新的低点突破 -> 看涨腿 (BULLISH_LEG = 1)
            elif parsedLow[i-swing_length] < min(recent_lows):
                leg[i] = 1  # BULLISH_LEG
            else:
                leg[i] = leg[i-1] if i > 0 else 0
        
        df['leg'] = leg
        
        # Step 3: 检测摆动点 (Swing Highs/Lows)
        df['swing_high_bar'] = False
        df['swing_low_bar'] = False
        df['swing_high_price'] = np.nan
        df['swing_low_price'] = np.nan
        df['swing_high_index'] = -1
        df['swing_low_index'] = -1
        
        current_swing_high = np.nan
        current_swing_low = np.nan
        last_swing_high_idx = -1
        last_swing_low_idx = -1
        
        for i in range(swing_length + 1, len(df)):
            # 检测 Leg 变化
            leg_changed = leg[i] != leg[i-1]
            
            if leg_changed:
                # 从看涨腿转为看跌腿 -> 记录高点
                if leg[i-1] == 1 and leg[i] == 0:
                    swing_idx = i - swing_length
                    if swing_idx >= 0:
                        df.loc[df.index[swing_idx], 'swing_high_bar'] = True
                        df.loc[df.index[swing_idx], 'swing_high_price'] = df['high'].iloc[swing_idx]
                        df.loc[df.index[swing_idx], 'swing_high_index'] = swing_idx
                        current_swing_high = df['high'].iloc[swing_idx]
                        last_swing_high_idx = swing_idx
                
                # 从看跌腿转为看涨腿 -> 记录低点
                elif leg[i-1] == 0 and leg[i] == 1:
                    swing_idx = i - swing_length
                    if swing_idx >= 0:
                        df.loc[df.index[swing_idx], 'swing_low_bar'] = True
                        df.loc[df.index[swing_idx], 'swing_low_price'] = df['low'].iloc[swing_idx]
                        df.loc[df.index[swing_idx], 'swing_low_index'] = swing_idx
                        current_swing_low = df['low'].iloc[swing_idx]
                        last_swing_low_idx = swing_idx
        
        # === 9. ATR 计算（用于订单块触发宽度）===
        df['atr'] = atr
        
        # === 10. 订单块检测（完全按 TradingView SMC 逻辑）===
        # 🔥 关键：基于摆动点突破来识别订单块
        
        df['bullish_ob'] = False
        df['bearish_ob'] = False
        df['ob_high'] = np.nan
        df['ob_low'] = np.nan
        df['ob_time'] = np.nan
        
        # 存储所有订单块（用于后续失效检测）
        order_blocks = []  # {type, high, low, time, index, mitigated}
        
        # 遍历所有K线，检测摆动点突破
        for i in range(swing_length + 2, len(df)):
            curr_close = df['close'].iloc[i]
            
            # 检测看涨摆动点突破 (close 突破 swing high)
            if not pd.isna(df['swing_high_price'].iloc[i]):
                swing_high_price = df['swing_high_price'].iloc[i]
                swing_high_idx = int(df['swing_high_index'].iloc[i])
                
                # 突破条件：当前收盘价 > 摆动高点
                if curr_close > swing_high_price and swing_high_idx >= 0:
                    # 🔥 在摆动高点之前的区间内找最高的K线 (看涨订单块)
                    # 区间：从上一个摆动低点到当前摆动高点
                    search_start = max(0, swing_high_idx - swing_length)
                    search_end = swing_high_idx + 1
                    
                    # 找 parsed_high 最大的K线
                    slice_parsed_highs = parsedHigh[search_start:search_end]
                    if len(slice_parsed_highs) > 0:
                        max_parsed_high_idx = search_start + np.argmax(slice_parsed_highs)
                        
                        # 订单块范围
                        ob_high_orig = df['high'].iloc[max_parsed_high_idx]
                        ob_low_orig = df['low'].iloc[max_parsed_high_idx]
                        
                        # 🔥 ATR 宽度扩展 (swingOBWidthMultiplier = 0.1)
                        expansion = atrMeasure.iloc[max_parsed_high_idx] * 0.1
                        ob_high = ob_high_orig + expansion
                        ob_low = ob_low_orig - expansion
                        
                        # 记录订单块
                        df.loc[df.index[max_parsed_high_idx], 'bullish_ob'] = True
                        df.loc[df.index[max_parsed_high_idx], 'ob_high'] = ob_high
                        df.loc[df.index[max_parsed_high_idx], 'ob_low'] = ob_low
                        df.loc[df.index[max_parsed_high_idx], 'ob_time'] = df.index[max_parsed_high_idx]
                        
                        order_blocks.append({
                            'type': 'BULLISH',
                            'high': ob_high,
                            'low': ob_low,
                            'index': max_parsed_high_idx,
                            'mitigated': False
                        })
            
            # 检测看跌摆动点突破 (close 突破 swing low)
            if not pd.isna(df['swing_low_price'].iloc[i]):
                swing_low_price = df['swing_low_price'].iloc[i]
                swing_low_idx = int(df['swing_low_index'].iloc[i])
                
                # 突破条件：当前收盘价 < 摆动低点
                if curr_close < swing_low_price and swing_low_idx >= 0:
                    # 🔥 在摆动低点之前的区间内找最低的K线 (看跌订单块)
                    search_start = max(0, swing_low_idx - swing_length)
                    search_end = swing_low_idx + 1
                    
                    # 找 parsed_low 最小的K线
                    slice_parsed_lows = parsedLow[search_start:search_end]
                    if len(slice_parsed_lows) > 0:
                        min_parsed_low_idx = search_start + np.argmin(slice_parsed_lows)
                        
                        # 订单块范围
                        ob_high_orig = df['high'].iloc[min_parsed_low_idx]
                        ob_low_orig = df['low'].iloc[min_parsed_low_idx]
                        
                        # 🔥 ATR 宽度扩展
                        expansion = atrMeasure.iloc[min_parsed_low_idx] * 0.1
                        ob_high = ob_high_orig + expansion
                        ob_low = ob_low_orig - expansion
                        
                        # 记录订单块
                        df.loc[df.index[min_parsed_low_idx], 'bearish_ob'] = True
                        df.loc[df.index[min_parsed_low_idx], 'ob_high'] = ob_high
                        df.loc[df.index[min_parsed_low_idx], 'ob_low'] = ob_low
                        df.loc[df.index[min_parsed_low_idx], 'ob_time'] = df.index[min_parsed_low_idx]
                        
                        order_blocks.append({
                            'type': 'BEARISH',
                            'high': ob_high,
                            'low': ob_low,
                            'index': min_parsed_low_idx,
                            'mitigated': False
                        })
        
        # 🔥 订单块失效检测 (Mitigation)
        for i in range(len(df)):
            curr_high = df['high'].iloc[i]
            curr_low = df['low'].iloc[i]
            
            for ob in order_blocks:
                if ob['mitigated']:
                    continue
                
                # 看涨订单块：价格跌破 ob_low 失效
                if ob['type'] == 'BULLISH' and curr_low < ob['low']:
                    ob['mitigated'] = True
                    # 清除订单块标记
                    if ob['index'] < len(df):
                        df.loc[df.index[ob['index']], 'bullish_ob'] = False
                
                # 看跌订单块：价格突破 ob_high 失效
                elif ob['type'] == 'BEARISH' and curr_high > ob['high']:
                    ob['mitigated'] = True
                    if ob['index'] < len(df):
                        df.loc[df.index[ob['index']], 'bearish_ob'] = False
        
        return df
    
    def check_signals(self, df, timeframe='3m'):
        """检查信号，新增timeframe参数用于信号源区分"""
        # 策略入口（静默，避免刷屏）
        
        if len(df) < 4:
            return {"action": "HOLD", "reason": "数据不足", "type": "NONE"}
        
        # 🔥 关键修复：验证 RSI 列是否存在
        if 'rsi' not in df.columns:
            raise ValueError("RSI column not found in df, please check calculation")
        
        # 验证 RSI 数据的有效性
        if df['rsi'].isnull().all():
            raise ValueError("RSI column contains all NaN values, calculation failed")
        
        # 🔥 00秒确认模式：使用已收盘的K线数据
        # 确保数据长度足够（至少4根K线）
        if len(df) < 4:
            return {"action": "HOLD", "reason": "数据不足（需至少4根K线）", "type": "NONE"}
        
        # 🔥 00秒确认模式（与TradingView收盘触发一致）
        # df.iloc[-1] 是刚开盘的新K线（只有几秒数据，不使用）
        # df.iloc[-2] 是刚收盘的K线（这是我们要判断的"当前K线"）
        # df.iloc[-3] 是上一根已收盘的K线
        curr = df.iloc[-2]   # 刚收盘的K线（与TradingView一致）
        prev = df.iloc[-3]   # 上一根已收盘的K线
        prev2 = df.iloc[-4]  # 上上根K线
        
        # 🔥 安全访问 RSI 值，提供默认值
        curr_rsi = curr.get('rsi', 50.0)
        prev_rsi = prev.get('rsi', 50.0)
        if pd.isna(curr_rsi):
            curr_rsi = 50.0
        if pd.isna(prev_rsi):
            prev_rsi = 50.0
        
        # === 趋势2.3 主信号 ===
        bullish_trend = (curr['ema12'] > curr['fast_top']) and (curr['ema12'] > curr['slow_top'])
        bearish_trend = (curr['ema12'] < curr['fast_bot']) and (curr['ema12'] < curr['slow_bot'])
        
        is_trending = (curr['trend_adx'] > self.osc_len) and (curr['adx_slope'] > 0)
        trend_filter = is_trending if self.osc_filter else True
        
        macd_below_rise = (curr['macd_hist'] < 0) and (curr['macd_hist'] > prev['macd_hist']) and \
                          (prev['macd_hist'] < prev2['macd_hist'])
        macd_above_fall = (curr['macd_hist'] > 0) and (curr['macd_hist'] < prev['macd_hist']) and \
                          (prev['macd_hist'] > prev2['macd_hist'])
        
        rsi_cross_up = (prev_rsi <= self.rsi_os) and (curr_rsi > self.rsi_os)
        rsi_cross_dn = (prev_rsi >= self.rsi_ob) and (curr_rsi < self.rsi_ob)
        
        long_cond = macd_below_rise and (curr_rsi > 50 or rsi_cross_up)
        short_cond = macd_above_fall and (curr_rsi < 50 or rsi_cross_dn)
        
        trend_buy = trend_filter and bullish_trend and long_cond
        trend_sell = trend_filter and bearish_trend and short_cond
        
        # === 何以为底信号 (完整实现，包含扩展信号) ===
        stoch_os = curr['stoch_k'] < 20
        stoch_ob = curr['stoch_k'] > 80
        kdj_gold = (prev['pk'] < prev['pd']) and (curr['pk'] > curr['pd'])
        kdj_dead = (prev['pk'] > prev['pd']) and (curr['pk'] < curr['pd'])
        smi_kdj_buy = stoch_os and kdj_gold
        smi_kdj_sell = stoch_ob and kdj_dead
        
        # 🔥 OBV-ADX 信号条件
        obv_buy = (curr['obv_minus'] >= 22) and (curr['obv_adx'] >= 22) and (curr['obv_plus'] <= 18)
        obv_sell = (curr['obv_plus'] >= 22) and (curr['obv_adx'] >= 22) and (curr['obv_minus'] <= 18)
        
        # 🔥 基础信号：KDJ + OBV 同时满足
        basic_buy_signal = smi_kdj_buy and obv_buy
        basic_sell_signal = smi_kdj_sell and obv_sell
        
        # 🔥 扩展信号逻辑（平衡模式）- 完全对齐TradingView逻辑
        # TradingView: 记录OBV信号出现的bar_index，当前bar与该bar距离 <= choose_bottom 时触发
        # Python: 向前回溯检查最近 choose_bottom+1 根K线内是否有OBV信号
        extended_buy_signal = False
        extended_sell_signal = False
        
        if self.more_bottom and len(df) >= 4:
            # 🔥 修复：TradingView的逻辑是 (bar_index - obv_buy_bar_bottom) <= choose_bottom
            # 这意味着：当前K线(bar_index) 与 OBV信号K线(obv_buy_bar_bottom) 的距离 <= choose_bottom
            # 距离为0表示同一根K线，距离为1表示相邻K线
            # 所以回溯范围是 [0, choose_bottom]，共 choose_bottom+1 根K线
            
            # 当前K线索引是 -2（00秒确认模式）
            # 回溯范围：当前K线(-2) 到 当前K线-choose_bottom(-2-choose_bottom)
            for lookback in range(0, self.choose_bottom + 1):  # 0 到 choose_bottom
                check_idx = -(2 + lookback)  # -2, -3, -4, ... 
                if len(df) >= abs(check_idx):
                    past = df.iloc[check_idx]
                    past_obv_buy = (past['obv_minus'] >= 22) and (past['obv_adx'] >= 22) and (past['obv_plus'] <= 18)
                    if past_obv_buy and smi_kdj_buy:
                        extended_buy_signal = True
                        break
            
            for lookback in range(0, self.choose_bottom + 1):
                check_idx = -(2 + lookback)
                if len(df) >= abs(check_idx):
                    past = df.iloc[check_idx]
                    past_obv_sell = (past['obv_plus'] >= 22) and (past['obv_adx'] >= 22) and (past['obv_minus'] <= 18)
                    if past_obv_sell and smi_kdj_sell:
                        extended_sell_signal = True
                        break
        
        # 🔥 组合信号：基础信号 OR 扩展信号
        bottom_buy = basic_buy_signal or extended_buy_signal
        bottom_sell = basic_sell_signal or extended_sell_signal
        
        # === 订单块信号检测 ===
        # 🔥 注意：订单块已经包含 ATR * 0.1 的扩展，不需要额外加 buffer
        ob_long_signal = False
        ob_short_signal = False
        
        # 查找最近的未失效订单块（向前回溯最多50根K线）
        for i in range(min(50, len(df) - 1), 0, -1):
            check_candle = df.iloc[-i]
            
            # 看涨订单块触发：当前价格回踩到订单块区域
            if check_candle.get('bullish_ob', False):
                ob_high = check_candle.get('ob_high', 0)
                ob_low = check_candle.get('ob_low', 0)
                
                # 🔥 触发条件：当前低点触及订单块区间 [无需额外buffer]
                if curr['low'] <= ob_high and curr['low'] >= ob_low:
                    # 确认订单块未失效（价格未跌破订单块低点）
                    if curr['close'] > ob_low:
                        ob_long_signal = True
                        break
            
            # 看跌订单块触发：当前价格反弹到订单块区域
            if check_candle.get('bearish_ob', False):
                ob_high = check_candle.get('ob_high', 0)
                ob_low = check_candle.get('ob_low', 0)
                
                # 🔥 触发条件：当前高点触及订单块区间
                if curr['high'] >= ob_low and curr['high'] <= ob_high:
                    # 确认订单块未失效（价格未突破订单块高点）
                    if curr['close'] < ob_high:
                        ob_short_signal = True
                        break
        
        # === 🔥 信号优先级判定（增强版：区分周期和订单块）===
        
        # 🔥 规则1：主信号使用 1m/3m/5m 的 Trend 2.3（1m替代15m）
        if timeframe in ['1m', '3m', '5m']:
            if trend_buy:
                return {
                    "action": "LONG",
                    "type": "MAIN_TREND",
                    "position_pct": self.main_signal_pct,
                    "leverage": 50,
                    "reason": f"[{timeframe}]趋势2.3主做多信号 | EMA12={curr['ema12']:.2f} | RSI={curr_rsi:.1f}"
                }
            elif trend_sell:
                return {
                    "action": "SHORT",
                    "type": "MAIN_TREND",
                    "position_pct": self.main_signal_pct,
                    "leverage": 50,
                    "reason": f"[{timeframe}]趋势2.3主做空信号 | EMA12={curr['ema12']:.2f} | RSI={curr_rsi:.1f}"
                }
        
        # 🔥 规则2：3m/5m/15m/30m/1h 的顶底信号可作为次信号开仓（1m顶底信号仅止盈）
        if timeframe in ['3m', '5m', '15m', '30m', '1h']:
            if bottom_buy:
                return {
                    "action": "LONG",
                    "type": "SUB_BOTTOM",
                    "position_pct": self.sub_signal_pct,
                    "leverage": 50,
                    "reason": f"[{timeframe}]何以为底抄底信号 | Stoch={curr['stoch_k']:.1f} | OBV_ADX={curr['obv_adx']:.1f}"
                }
            elif bottom_sell:
                return {
                    "action": "SHORT",
                    "type": "SUB_TOP",
                    "position_pct": self.sub_signal_pct,
                    "leverage": 50,
                    "reason": f"[{timeframe}]何以为底逃顶信号 | Stoch={curr['stoch_k']:.1f}"
                }
        
        # 🔥 规则3：1m 顶底信号仅用于止盈（不开仓）
        if timeframe == '1m':
            if bottom_buy:
                return {
                    "action": "LONG",
                    "type": "TP_BOTTOM",  # 🔥 特殊标记：止盈专用
                    "position_pct": 0,
                    "leverage": 0,
                    "reason": f"[{timeframe}]顶底止盈信号（仅平仓）"
                }
            elif bottom_sell:
                return {
                    "action": "SHORT",
                    "type": "TP_TOP",  # 🔥 特殊标记：止盈专用
                    "position_pct": 0,
                    "leverage": 0,
                    "reason": f"[{timeframe}]顶底止盈信号（仅平仓）"
                }
        
        # 🔥 规则4：30m/1h 订单块可用于开仓和加仓（次信号）
        if timeframe in ['30m', '1h']:
            if ob_long_signal:
                return {
                    "action": "LONG",
                    "type": "SUB_ORDER_BLOCK",
                    "position_pct": self.sub_signal_pct,
                    "leverage": 50,
                    "reason": f"[{timeframe}]SMC看涨订单块触发 | 触发价≈${curr['close']:.4f}"
                }
            elif ob_short_signal:
                return {
                    "action": "SHORT",
                    "type": "SUB_ORDER_BLOCK",
                    "position_pct": self.sub_signal_pct,
                    "leverage": 50,
                    "reason": f"[{timeframe}]SMC看跌订单块触发 | 触发价≈${curr['close']:.4f}"
                }
        
        # 🔥 规则5：1m/3m/5m/15m 订单块仅用于止盈/平仓信号（标记为特殊类型）
        if timeframe in ['1m', '3m', '5m', '15m']:
            if ob_long_signal:
                return {
                    "action": "LONG",
                    "type": "TP_ORDER_BLOCK",  # 🔥 特殊标记：止盈专用
                    "position_pct": 0,  # 🔥 不用于开新仓
                    "leverage": 0,
                    "reason": f"[{timeframe}]订单块止盈信号（仅平仓）"
                }
            elif ob_short_signal:
                return {
                    "action": "SHORT",
                    "type": "TP_ORDER_BLOCK",  # 🔥 特殊标记：止盈专用
                    "position_pct": 0,  # 🔥 不用于开新仓
                    "leverage": 0,
                    "reason": f"[{timeframe}]订单块止盈信号（仅平仓）"
                }
        
        return {
            "action": "HOLD",
            "type": "NONE",
            "reason": "无有效信号"
        }
    
    def risk_check(self, current_equity, current_position_notional, proposed_notional):
        """
        风控检查 - 使用名义价值 (Notional Value)
        
        🔥 重要修复：
        - 之前的 BUG：使用 max_total_position_pct * max_leverage 计算限额
          这会导致 10% × 50x = 500% 的限额，完全失效
        - 正确逻辑：总名义价值 <= 权益 × max_total_position_pct (10%)
        
        Args:
            current_equity: 当前账户权益
            current_position_notional: 当前持仓名义价值（不是保证金！）
            proposed_notional: 拟开仓的名义价值
        
        Returns:
            (bool, str): (是否通过, 原因)
        """
        new_total_notional = current_position_notional + proposed_notional
        # 🔥 修复：最大允许名义价值 = 权益 × 10%（不乘杠杆！）
        max_allowed_notional = current_equity * self.max_total_position_pct
        
        if new_total_notional > max_allowed_notional:
            return False, (
                f"风控拒绝: 持仓名义价值 {current_position_notional:.2f} + "
                f"拟开仓 {proposed_notional:.2f} = {new_total_notional:.2f} > "
                f"限额 {max_allowed_notional:.2f} (权益 {current_equity:.2f} × 10%)"
            )
        return True, "通过"
    
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
                "tf": "15m",
                "action": "LONG",
                "type": "BOTTOM_SIGNAL",
                "rsi": 28.5,
                "signal": {...},
                "reason": "何以为底+震荡金叉",
                "candle_time": Timestamp(...)
            },
            ...
        ]
        """
        scan_results = []
        
        for tf in due_tfs:
            # 使用预加载的数据
            df = preloaded_data.get(tf)
            
            if df is None or len(df) < 200:
                scan_results.append({
                    "tf": tf,
                    "action": "ERROR",
                    "type": "DATA_ERROR",
                    "rsi": 50.0,
                    "signal": None,
                    "reason": "数据不足",
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
                
                # 🔥 获取K线时间戳（使用已收盘的K线，与信号计算一致）
                # 因为信号是基于 df.iloc[-2] 计算的（00秒确认模式），所以去重也用 df.iloc[-2] 的时间戳
                candle_time = None
                if len(df_with_indicators) >= 2:
                    candle_time = df_with_indicators.iloc[-2]['timestamp']
                
                scan_results.append({
                    "tf": tf,
                    "action": sig['action'],
                    "type": sig['type'],
                    "rsi": rsi_val,
                    "signal": sig,
                    "reason": sig['reason'],
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


# 全局实例
strategy_engine = TradingStrategy()