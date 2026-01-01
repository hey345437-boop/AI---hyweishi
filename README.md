# 🚀 何以为势 (HyWeiShi)

<div align="center">

<img src="https://img.shields.io/badge/AI-Powered-blueviolet?style=for-the-badge&logo=openai&logoColor=white" alt="AI Powered"/>
<img src="https://img.shields.io/badge/Crypto-Futures-orange?style=for-the-badge&logo=bitcoin&logoColor=white" alt="Crypto Futures"/>
<img src="https://img.shields.io/badge/Trading-Bot-success?style=for-the-badge&logo=robot&logoColor=white" alt="Trading Bot"/>

<br/><br/>

**🔮 AI 驱动的加密货币合约交易引擎**

*让 AI 成为你的交易搭档，洞察市场先机*

<br/>

[![License: AGPL-3.0](https://img.shields.io/badge/License-AGPL%203.0-blue.svg?style=flat-square)](LICENSE)
[![Python 3.8+](https://img.shields.io/badge/Python-3.8+-3776AB.svg?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.28+-FF4B4B.svg?style=flat-square&logo=streamlit&logoColor=white)](https://streamlit.io/)
[![OKX](https://img.shields.io/badge/OKX-Supported-000000.svg?style=flat-square)](https://www.okx.com/)

<br/>

[中文文档](#功能特性) | [English](README.en.md) | [快速开始](#快速开始) | [AI 模型](#支持的-ai-模型)

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

### 🤖 AI 智能决策
- **12+ AI 服务商** - DeepSeek、通义千问、GPT-5、Claude 4.5、Gemini 3 等最新模型
- **AI 竞技场** - 多个 AI 模型同时分析，投票决策，提高准确率
- **5 种交易人设** - 猎人型/均衡型/僧侣型/闪电型/冲浪型，适应不同风格
- **自定义提示词** - 完全自定义 AI 人设和交易策略，打造专属交易员
- **智能新闻分析** - AI 自动解读市场新闻，生成交易信号

### 📊 技术分析
- **多时间周期** - 支持 1m/5m/15m/1h/4h/1d 等多周期分析
- **丰富指标** - MA/EMA/RSI/MACD/KDJ/BOLL/ATR/OBV/VWAP 等
- **变化量追踪** - 指标变化趋势可视化，AI 更好理解市场动态
- **双通道信号** - 多时间周期信号确认机制

### 💹 交易功能
- **OKX 合约交易** - 深度集成 OKX 永续合约 API
- **模拟交易** - Paper Trading 模式，零风险测试策略
- **风控系统** - 止损止盈、仓位管理、每日亏损限制
- **多策略支持** - 内置策略 + 自定义策略开发
- **更多交易所** - 后续将支持 Binance、Bybit 等主流交易所

### 📈 市场情绪
- **恐惧贪婪指数** - 实时市场情绪监控
- **多空比分析** - 智能解读多空比变化
- **链上数据** - 大户动向、交易所流入流出

### 🖥️ 用户界面
- **Web UI** - 基于 Streamlit 的现代化界面
- **实时监控** - 持仓、收益、信号实时更新
- **一键部署** - Docker 支持，Windows/Linux/macOS 全平台

---

## 快速开始

### 方式一：本地安装 (推荐)

**Windows:**
```bash
git clone https://github.com/hey345437-boop/my-trading-bot-2.git
cd my-trading-bot-2
install.bat
```
安装完成后编辑 `.env` 文件配置 API 密钥，然后双击 `启动机器人.bat` 启动。

**Linux/macOS:**
```bash
git clone https://github.com/hey345437-boop/my-trading-bot-2.git
cd my-trading-bot-2
chmod +x install.sh && ./install.sh
cp .env.example .env && nano .env
source .venv/bin/activate && streamlit run app.py
```

### 方式二：Docker 部署

```bash
git clone https://github.com/hey345437-boop/my-trading-bot-2.git
cd my-trading-bot-2
cp .env.example .env
# 编辑 .env 配置 API 密钥
docker-compose up -d
# 访问 http://localhost:8501
```

---

## 配置说明

编辑 `.env` 文件：

```env
# 运行模式: paper(测试) / live(实盘)
RUN_MODE=paper

# OKX API
OKX_API_KEY=your_api_key
OKX_API_SECRET=your_api_secret
OKX_API_PASSPHRASE=your_passphrase

# AI 配置（可选）
DEEPSEEK_API_KEY=your_deepseek_key
```

---

## 项目结构

```
hyweishi-trading-bot/
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
| DeepSeek | V3.1 Chat, R1 Reasoner | ✅ | 国产高性能，推荐 |
| 通义千问 | Qwen 3 (235B), QwQ Plus | ✅ | 阿里云，深度思考 |
| 讯飞星火 | Spark 4.0 Ultra | ✅ Lite | 科大讯飞 |
| 腾讯混元 | Turbo Latest | ✅ Lite | 256K 上下文 |
| 火山豆包 | Doubao 1.5 Pro/Seed 1.6 | ✅ | 字节跳动 |
| 智谱 GLM | GLM-4.6, GLM-4 Plus | ✅ Flash | 国产领先 |
| OpenAI | GPT-5.2, o3, o4-mini | ❌ | 最新旗舰 |
| Claude | Claude 4.5 Sonnet/Opus | ❌ | Anthropic |
| Gemini | Gemini 3 Pro, 2.5 Flash | ✅ | Google |
| Grok | Grok 4, Grok 3 | ❌ | xAI |
| Perplexity | Sonar Pro, Reasoning | ❌ | 联网搜索 |

---

## 许可证

[AGPL-3.0](LICENSE)

---

## 支持项目

如果这个项目对你有帮助，欢迎请作者喝杯咖啡 ☕

**加密货币捐赠：**
- BTC: `待填写`
- ETH/USDT (ERC20): `待填写`
- USDT (TRC20): `待填写`

---

## 联系方式

- 邮箱: hey345437@gmail.com
- QQ: 3269180865

---

<div align="center">

**Made with ❤️ by HyWeiShi**

</div>
