# 安全政策

## 报告漏洞

发现安全问题**不要**公开发 Issue。

发邮件到 **hey345437@gmail.com**，标题加 `[SECURITY]`。

包含：
1. 漏洞类型
2. 影响范围
3. 复现步骤
4. PoC（如果有）

响应时间：48 小时内确认，7 天内评估。

## 使用建议

### API Key

- 用 `.env` 存储，确保在 `.gitignore` 里
- 行情和交易分开用不同的 Key
- 别在代码里硬编码

### 交易安全

- 先用 `paper` 模式测试
- 设置 `MAX_ORDER_SIZE` 和 `DAILY_LOSS_LIMIT_PCT`
- 不熟悉别用 `live` 模式

### 部署

- 公网部署要设 `STREAMLIT_ACCESS_PASSWORD`
- 定期更新依赖
- `.env` 和 `*.db` 文件权限设好
