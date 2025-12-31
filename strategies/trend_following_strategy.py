# -*- coding: utf-8 -*-
"""
趋势跟随 + 震荡过滤 + 动态风控策略

适用于：BTCUSDT/ETHUSDT 永续合约
周期：15m / 1h

⚠️ 风险提示：
- 本策略仅供学习和研究使用
- 加密货币交易存在高风险，可能导致全部本金损失
- 过去的表现不代表未来收益
- 请根据自身风险承受能力谨慎决策

入场条件（必须同时满足）：
做多：
  - EMA12 上穿 EMA26（黄金交叉）
  - 收盘价在 EMA200 之上（顺大趋势）
  - RSI(14) 在 45-70 之间（避免超买和过弱）
  - 成交量 > VOL_SMA(20) * 1.2（过滤假突破）

做空：
  - EMA12 下穿 EMA26（死亡交叉）
  - 收盘价在 EMA200 之下
  - RSI(14) 在 30-55 之间
  - 成交量 > VOL_SMA(20) * 1.2

止损止盈：
  - 初始止损：ATR * 2.2
  - TP1：+1R 平 30%
  - TP2：+2R 平 30%
  - TP3：剩余 40% 用 ATR*2 追踪止损
"""
import numpy as np
from typing import Dict, Any, Optional
from datetime import datetime

# 导入基类
try:
    from strategies.advanced_strategy_template import (
        AdvancedStrategyBase, PositionSide, RiskConfig
    )
except ImportError:
    from advanced_strategy_template import (
        AdvancedStrategyBase, PositionSide, RiskConfig
    )

# 尝试导入加速指标
try:
    from ai_indicators import calc_ema, calc_rsi, calc_atr
    USE_ACCELERATED = True
except ImportError:
    import pandas_ta as ta
    USE_ACCELERATED = False


