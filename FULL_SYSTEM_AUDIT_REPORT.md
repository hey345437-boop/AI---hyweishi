# 量化交易系统端到端审计报告

**审计日期**: 2024-12-16  
**审计范围**: 前端UI、后端引擎、交易接入、配置存储、部署运行  
**审计目标**: 端到端可运行性 + 交易风险评估

---

## D) 结论总览

| 项目 | 结论 | 判定依据 |
|------|------|---------|
| **端到端是否可运行** | ✅ 可运行（有条件） | 需配置API密钥、启动后端runner |
| **当前默认运行模式** | `sim`（模拟） | `config.py:28` `RUN_MODE = os.getenv("RUN_MODE", "sim")` |
| **交易品种** | 永续合约 (swap) | `config.py:27` `OKX_MARKET_TYPE = "swap"` |
| **仓位模式** | 双向持仓 (long/short) | `okx_adapter.py:470` `ensure_position_mode(hedged=True)` |
| **保证金模式** | 全仓 (cross) | `config.py:26` `OKX_TD_MODE = "cross"` |

### 阻断点列表（若不满足则无法运行）

1. **P0-阻断**: 未配置 `OKX_API_KEY/SECRET/PASSPHRASE` 时，交易所连接失败
2. **P0-阻断**: 后端 `separated_system/trade_engine.py` 未启动时，UI显示"后端未运行"
3. **P1-阻断**: 数据库文件损坏或被锁定时，`init_db()` 失败

---

## A) 端到端可运行性审计

### A1. 启动链路梳理

```
入口文件:
├── 前端: app.py → ui_legacy.py (Streamlit UI)
├── 后端: separated_system/trade_engine.py (24h常驻)
└── 启动脚本: start.sh / 启动测试.bat
```

**所需环境变量** (`config.py` + `.env.example`):
