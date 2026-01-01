# API 参考

## 核心模块

### 风控 (`core.risk_control`)

```python
from core.risk_control import RiskControlModule, RiskControlConfig

# 创建风控模块
config = RiskControlConfig(
    max_order_size=1000.0,      # 单笔最大 USDT
    daily_loss_limit_pct=0.10   # 日损失限制 10%
)
risk = RiskControlModule(config)

# 验证订单
result = risk.validate_order(amount=500.0, symbol="BTC/USDT")
if not result.is_valid:
    print(f"拒绝: {result.error_message}")

# 记录盈亏
risk.record_trade_pnl(-50.0)  # 亏损 50

# 检查是否可以继续交易
can_trade, reason = risk.can_trade(equity=1000.0)
```

### 策略注册表 (`strategies.strategy_registry`)

```python
from strategies.strategy_registry import (
    get_strategy_registry,
    list_all_strategies,
    validate_and_fallback_strategy
)

# 获取所有策略
strategies = list_all_strategies()
# [("📈 趋势策略 v1", "strategy_v1"), ("📈 趋势策略 v2", "strategy_v2"), ...]

# 加载策略类
registry = get_strategy_registry()
strategy_class = registry.get_strategy_class("strategy_v2")
strategy = strategy_class()

# 验证策略 ID
strategy_id = validate_and_fallback_strategy("invalid")  # 抛出 ValueError
strategy_id = validate_and_fallback_strategy(None)       # 返回默认 "strategy_v2"
```

### AI 服务商 (`ai.ai_providers`)

```python
from ai.ai_providers import (
    UniversalAIClient,
    get_available_providers,
    get_free_models,
    verify_api_key_sync
)

# 查看支持的服务商
providers = get_available_providers()
# {'deepseek': AIProvider(...), 'qwen': AIProvider(...), ...}

# 获取免费模型
free = get_free_models()
# [('spark', AIModel('lite', ...)), ('glm', AIModel('glm-4-flash', ...)), ...]

# 验证 API Key
valid, msg = verify_api_key_sync("deepseek", "sk-xxx")

# 调用 AI
client = UniversalAIClient("deepseek", "sk-xxx", model_id="deepseek-chat")
response = client.chat("分析 BTC 走势", system_prompt="你是交易分析师")
```

### 交易所适配器 (`exchange_adapters.okx_adapter`)

```python
from exchange_adapters.okx_adapter import OKXAdapter

adapter = OKXAdapter({
    "api_key": "xxx",
    "api_secret": "xxx",
    "api_passphrase": "xxx",
    "run_mode": "paper"  # paper=模拟, live=实盘
})
adapter.initialize()

# 获取 K 线
ohlcv = adapter.fetch_ohlcv("BTC/USDT", timeframe="1h", limit=100)

# 获取余额
balance = adapter.fetch_balance()

# 下单（paper 模式会本地模拟）
order = adapter.create_order("BTC/USDT", "buy", amount=0.01)
```

## 情绪分析 (`sentiment`)

```python
from sentiment import (
    get_fear_greed_index,
    get_latest_news,
    get_market_impact,
    get_liquidation_data,
    get_whale_data
)

# 恐惧贪婪指数
fg = get_fear_greed_index()
# {"value": 45, "classification": "Fear", ...}

# 最新新闻
news = get_latest_news(limit=10)
# [{"title": "...", "sentiment_score": 30, "impact": "high", ...}, ...]

# 综合市场影响
impact = get_market_impact()
# {"combined_score": 20, "combined_bias": "bullish", ...}

# 多空比
liq = get_liquidation_data()
# {"btc": {"long_ratio": 0.55, ...}, "bias": "bearish", ...}

# 巨鲸转账
whale = get_whale_data()
# {"count": 5, "total_usd": 50000000, "recent_transfers": [...], ...}
```
