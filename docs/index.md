# 何以为势 (HyWeiShi)

中文优先的 AI 量化交易系统。

## 特性

- **多 AI 竞技场** - 12+ 大模型同时决策，排行榜 PK
- **策略系统** - 注册表模式，支持自定义 + Pine 转换
- **风控内置** - 订单限额、日损失限制、模拟交易
- **OKX 集成** - 实盘/模拟双模式，实盘行情 + 本地撮合

## 快速开始

```bash
# 克隆
git clone https://github.com/your-username/hyweishi.git
cd hyweishi

# 安装
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 配置
cp .env.example .env
# 编辑 .env 填入 API Key

# 启动
streamlit run app.py
```

Windows 用户直接双击 `install.bat`，然后 `启动机器人.bat`。

## 文档导航

- [架构设计](architecture.md)
- [策略开发](strategies.md)
- [API 参考](api/index.md)
- [部署指南](deployment.md)