class TrendFollowingStrategy(AdvancedStrategyBase):
    """
    趋势跟随策略
    
    继承自 AdvancedStrategyBase，自动获得：
    - 动态 ATR 止损
    - 分批止盈 (TP1/TP2/TP3)
    - 追踪止损
    - 时间过滤
    - 新闻过滤
    - 防抖机制
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        
        # 策略特定参数（可通过 config 覆盖）
        self.ema_fast = config.get('ema_fast', 12) if config else 12
        self.ema_slow = config.get('ema_slow', 26) if config else 26
        self.ema_trend = config.get('ema_trend', 200) if config else 200
        self.rsi_period = config.get('rsi_period', 14) if config else 14
        self.vol_sma_period = config.get('vol_sma_period', 20) if config else 20
        
        # RSI 区间
        self.rsi_long_min = config.get('rsi_long_min', 45) if config else 45
        self.rsi_long_max = config.get('rsi_long_max', 70) if config else 70
        self.rsi_short_min = config.get('rsi_short_min', 30) if config else 30
        self.rsi_short_max = config.get('rsi_short_max', 55) if config else 55
        
        # 成交量倍数
        self.volume_multiplier = config.get('volume_multiplier', 1.2) if config else 1.2
        
        # 上一根 K 线的 EMA 值（用于检测交叉）
        self._prev_ema_fast = None
        self._prev_ema_slow = None
    
    def _calculate_indicators(self, ohlcv) -> Dict[str, np.ndarray]:
        """计算策略所需的技术指标"""
        close = ohlcv['close'].values if hasattr(ohlcv['close'], 'values') else np.array(ohlcv['close'])
        high = ohlcv['high'].values if hasattr(ohlcv['high'], 'values') else np.array(ohlcv['high'])
        low = ohlcv['low'].values if hasattr(ohlcv['low'], 'values') else np.array(ohlcv['low'])
        volume = ohlcv['volume'].values if hasattr(ohlcv['volume'], 'values') else np.array(ohlcv['volume'])
        
        if USE_ACCELERATED:
            ema_fast = calc_ema(close, self.ema_fast)
            ema_slow = calc_ema(close, self.ema_slow)
            ema_trend = calc_ema(close, self.ema_trend)
            rsi = calc_rsi(close, self.rsi_period)
            atr = calc_atr(high, low, close, 14)
        else:
            ema_fast = ta.ema(ohlcv['close'], length=self.ema_fast).values
            ema_slow = ta.ema(ohlcv['close'], length=self.ema_slow).values
            ema_trend = ta.ema(ohlcv['close'], length=self.ema_trend).values
            rsi = ta.rsi(ohlcv['close'], length=self.rsi_period).values
            atr_df = ta.atr(ohlcv['high'], ohlcv['low'], ohlcv['close'], length=14)
            atr = atr_df.values if atr_df is not None else np.zeros(len(close))
        
        # 成交量均线
        vol_sma = np.convolve(volume, np.ones(self.vol_sma_period)/self.vol_sma_period, mode='same')
        
        return {
            'close': close,
            'high': high,
            'low': low,
            'volume': volume,
            'ema_fast': ema_fast,
            'ema_slow': ema_slow,
            'ema_trend': ema_trend,
            'rsi': rsi,
            'atr': atr,
            'vol_sma': vol_sma,
        }
    
    def check_entry_signal(self, indicators: Dict[str, np.ndarray], bar_index: int) -> Optional[PositionSide]:
        """
        检查入场信号
        
        做多条件：
        1. EMA12 上穿 EMA26（黄金交叉）
        2. 收盘价 > EMA200
        3. RSI 在 45-70 之间
        4. 成交量 > VOL_SMA * 1.2
        
        做空条件：
        1. EMA12 下穿 EMA26（死亡交叉）
        2. 收盘价 < EMA200
        3. RSI 在 30-55 之间
        4. 成交量 > VOL_SMA * 1.2
        """
        # 获取当前和前一根 K 线的值
        ema_fast_now = indicators['ema_fast'][-1]
        ema_slow_now = indicators['ema_slow'][-1]
        ema_fast_prev = indicators['ema_fast'][-2]
        ema_slow_prev = indicators['ema_slow'][-2]
        
        close_now = indicators['close'][-1]
        ema_trend_now = indicators['ema_trend'][-1]
        rsi_now = indicators['rsi'][-1]
        volume_now = indicators['volume'][-1]
        vol_sma_now = indicators['vol_sma'][-1]
        
        # 检查 NaN
        if np.isnan(ema_fast_now) or np.isnan(ema_slow_now) or np.isnan(rsi_now):
            return None
        
        # 成交量过滤
        volume_ok = volume_now > vol_sma_now * self.volume_multiplier
        
        # === 做多信号 ===
        # 1. 金叉：EMA12 从下方穿越 EMA26
        golden_cross = (ema_fast_prev <= ema_slow_prev) and (ema_fast_now > ema_slow_now)
        
        # 2. 趋势过滤：收盘价在 EMA200 之上
        above_trend = close_now > ema_trend_now
        
        # 3. RSI 过滤：45-70 之间
        rsi_long_ok = self.rsi_long_min <= rsi_now <= self.rsi_long_max
        
        if golden_cross and above_trend and rsi_long_ok and volume_ok:
            return PositionSide.LONG
        
        # === 做空信号 ===
        # 1. 死叉：EMA12 从上方穿越 EMA26
        death_cross = (ema_fast_prev >= ema_slow_prev) and (ema_fast_now < ema_slow_now)
        
        # 2. 趋势过滤：收盘价在 EMA200 之下
        below_trend = close_now < ema_trend_now
        
        # 3. RSI 过滤：30-55 之间
        rsi_short_ok = self.rsi_short_min <= rsi_now <= self.rsi_short_max
        
        if death_cross and below_trend and rsi_short_ok and volume_ok:
            return PositionSide.SHORT
        
        return None
    
    def check_exit_signal(self, indicators: Dict[str, np.ndarray], bar_index: int) -> bool:
        """
        检查反向信号平仓
        
        出现反向 EMA12/EMA26 交叉时，立即平仓
        """
        ema_fast_now = indicators['ema_fast'][-1]
        ema_slow_now = indicators['ema_slow'][-1]
        ema_fast_prev = indicators['ema_fast'][-2]
        ema_slow_prev = indicators['ema_slow'][-2]
        
        if self.position.side == PositionSide.LONG:
            # 持多仓时，出现死叉则平仓
            death_cross = (ema_fast_prev >= ema_slow_prev) and (ema_fast_now < ema_slow_now)
            return death_cross
        
        elif self.position.side == PositionSide.SHORT:
            # 持空仓时，出现金叉则平仓
            golden_cross = (ema_fast_prev <= ema_slow_prev) and (ema_fast_now > ema_slow_now)
            return golden_cross
        
        return False
    
    def get_config_schema(self) -> Dict[str, Any]:
        """返回配置参数 schema（包含基类参数 + 策略特定参数）"""
        schema = super().get_config_schema()
        
        # 添加策略特定参数
        schema.update({
            "ema_fast": {
                "type": "int",
                "label": "快速EMA周期",
                "default": 12,
                "min": 5,
                "max": 50,
                "description": "快速EMA周期"
            },
            "ema_slow": {
                "type": "int",
                "label": "慢速EMA周期",
                "default": 26,
                "min": 10,
                "max": 100,
                "description": "慢速EMA周期"
            },
            "ema_trend": {
                "type": "int",
                "label": "趋势EMA周期",
                "default": 200,
                "min": 50,
                "max": 500,
                "description": "趋势判断EMA周期"
            },
            "rsi_long_min": {
                "type": "int",
                "label": "做多RSI下限",
                "default": 45,
                "min": 20,
                "max": 60,
                "description": "做多时RSI最小值"
            },
            "rsi_long_max": {
                "type": "int",
                "label": "做多RSI上限",
                "default": 70,
                "min": 50,
                "max": 80,
                "description": "做多时RSI最大值"
            },
            "rsi_short_min": {
                "type": "int",
                "label": "做空RSI下限",
                "default": 30,
                "min": 20,
                "max": 50,
                "description": "做空时RSI最小值"
            },
            "rsi_short_max": {
                "type": "int",
                "label": "做空RSI上限",
                "default": 55,
                "min": 40,
                "max": 80,
                "description": "做空时RSI最大值"
            },
            "volume_multiplier": {
                "type": "float",
                "label": "成交量倍数",
                "default": 1.2,
                "min": 1.0,
                "max": 2.0,
                "step": 0.1,
                "description": "成交量需大于均线的倍数"
            },
        })
        
        return schema


# 兼容传统引擎的包装类
class TrendFollowingStrategyWrapper:
    """
    包装类 - 兼容传统交易引擎格式
    
    传统引擎期望的接口：
    - __init__(config=None)
    - analyze(ohlcv, symbol, timeframe) -> {"action": "LONG/SHORT/HOLD", ...}
    """
    
    def __init__(self, config=None):
        self.strategy = TrendFollowingStrategy(config)
        self.config = config or {}
        
        # 兼容旧格式
        self.position_pct = self.config.get('position_pct', 2.0)
        self.leverage = self.config.get('leverage', 5)
    
    def analyze(self, ohlcv, symbol: str, timeframe: str = '15m') -> Dict[str, Any]:
        """分析并返回交易信号"""
        result = self.strategy.analyze(ohlcv, symbol, timeframe)
        
        # 添加兼容字段
        result['position_pct'] = self.position_pct
        result['leverage'] = self.leverage
        
        return result
    
    def set_news_filter(self, filter_func):
        """设置新闻过滤函数"""
        self.strategy.set_news_filter(filter_func)
    
    def set_equity(self, equity: float):
        """更新账户权益"""
        self.strategy.set_equity(equity)
    
    def get_position_info(self) -> Dict[str, Any]:
        """获取持仓信息"""
        return self.strategy.get_position_info()
    
    def get_config_schema(self) -> Dict[str, Any]:
        """获取配置 schema"""
        return self.strategy.get_config_schema()


# 导出
__all__ = ['TrendFollowingStrategy', 'TrendFollowingStrategyWrapper']
