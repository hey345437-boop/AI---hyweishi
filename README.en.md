# (・ω・) HyWeiShi (何以为势)

<div align="center">

<img src="https://img.shields.io/badge/AI-Powered-blueviolet?style=for-the-badge&logo=openai&logoColor=white" alt="AI Powered"/>
<img src="https://img.shields.io/badge/Crypto-Futures-orange?style=for-the-badge&logo=bitcoin&logoColor=white" alt="Crypto Futures"/>
<img src="https://img.shields.io/badge/Trading-Bot-success?style=for-the-badge&logo=robot&logoColor=white" alt="Trading Bot"/>

<br/><br/>

<pre>
██╗  ██╗██╗   ██╗██╗    ██╗███████╗██╗███████╗██╗  ██╗██╗
██║  ██║╚██╗ ██╔╝██║    ██║██╔════╝██║██╔════╝██║  ██║██║
███████║ ╚████╔╝ ██║ █╗ ██║█████╗  ██║███████╗███████║██║
██╔══██║  ╚██╔╝  ██║███╗██║██╔══╝  ██║╚════██║██╔══██║██║
██║  ██║   ██║   ╚███╔███╔╝███████╗██║███████║██║  ██║██║
╚═╝  ╚═╝   ╚═╝    ╚══╝╚══╝ ╚══════╝╚═╝╚══════╝╚═╝  ╚═╝╚═╝
</pre>

**(*≧▽≦) AI-Powered Cryptocurrency Futures Trading Engine**

*Let AI be your trading partner, seize market opportunities*

<br/>

