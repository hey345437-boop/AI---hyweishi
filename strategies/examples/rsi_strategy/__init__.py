# -*- coding: utf-8 -*-
"""
RSI 超买超卖策略 - 示例

简单的 RSI 策略：
- RSI < 30 做多
- RSI > 70 做空
- 其他情况观望

这是一个教学示例，实盘效果一般，建议结合其他指标使用。
"""


class RSIStrategy:
    """RSI 超买超卖策略"""
    
    def __init__(self, config=None):
        config = config or {}
        self.oversold = config.get("oversold", 30)
        self.overbought = config.get("overbought", 70)
        self.stop_loss_pct = config.get("stop_loss_pct", 2.0)
        self.take_profit_pct = config.get("take_profit_pct", 4.0)
    
    def analyze(self, ohlcv, indicators):
        """
        分析市场，返回交易信号
        
        Args:
            ohlcv: K 线数据 [[ts, o, h, l, c, v], ...]
            indicators: 技术指标 {"rsi": 45.0, "atr": 500.0, ...}
        
        Returns:
            dict: 信号和参数
        """
        rsi = indicators.get("rsi", 50)
        current_price = ohlcv[-1][4] if ohlcv else 0
        
        result = {
            "signal": "neutral",
            "confidence": 50,
            "stop_loss": None,
            "take_profit": None,
            "reason": ""
        }
        
        if rsi < self.oversold:
            result["signal"] = "long"
            result["confidence"] = min(90, 50 + (self.oversold - rsi) * 2)
            result["stop_loss"] = current_price * (1 - self.stop_loss_pct / 100)
            result["take_profit"] = current_price * (1 + self.take_profit_pct / 100)
            result["reason"] = f"RSI={rsi:.1f} 超卖"
        
        elif rsi > self.overbought:
            result["signal"] = "short"
            result["confidence"] = min(90, 50 + (rsi - self.overbought) * 2)
            result["stop_loss"] = current_price * (1 + self.stop_loss_pct / 100)
            result["take_profit"] = current_price * (1 - self.take_profit_pct / 100)
            result["reason"] = f"RSI={rsi:.1f} 超买"
        
        else:
            result["reason"] = f"RSI={rsi:.1f} 中性区间"
        
        return result
