# 架构设计

## 整体结构

```
┌─────────────────────────────────────────────────────────┐
│                    Streamlit UI                         │
│                    (ui/*.py)                            │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐     │
│  │  AI Brain   │  │  Strategies │  │  Sentiment  │     │
│  │  (ai/)      │  │ (strategies)│  │ (sentiment/)│     │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘     │
│         │                │                │             │
│         └────────────────┼────────────────┘             │
│                          ▼                              │
│              ┌───────────────────────┐                  │
│              │     Trade Engine      │                  │
│              │   (core/trade_engine) │                  │
│              └───────────┬───────────┘                  │
│                          │                              │
│         ┌────────────────┼────────────────┐             │
│         ▼                ▼                ▼             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐     │
│  │ Risk Control│  │  Database   │  │  Exchange   │     │
│  │   (core/)   │  │ (database/) │  │  Adapters   │     │
│  └─────────────┘  └─────────────┘  └─────────────┘     │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

## 核心模块

### AI 决策 (`ai/`)

| 文件 | 职责 |
|------|------|
| `ai_brain.py` | 多模型决策引擎，僧侣型交易员 Prompt |
| `ai_providers.py` | 12+ AI 服务商统一适配 |
| `arena_scheduler.py` | 竞技场调度器 |

### 策略系统 (`strategies/`)

| 文件 | 职责 |
|------|------|
| `strategy_registry.py` | 策略注册表，动态加载 |
| `strategy_v1.py` | 趋势策略 v1 |
| `strategy_v2.py` | 趋势策略 v2 |
| `pine_converter.py` | TradingView Pine 转 Python |

### 风控 (`core/`)

| 文件 | 职责 |
|------|------|
| `risk_control.py` | 订单验证、日损失限制 |
| `trade_engine.py` | 交易执行引擎 |
| `simulated_account.py` | 模拟账户 |

### 交易所适配 (`exchange_adapters/`)

| 文件 | 职责 |
|------|------|
| `okx_adapter.py` | OKX 适配器，live/paper 双模式 |
| `base.py` | 适配器基类 |

## 数据流

```
市场数据 → 策略信号 → AI 决策 → 风控检查 → 下单执行
    ↑                                          │
    └──────────── 持仓/余额更新 ←───────────────┘
```

## 扩展点

1. **添加策略** - 在 `strategies/` 下创建目录，写 `manifest.json` + `__init__.py`
2. **添加 AI 服务商** - 在 `ai/ai_providers.py` 的 `AI_PROVIDERS` 字典里加
3. **添加交易所** - 继承 `exchange_adapters/base.py` 的 `ExchangeAdapter`