[![License: AGPL-3.0](https://img.shields.io/badge/License-AGPL%203.0-blue.svg?style=flat-square)](LICENSE)
[![Python 3.8+](https://img.shields.io/badge/Python-3.8+-3776AB.svg?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.28+-FF4B4B.svg?style=flat-square&logo=streamlit&logoColor=white)](https://streamlit.io/)
[![OKX](https://img.shields.io/badge/OKX-Supported-000000.svg?style=flat-square)](https://www.okx.com/)

<br/>

[中文文档](README.md) | [English](#features) | [日本語](README.ja.md) | [한국어](README.ko.md) | [Quick Start](#quick-start) | [AI Models](#supported-ai-models)

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

### (￣▽￣) AI-Powered Trading
- **12+ AI Providers** - DeepSeek, Qwen 3, GPT-5, Claude 4.5, Gemini 3, and more
- **AI Arena** - Multiple AI models analyze simultaneously, vote-based decisions
- **5 Trading Personas** - Hunter/Balanced/Monk/Flash/Surfer styles for different strategies
- **Custom Prompts** - Fully customizable AI persona and trading strategy
- **Smart News Analysis** - AI interprets market news and generates trading signals

### (◎_◎) Technical Analysis
- **Multi-Timeframe** - Support for 1m/5m/15m/1h/4h/1d analysis
- **Rich Indicators** - MA/EMA/RSI/MACD/KDJ/BOLL/ATR/OBV/VWAP and more
- **Change Tracking** - Visualize indicator trends for better AI understanding
- **Dual-Channel Signals** - Multi-timeframe signal confirmation

### (￥ω￥) Trading Features
- **OKX Futures** - Deep integration with OKX perpetual contracts API
- **Paper Trading** - Risk-free strategy testing
- **Risk Control** - Stop-loss, take-profit, position sizing, daily loss limits
- **Multi-Strategy** - Built-in strategies + custom strategy development
- **More Exchanges** - Binance, Bybit support coming soon

---

## Complete Trading Features

### Supported Assets
BTC, ETH, SOL, BNB, XRP, DOGE, GT, TRUMP, ADA, WLFI and other major cryptocurrencies. Trading pool is fully configurable in the interface.

### Contract Type
- **USDT Perpetual Contracts** - Settled in USDT
- **Hedge Mode** - Support simultaneous long and short positions

### Margin Mode
| Mode | Description | Use Case |
|------|-------------|----------|
| Cross | All positions share margin, shared risk | Higher capital efficiency, for experienced traders |
| Isolated | Each position has independent margin | Single position liquidation won't affect others, better risk control |

### Leverage Range
- **Configurable Range**: 1x ~ 50x (adjustable in UI)
- **Recommended**: 5x ~ 20x (balance risk and reward)
- **Auto-Deleverage**: Advanced strategies auto-adjust based on ATR volatility

### Order Types
| Type | Description | Status |
|------|-------------|--------|
| Market Order | Immediate execution at current price | ✅ Supported |
| Stop Loss | Auto-close when price triggers | ✅ Supported |
| Take Profit | Auto-close when profit target reached | ✅ Supported |
| Limit Order | Pending order at specified price | 🔜 Coming Soon |

### Risk Control System
- **Order Size Limit**: Maximum amount per single order
- **Max Position**: Total position capped at percentage of equity
- **Daily Loss Limit**: Auto-stop trading when daily loss threshold reached
- **Cooldown Period**: Prevent same-direction entry after stop-loss

---

## Real-Time Monitoring

### Web Dashboard
- **Account Overview**: Equity, available balance, used margin
- **Position Monitor**: Real-time PnL, leverage, liquidation price
- **Charts**: Multi-timeframe candlesticks with technical indicators

### AI Decision Logs
- **Reasoning Process**: Transparent display of AI analysis
- **Confidence Score**: Percentage confidence for each decision
- **Historical Review**: Track past decision accuracy

### Trade History
- **Complete Records**: All entries, exits, stop-loss, take-profit events
- **Timestamps**: Millisecond-precision trade times
- **Statistics**: Auto-calculated win rate, profit factor, max drawdown

### (°∀°) Market Sentiment
- **Fear & Greed Index** - Real-time market sentiment monitoring
- **Long/Short Ratio** - Smart interpretation of market positioning
- **On-Chain Data** - Whale movements, exchange inflows/outflows

### (｡･ω･｡) User Interface
- **Web UI** - Modern Streamlit-based dashboard
- **Real-Time Monitoring** - Live positions, PnL, and signals
- **One-Click Deploy** - Docker support, Windows/Linux/macOS

---

## Quick Start

### Option 1: Local Installation

**Windows:**
```bash
git clone https://github.com/hey345437-boop/AI---hyweishi.git
cd AI---hyweishi
install.bat
```
After installation, run `启动机器人.bat` and configure API keys in the web interface.

**Linux/macOS:**
```bash
git clone https://github.com/hey345437-boop/AI---hyweishi.git
cd AI---hyweishi
chmod +x install.sh && ./install.sh
source .venv/bin/activate && streamlit run app.py
```
Visit http://localhost:8501 and configure API keys in the interface.

### Option 2: Docker

```bash
git clone https://github.com/hey345437-boop/AI---hyweishi.git
cd AI---hyweishi
docker-compose up -d
```
Visit http://localhost:8501 and configure API keys in the interface.

---

## Configuration

All settings can be configured in the Web interface:

- **OKX API** - Configure exchange API in "Trading Settings"
- **AI API** - Configure AI provider API keys in "AI Settings"  
- **Trading Parameters** - Set trading pairs, leverage, position size in the interface

> (・ω・) Advanced users can also configure via `.env` file for Docker deployment

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

This project is licensed under [AGPL-3.0](LICENSE).

**This means:**
- ✅ Free to use, modify, and distribute
- ✅ Can be used for personal learning and research
- ⚠️ Modified code must also be open-sourced
- ⚠️ If used for network services, source code must be disclosed
- ❌ Copyright notices and license information must not be removed

**For commercial use, please contact the author for licensing.**

---

## Support the Project

If this project helps you, consider buying the author a coffee (´▽`ʃ♡ƪ)

**Crypto Donations:**
- USDT (BEP20): `0x67c77a43d6524994af9497b4cd32080b95f2ace9`

---

## Contact

- Email: hey345437@gmail.com
- QQ: 3269180865

---

## ⭐ Give it a Star

<div align="center">

If you find this project helpful, please give it a **Star** ⭐

It means a lot to a student developer like me (´;ω;`)

Your support keeps me motivated to keep improving!

[![GitHub stars](https://img.shields.io/github/stars/hey345437-boop/AI---hyweishi?style=social)](https://github.com/hey345437-boop/AI---hyweishi)

</div>

