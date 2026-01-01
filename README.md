# 何以为势 (HyWeiShi)

<div align="center">

```
 _   _  __   __ __        __  _____ ___  ____   _   _  ___ 
| | | | \ \ / / \ \      / / | ____||_ _|/ ___| | | | ||_ _|
| |_| |  \ V /   \ \ /\ / /  |  _|   | | \___ \ | |_| | | | 
|  _  |   | |     \ V  V /   | |___  | |  ___) ||  _  | | | 
|_| |_|   |_|      \_/\_/    |_____||___||____/ |_| |_||___|
```

**智能量化交易系统 | Quantitative Trading System**

[![License: AGPL-3.0](https://img.shields.io/badge/License-AGPL%203.0-blue.svg)](LICENSE)
[![Python 3.8+](https://img.shields.io/badge/Python-3.8+-green.svg)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.28+-red.svg)](https://streamlit.io/)

中文 | [English](README.en.md)

</div>

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

- **多策略支持** - 内置多种交易策略，支持自定义策略开发
- **AI 决策辅助** - 集成 DeepSeek/通义千问等大模型，提供智能分析
- **可视化界面** - 基于 Streamlit 的 Web UI，实时监控交易状态
- **风控系统** - 完善的止损止盈、仓位管理、风险控制
- **双通道信号** - 多时间周期信号确认机制
- **模拟交易** - 支持 Paper Trading，零风险测试策略
- **OKX 集成** - 深度集成 OKX 交易所 API

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

## 许可证

[AGPL-3.0](LICENSE)

---

## 联系方式

- 邮箱: hey345437@gmail.com
- QQ: 3269180865

---

<div align="center">

**Made with ❤️ by HyWeiShi**

</div>
