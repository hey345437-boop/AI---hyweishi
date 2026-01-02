# (・ω・) 何以为势 (HyWeiShi)

<div align="center">

<img src="https://img.shields.io/badge/AI-Powered-blueviolet?style=for-the-badge&logo=openai&logoColor=white" alt="AI Powered"/>
<img src="https://img.shields.io/badge/Crypto-Futures-orange?style=for-the-badge&logo=bitcoin&logoColor=white" alt="Crypto Futures"/>
<img src="https://img.shields.io/badge/Trading-Bot-success?style=for-the-badge&logo=robot&logoColor=white" alt="Trading Bot"/>

<br/><br/>

```
 _   ___   ____        _______ ___ ____  _   _ ___ 
| | | \ \ / /\ \      / / ____|_ _/ ___|| | | |_ _|
| |_| |\ V /  \ \ /\ / /|  _|  | |\___ \| |_| || | 
|  _  | | |    \ V  V / | |___ | | ___) |  _  || | 
|_| |_| |_|     \_/\_/  |_____|___|____/|_| |_|___|
```

**(*≧▽≦) AI 驱动的加密货币合约交易引擎**

*让 AI 成为你的交易搭档，洞察市场先机*

<br/>

[![License: AGPL-3.0](https://img.shields.io/badge/License-AGPL%203.0-blue.svg?style=flat-square)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/Python-3.9+-3776AB.svg?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.28+-FF4B4B.svg?style=flat-square&logo=streamlit&logoColor=white)](https://streamlit.io/)
[![OKX](https://img.shields.io/badge/OKX-Supported-000000.svg?style=flat-square)](https://www.okx.com/)

<br/>

[中文文档](#功能特性) | [English](README.en.md) | [日本語](README.ja.md) | [한국어](README.ko.md) | [快速开始](#快速开始) | [AI 模型](#支持的-ai-模型)

</div>

<br/>

---

## 风险声明

**本项目仅供学习研究，不构成投资建议。**

- 自动交易存在技术故障、API 失败、网络延迟等风险
- 历史回测不代表未来收益，策略可能在实盘中失效
- 请勿使用超出承受能力的资金
- 作者不对任何交易损失负责

**使用本软件即表示您已理解并接受上述风险。**

---

## 功能特性

### (￣▽￣) AI 智能决策
- **12+ AI 服务商** - DeepSeek、通义千问、GPT-5、Claude 4.5、Gemini 3 等最新模型
- **AI 竞技场** - 多个 AI 模型同时分析，投票决策，提高准确率
- **5 种交易人设** - 猎人型、均衡型、僧侣型、闪电型、冲浪型，适应不同风格
- **自定义提示词** - 完全自定义 AI 人设和交易策略，打造专属交易员
- **智能新闻分析** - AI 自动解读市场新闻，生成交易信号

### (◎_◎) 技术分析
- **多时间周期** - 支持 1m/5m/15m/1h/4h/1d 等多周期分析
- **丰富指标** - MA/EMA/RSI/MACD/KDJ/BOLL/ATR/OBV/VWAP 等
- **变化量追踪** - 指标变化趋势可视化，AI 更好理解市场动态
- **双通道信号** - 多时间周期信号确认机制

### (￥ω￥) 交易功能
- **OKX 合约交易** - 深度集成 OKX 永续合约 API
- **模拟交易** - Paper Trading 模式，零风险测试策略
- **风控系统** - 止损止盈、仓位管理、每日亏损限制
- **多策略支持** - 内置策略 + 自定义策略开发
- **限价单支持** - 支持限价挂单，可设置价格偏移和超时时间
- **更多交易所** - 后续将支持 Binance、Bybit 等主流交易所

---

## 完整交易功能

### 支持资产
BTC、ETH、SOL、BNB、XRP、DOGE、GT、TRUMP、ADA、WLFI 等主流币种，可在界面自由配置交易池。

### 合约类型
- **USDT 永续合约** - 以 USDT 结算的永续合约
- **双向持仓模式** - 支持同时持有多空仓位

### 持仓模式
| 模式 | 说明 | 适用场景 |
|------|------|----------|
| 全仓 (Cross) | 所有仓位共享保证金，风险共担 | 资金利用率高，适合有经验的交易者 |
| 逐仓 (Isolated) | 每个仓位独立保证金，风险隔离 | 单仓爆仓不影响其他，适合风险控制 |

### 杠杆范围
- **可配置范围**: 1x ~ 50x（界面可调）
- **推荐设置**: 5x ~ 20x（平衡风险与收益）
- **高波动自动降杠杆**: 高级策略支持根据 ATR 自动调整

### 订单类型
| 类型 | 说明 | 状态 |
|------|------|------|
| 市价单 | 立即成交，按当前市场价格 | ✅ 已支持 |
| 止损单 | 价格触发后自动平仓 | ✅ 已支持 |
| 止盈单 | 盈利达标后自动平仓 | ✅ 已支持 |
| 限价单 | 挂单等待指定价格成交 | ✅ 已支持 |

### 风控系统
- **单笔限额**: 单笔订单最大金额限制
- **最大仓位**: 总仓位不超过账户权益的指定比例
- **每日亏损限制**: 当日亏损达到阈值自动停止交易
- **冷却时间**: 止损后禁止同方向开仓一段时间

---

## 实时监控

### Web 仪表盘
- **账户概览**: 权益、可用余额、已用保证金
- **持仓监控**: 实时盈亏、杠杆、强平价格
- **K线图表**: 多周期 K 线 + 技术指标叠加

### AI 决策日志
- **推理过程**: 透明展示 AI 的分析思路
- **置信度评分**: 每个决策的置信度百分比
- **历史回顾**: 查看过往决策的准确率

### 交易历史
- **完整记录**: 所有开仓、平仓、止损止盈记录
- **时间戳**: 精确到毫秒的交易时间
- **盈亏统计**: 自动计算胜率、盈亏比、最大回撤

### (°∀°) 市场情绪
- **恐惧贪婪指数** - 实时市场情绪监控
- **多空比分析** - 智能解读多空比变化
- **链上数据** - 大户动向、交易所流入流出

### (｡･ω･｡) 用户界面
- **Web UI** - 基于 Streamlit 的现代化界面
- **实时监控** - 持仓、收益、信号实时更新
- **一键部署** - Docker 支持，Windows/Linux/macOS 全平台

---

## 快速开始

### 方式一：本地安装 (推荐)

**Windows:**
```bash
git clone https://github.com/hey345437-boop/hyweishi-ai-trader.git
cd hyweishi-ai-trader
install.bat
```
安装完成后双击 `启动机器人.bat` 启动，在 Web 界面中配置 API 密钥即可使用。

**Linux/macOS:**
```bash
git clone https://github.com/hey345437-boop/hyweishi-ai-trader.git
cd hyweishi-ai-trader
chmod +x install.sh && ./install.sh
source .venv/bin/activate && streamlit run app.py
```
启动后访问 http://localhost:8501，在界面中配置 API 密钥。

### 方式二：Docker 部署

```bash
git clone https://github.com/hey345437-boop/hyweishi-ai-trader.git
cd hyweishi-ai-trader
docker-compose up -d
```
访问 http://localhost:8501，在界面中配置 API 密钥。

---

## 配置说明

所有配置都可以在 Web 界面中完成：

- **OKX API** - 在「交易设置」页面配置交易所 API
- **AI API** - 在「AI 设置」页面配置各 AI 服务商的 API Key
- **交易参数** - 在界面中设置交易对、杠杆、仓位等参数

> (・ω・) 也支持通过 `.env` 文件配置，适合高级用户和 Docker 部署

---

## 项目结构

```
hyweishi-ai-trader/
├── app.py                 # 主入口
├── ai/                    # AI 决策模块
├── core/                  # 核心引擎
├── database/              # 数据库
├── exchange/              # 交易所对接
├── strategies/            # 交易策略
├── ui/                    # Web UI
├── utils/                 # 工具函数
└── separated_system/      # 后端引擎
```

---

## 支持的 AI 模型

| 服务商 | 模型版本 | 免费额度 | 备注 |
|--------|---------|---------|------|
| DeepSeek | V3.1 Chat, R1 Reasoner | 有 | 国产高性能，推荐 |
| 通义千问 | Qwen 3 (235B), QwQ Plus | 有 | 阿里云，深度思考 |
| 讯飞星火 | Spark 4.0 Ultra | 有 Lite | 科大讯飞 |
| 腾讯混元 | Turbo Latest | 有 Lite | 256K 上下文 |
| 火山豆包 | Doubao 1.5 Pro/Seed 1.6 | 有 | 字节跳动 |
| 智谱 GLM | GLM-4.6, GLM-4 Plus | 有 Flash | 国产领先 |
| OpenAI | GPT-5.2, o3, o4-mini | 无 | 最新旗舰 |
| Claude | Claude 4.5 Sonnet/Opus | 无 | Anthropic |
| Gemini | Gemini 3 Pro, 2.5 Flash | 有 | Google |
| Grok | Grok 4, Grok 3 | 有 | xAI |
| Perplexity | Sonar Pro, Reasoning | 有 | 联网搜索 |

---

## 许可证

本项目采用 [AGPL-3.0](LICENSE) 开源许可证。

**这意味着：**
- ✅ 可以免费使用、修改、分发本项目
- ✅ 可以用于个人学习和研究
- ⚠️ 修改后的代码必须同样开源
- ⚠️ 如果将本项目用于网络服务，必须公开源代码
- ❌ 不得移除版权声明和许可证信息

**商业使用请联系作者获取授权。**

---

## 支持项目

如果这个项目对你有帮助，欢迎请作者喝杯咖啡 (´▽`ʃ♡ƪ)

**加密货币捐赠：**
- USDT (BEP20): `0x67c77a43d6524994af9497b4cd32080b95f2ace9`

---

## 联系方式

- 邮箱: hey345437@gmail.com
- QQ: 3269180865

---

## ⭐ 给个 Star ⭐

<div align="center">

如果你觉得这个项目还不错，请给我一个 **Star** ⭐

这对一个学生开发者来说真的很重要 (´;ω;`)

你的支持是我继续更新的最大动力！

[![GitHub stars](https://img.shields.io/github/stars/hey345437-boop/hyweishi-ai-trader?style=social)](https://github.com/hey345437-boop/hyweishi-ai-trader)

</div>
