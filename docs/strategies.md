# 策略开发

## 内置策略

| ID | 名称 | 说明 |
|----|------|------|
| `strategy_v1` | 趋势策略 v1 | 双 MACD + 顶底系统 + SMC |
| `strategy_v2` | 趋势策略 v2 | 综合策略，默认选项 |
| `strategy_v3` | 实时策略 v3 | 布林带突破 + ADX，不等 K 线收盘 |

## 自定义策略

### 目录结构

```
strategies/
└── my_strategy/
    ├── __init__.py      # 策略代码
    └── manifest.json    # 元数据
```

### manifest.json

```json
{
  "strategy_id": "my_strategy",
  "display_name": "我的策略",
  "class_name": "MyStrategy",
  "description": "策略描述",
  "version": "1.0.0",
  "order": 100,
  "default_params": {
    "position_pct": 2.0,
    "leverage": 10,
    "stop_loss_pct": 2.0,
    "take_profit_pct": 6.0
  }
}
```

### 策略类

```python
# strategies/my_strategy/__init__.py

class MyStrategy:
    """自定义策略示例"""
    
    def __init__(self, config=None):
        self.config = config or {}
    
    def analyze(self, ohlcv, indicators):
        """
        分析市场数据，返回信号
        
        Args:
            ohlcv: K 线数据 [[ts, o, h, l, c, v], ...]
            indicators: 技术指标字典
        
        Returns:
            dict: {
                "signal": "long" | "short" | "neutral",
                "confidence": 0-100,
                "stop_loss": float,
                "take_profit": float
            }
        """
        closes = [c[4] for c in ohlcv]
        rsi = indicators.get("rsi", 50)
        
        if rsi < 30:
            return {"signal": "long", "confidence": 70}
        elif rsi > 70:
            return {"signal": "short", "confidence": 70}
        
        return {"signal": "neutral", "confidence": 50}
```

### 注册策略

策略放到 `strategies/` 目录后自动注册，重启应用即可在 UI 中选择。

## Pine Script 转换

支持将 TradingView Pine Script 转换为 Python：

```python
from strategies.pine_converter import convert_pine_to_python

pine_code = """
//@version=5
strategy("My Strategy")
fast = ta.sma(close, 10)
slow = ta.sma(close, 20)
if ta.crossover(fast, slow)
    strategy.entry("Long", strategy.long)
"""

python_code = convert_pine_to_python(pine_code)
```

注意：转换器支持常用语法，复杂脚本可能需要手动调整。
