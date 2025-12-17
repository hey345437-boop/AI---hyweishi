"""
策略创建指南 (HOWTO)

快速开始：复制 strategy_template 目录并按照以下步骤修改

## 1. 修改 manifest.json

{
  "strategy_id": "my_strategy_01",          // 唯一标识符，英文下划线分隔（必填）
  "display_name": "我的策略 v1",            // UI 中显示的名称（必填）
  "version": "1.0.0",                       // 版本号（推荐）
  "description": "基于 MACD 的趋势策略",    // 策略描述
  "author": "Your Name",                    // 作者名称（可选）
  "class_name": "MyStrategy",               // Python 类名（必填）
  "order": 100                              // 在下拉菜单中的排序，越小越靠前（可选，默认 999）
}

## 2. 修改 __init__.py

继承 TemplateStrategy 或直接实现相同接口：
- __init__(): 初始化参数
- analyze(df): 输入 OHLCV DataFrame，返回 {'signal', 'confidence', 'entry_price', 'stop_loss', 'take_profit', 'reason'}
- get_position_size(symbol, balance, leverage=1.0): 计算仓位

## 3. 文件结构

strategies/
└── my_strategy_01/          // 目录名称建议与 strategy_id 相同
    ├── manifest.json        // 元数据（必填）
    ├── __init__.py          // 策略实现（必填，导出策略类）
    ├── config.yaml          // 可选：策略配置文件
    ├── README.md            // 可选：策略说明文档
    └── utils.py             // 可选：辅助函数

## 4. 约定与建议

- strategy_id 必须唯一，建议使用英文和下划线，如 strategy_v1, my_strategy_rsi_bb
- display_name 可使用中文和 emoji，如 "RSI+BB 策略 📊"
- 策略类必须实现上述三个方法，否则会导致运行时错误
- analyze() 必须返回 dict，包含 'signal' 和 'confidence' 字段（其他字段可选）
- 确保代码中不要硬编码 API 密钥或敏感信息，用环境变量代替

## 5. 调试

重启应用后，新策略会自动在 UI 下拉菜单出现。
如果看不到，检查：
1. manifest.json 格式是否正确（JSON 语法错误）
2. 类名是否与 manifest.json 中的 class_name 匹配
3. __init__.py 是否存在且可以导入
4. 查看应用日志中是否有错误信息

## 6. 示例：简单 RSI 策略

# strategies/my_rsi_strategy/__init__.py

from __init__ import TemplateStrategy
import pandas as pd

class RSIStrategy(TemplateStrategy):
    def __init__(self):
        super().__init__()
        self.rsi_period = 14
        self.overbought = 70
        self.oversold = 30
    
    def analyze(self, df: pd.DataFrame) -> dict:
        if len(df) < self.rsi_period:
            return {'signal': 'HOLD', 'confidence': 0, ...}
        
        # 计算 RSI
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=self.rsi_period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=self.rsi_period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        
        latest_rsi = rsi.iloc[-1]
        signal = 'HOLD'
        reason = f'RSI: {latest_rsi:.2f}'
        
        if latest_rsi < self.oversold:
            signal = 'BUY'
        elif latest_rsi > self.overbought:
            signal = 'SELL'
        
        return {
            'signal': signal,
            'confidence': abs(latest_rsi - 50) / 50,  // 越极端越有信心
            'entry_price': df['close'].iloc[-1],
            'reason': reason
        }

# manifest.json
{
  "strategy_id": "my_rsi_strategy",
  "display_name": "RSI 超买超卖 📊",
  "version": "1.0.0",
  "class_name": "RSIStrategy",
  "order": 50
}

"""
