# HyWeiShi (何以为势)

<div align="center">

```
 _   _  __   __ __        __  _____ ___  ____   _   _  ___ 
| | | | \ \ / / \ \      / / | ____||_ _|/ ___| | | | ||_ _|
| |_| |  \ V /   \ \ /\ / /  |  _|   | | \___ \ | |_| | | | 
|  _  |   | |     \ V  V /   | |___  | |  ___) ||  _  | | | 
|_| |_|   |_|      \_/\_/    |_____||___||____/ |_| |_||___|
```

**AI-Powered Quantitative Trading System**

[![License: AGPL-3.0](https://img.shields.io/badge/License-AGPL%203.0-blue.svg)](LICENSE)
[![Python 3.8+](https://img.shields.io/badge/Python-3.8+-green.svg)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.28+-red.svg)](https://streamlit.io/)

[中文文档](README.md) | English

</div>

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

- **Multi-Strategy Support** - Built-in strategies + custom strategy development
- **AI Decision Engine** - 12+ LLM providers (DeepSeek, Qwen, GPT, Claude, Gemini...)
- **AI Arena** - Multiple AI models compete in real-time trading decisions
- **Risk Control** - Order limits, daily loss limits, paper trading mode
- **Market Sentiment** - Fear & Greed Index, news analysis, on-chain data
- **OKX Integration** - Live and paper trading modes
- **Web UI** - Streamlit-based dashboard for monitoring and control
- **One-Click Deploy** - Docker support, simple installation scripts

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

## Supported AI Providers

| Provider | Free Tier | Notes |
|----------|-----------|-------|
| DeepSeek | ✅ | Recommended for Chinese users |
| Qwen (通义千问) | ✅ | Via DashScope |
| Spark (讯飞星火) | ✅ | Spark Lite free |
| GLM (智谱) | ✅ | GLM-4-Flash free |
| Hunyuan (腾讯混元) | ✅ | Hunyuan-Lite free |
| Doubao (豆包) | ✅ | Via Volcengine |
| OpenAI | ❌ | GPT-4, GPT-3.5 |
| Claude | ❌ | Anthropic |
| Gemini | ✅ | Google, free tier available |
| Grok | ❌ | xAI |
| Perplexity | ❌ | Online search capability |

---

## License

[AGPL-3.0](LICENSE)

---

## Contact

- Email: hey345437@gmail.com
- QQ: 3269180865

---

<div align="center">

**Made with ❤️ by HyWeiShi**

</div>
