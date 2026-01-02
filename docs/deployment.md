# 部署指南

## 本地运行

### Windows

```batch
install.bat
# 编辑 .env
启动机器人.bat
```

### Linux/macOS

```bash
chmod +x install.sh && ./install.sh
cp .env.example .env && nano .env
source .venv/bin/activate && streamlit run app.py
```

## Docker

```bash
cp .env.example .env
# 编辑 .env
docker-compose up -d
# 访问 http://localhost:8501
```

## 配置说明

### 必填项

```env
# OKX API（实盘 Key，不是模拟盘）
OKX_API_KEY=xxx
OKX_API_SECRET=xxx
OKX_API_PASSPHRASE=xxx

# 运行模式
RUN_MODE=paper  # paper=模拟, live=实盘
```

### 风控配置

```env
MAX_ORDER_SIZE=1000          # 单笔最大金额 USDT
DAILY_LOSS_LIMIT_PCT=0.10    # 日损失限制 10%
```

### AI 配置（可选）

```env
DEEPSEEK_API_KEY=sk-xxx
DASHSCOPE_API_KEY=sk-xxx     # 通义千问
SPARK_API_PASSWORD=xxx       # 讯飞星火
```

## 生产环境建议

1. **设置访问密码**
   ```env
   STREAMLIT_ACCESS_PASSWORD=your_password
   ```

2. **使用 PostgreSQL**
   ```env
   DATABASE_URL=postgresql://user:pass@host:5432/dbname
   ```

3. **配置代理**（如果需要）
   ```env
   https_proxy=http://127.0.0.1:7890
   ```

4. **日志级别**
   ```env
   LOG_LEVEL=WARNING  # 生产环境减少日志
   ```
