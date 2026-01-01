# 贡献指南

## 报告问题

在 Issues 里提，包含：
- 问题描述
- 复现步骤
- 环境信息（Python 版本、OS）
- 相关日志（记得脱敏）

## 提交代码

```bash
# fork 后
git checkout -b feature/xxx
git commit -m 'feat: xxx'
git push origin feature/xxx
# 然后提 PR
```

### Commit 格式

用 [Conventional Commits](https://www.conventionalcommits.org/)：

- `feat:` 新功能
- `fix:` 修 bug
- `docs:` 文档
- `refactor:` 重构
- `test:` 测试

## 本地开发

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pytest tests/
```

## 代码规范

- Python 3.8+
- 遵循 PEP 8
- 写 docstring
- 敏感信息走环境变量

## 目录结构

```
ai/           # AI 决策
core/         # 核心引擎
database/     # 数据库
exchange_adapters/  # 交易所
sentiment/    # 情绪分析
strategies/   # 策略
ui/           # Web UI
```

有问题发 Issue 或邮件 hey345437@gmail.com。
