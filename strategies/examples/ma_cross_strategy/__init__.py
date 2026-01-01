# -*- coding: utf-8 -*-
"""
均线交叉策略 - 示例

经典的双均线策略：
- 快线上穿慢线做多
- 快线下穿慢线做空

参数可调，默认 EMA(12) 和 EMA(26)。
"""


class MACrossStrategy:
    """均线交叉策略"""
    
    def __init__(self, config=None):
        config = config or {}
        self.fast_period = config.get("fast_period", 12)
        self.slow_period = config.get("slow_period", 26)
        self.stop_loss_pct = config.get("stop_loss_pct", 1.5)
        self.take_profit_pct = config.get("take_profit_pct", 3.0)
        
        # 上一次的均线状态，用于判断交叉
        self._prev_fast = None
        self._prev_slow = None
    
    def analyze(self, ohlcv, indicators):
        """分析市场，返回交易信号"""
        
        # 从 indicators 获取均线，或者自己算
        fast_ma = indicators.get(f"ema_{self.fast_period}")
        slow_ma = indicators.get(f"ema_{self.slow_period}")
        
        # 如果没有预计算的均线，自己算
        if fast_ma is None or slow_ma is None:
            closes = [c[4] for c in ohlcv]
            fast_ma = self._ema(closes, self.fast_period)
            slow_ma = self._ema(closes, self.slow_period)
        
        current_price = ohlcv[-1][4] if ohlcv else 0
        
        result = {
            "signal": "neutral",
            "confidence": 50,
            "stop_loss": None,
            "take_profit": None,
            "reason": ""
        }
        
        # 判断交叉
        if self._prev_fast is not None and self._prev_slow is not None:
            # 金叉：快线从下方穿过慢线
            if self._prev_fast <= self._prev_slow and fast_ma > slow_ma:
                result["signal"] = "long"
                result["confidence"] = 75
                result["stop_loss"] = current_price * (1 - self.stop_loss_pct / 100)
                result["take_profit"] = current_price * (1 + self.take_profit_pct / 100)
                result["reason"] = f"EMA({self.fast_period}) 金叉 EMA({self.slow_period})"
            
            # 死叉：快线从上方穿过慢线
            elif self._prev_fast >= self._prev_slow and fast_ma < slow_ma:
                result["signal"] = "short"
                result["confidence"] = 75
                result["stop_loss"] = current_price * (1 + self.stop_loss_pct / 100)
                result["take_profit"] = current_price * (1 - self.take_profit_pct / 100)
                result["reason"] = f"EMA({self.fast_period}) 死叉 EMA({self.slow_period})"
            
            else:
                trend = "多头" if fast_ma > slow_ma else "空头"
                result["reason"] = f"趋势延续 ({trend})"
        
        # 更新状态
        self._prev_fast = fast_ma
        self._prev_slow = slow_ma
        
        return result
    
    def _ema(self, data, period):
        """计算 EMA"""
        if len(data) < period:
            return data[-1] if data else 0
        
        multiplier = 2 / (period + 1)
        ema = sum(data[:period]) / period
        
        for price in data[period:]:
            ema = (price - ema) * multiplier + ema
        
        return ema
