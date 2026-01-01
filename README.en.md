# 🚀 HyWeiShi (何以为势)

<div align="center">

<img src="https://img.shields.io/badge/AI-Powered-blueviolet?style=for-the-badge&logo=openai&logoColor=white" alt="AI Powered"/>
<img src="https://img.shields.io/badge/Crypto-Futures-orange?style=for-the-badge&logo=bitcoin&logoColor=white" alt="Crypto Futures"/>
<img src="https://img.shields.io/badge/Trading-Bot-success?style=for-the-badge&logo=robot&logoColor=white" alt="Trading Bot"/>

<br/><br/>

**🔮 AI-Powered Cryptocurrency Futures Trading Engine**

*Let AI be your trading partner, seize market opportunities*

<br/>

[![License: AGPL-3.0](https://img.shields.io/badge/License-AGPL%203.0-blue.svg?style=flat-square)](LICENSE)
[![Python 3.8+](https://img.shields.io/badge/Python-3.8+-3776AB.svg?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.28+-FF4B4B.svg?style=flat-square&logo=streamlit&logoColor=white)](https://streamlit.io/)
[![OKX](https://img.shields.io/badge/OKX-Supported-000000.svg?style=flat-square)](https://www.okx.com/)

<br/>

[中文文档](README.md) | [English](#features) | [Quick Start](#quick-start) | [AI Models](#supported-ai-models)

</div>

<br/>

---

## Disclaimer

**This project is for educational and research purposes only. Not financial advice.**

- Automated trading involves risks including technical failures, API errors, and network latency
- Past performance does not guarantee future results
- Never trade with money you cannot afford to lose
- The author is not responsible for any trading losses

**By using this software, you acknowledge and accept these risks.**

---

## Features

### 🤖 AI-Powered Trading
- **12+ AI Providers** - DeepSeek, Qwen 3, GPT-5, Claude 4.5, Gemini 3, and more
- **AI Arena** - Multiple AI models analyze simultaneously, vote-based decisions
- **5 Trading Personas** - Hunter/Balanced/Monk/Flash/Surfer styles for different strategies
- **Custom Prompts** - Fully customizable AI persona and trading strategy
- **Smart News Analysis** - AI interprets market news and generates trading signals

### 📊 Technical Analysis
- **Multi-Timeframe** - Support for 1m/5m/15m/1h/4h/1d analysis
- **Rich Indicators** - MA/EMA/RSI/MACD/KDJ/BOLL/ATR/OBV/VWAP and more
- **Change Tracking** - Visualize indicator trends for better AI understanding
- **Dual-Channel Signals** - Multi-timeframe signal confirmation

### 💹 Trading Features
- **OKX Futures** - Deep integration with OKX perpetual contracts API
- **Paper Trading** - Risk-free strategy testing
- **Risk Control** - Stop-loss, take-profit, position sizing, daily loss limits
- **Multi-Strategy** - Built-in strategies + custom strategy development
- **More Exchanges** - Binance, Bybit support coming soon

### 📈 Market Sentiment
- **Fear & Greed Index** - Real-time market sentiment monitoring
- **Long/Short Ratio** - Smart interpretation of market positioning
- **On-Chain Data** - Whale movements, exchange inflows/outflows

### 🖥️ User Interface
- **Web UI** - Modern Streamlit-based dashboard
- **Real-Time Monitoring** - Live positions, PnL, and signals
- **One-Click Deploy** - Docker support, Windows/Linux/macOS

---

## Quick Start

### Option 1: Local Installation

**Windows:**
```bash
git clone https://github.com/hey345437-boop/my-trading-bot-2.git
cd my-trading-bot-2
install.bat
```
After installation, edit `.env` file with your API keys, then run `启动机器人.bat`.

**Linux/macOS:**
```bash
git clone https://github.com/hey345437-boop/my-trading-bot-2.git
cd my-trading-bot-2
chmod +x install.sh && ./install.sh
cp .env.example .env && nano .env
source .venv/bin/activate && streamlit run app.py
```

### Option 2: Docker

```bash
git clone https://github.com/hey345437-boop/my-trading-bot-2.git
cd my-trading-bot-2
cp .env.example .env
# Edit .env with your API keys
docker-compose up -d
# Visit http://localhost:8501
```

---

## Configuration

Edit `.env` file:

```env
# Run mode: paper (testing) / live (real trading)
RUN_MODE=paper

# OKX API
OKX_API_KEY=your_api_key
OKX_API_SECRET=your_api_secret
OKX_API_PASSPHRASE=your_passphrase

# AI Configuration (optional)
DEEPSEEK_API_KEY=your_deepseek_key
```

---

## Project Structure

```
hyweishi/
├── app.py                 # Main entry
├── ai/                    # AI decision engine
├── core/                  # Core trading engine
├── database/              # Database layer
├── exchange_adapters/     # Exchange adapters
├── strategies/            # Trading strategies
├── sentiment/             # Market sentiment analysis
├── ui/                    # Web UI
└── utils/                 # Utilities
```

---

## Supported AI Models

| Provider | Models | Free Tier | Notes |
|----------|--------|-----------|-------|
| DeepSeek | V3.1 Chat, R1 Reasoner | ✅ | High-performance, recommended |
| Qwen | Qwen 3 (235B), QwQ Plus | ✅ | Alibaba Cloud, deep reasoning |
| Spark | Spark 4.0 Ultra | ✅ Lite | iFlytek |
| Hunyuan | Turbo Latest | ✅ Lite | Tencent, 256K context |
| Doubao | 1.5 Pro, Seed 1.6 | ✅ | ByteDance |
| GLM | GLM-4.6, GLM-4 Plus | ✅ Flash | Zhipu AI |
| OpenAI | GPT-5.2, o3, o4-mini | ❌ | Latest flagship |
| Claude | Claude 4.5 Sonnet/Opus | ❌ | Anthropic |
| Gemini | Gemini 3 Pro, 2.5 Flash | ✅ | Google |
| Grok | Grok 4, Grok 3 | ❌ | xAI |
| Perplexity | Sonar Pro, Reasoning | ❌ | Web search capability |

---

## License

[AGPL-3.0](LICENSE)

---

## Support the Project

If this project helps you, consider buying the author a coffee ☕

**Crypto Donations:**
- BTC: `TBD`
- ETH/USDT (ERC20): `TBD`
- USDT (TRC20): `TBD`

---

## Contact

- Email: hey345437@gmail.com
- QQ: 3269180865

---

<div align="center">

**Made with ❤️ by HyWeiShi**

</div>
