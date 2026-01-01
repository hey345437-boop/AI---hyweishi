#!/bin/bash
# -*- coding: utf-8 -*-
# ============================================================================
#    何以为势 - Quantitative Trading System
#    一键安装脚本 (Linux/macOS)
# ============================================================================

set -e

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║                                                              ║"
echo "║     何以为势 - Quantitative Trading System                   ║"
echo "║     一键安装脚本 (Linux/macOS)                               ║"
echo "║                                                              ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# 检查 Python
echo "[1/5] 检查 Python..."
if ! command -v python3 &> /dev/null; then
    echo "[错误] Python3 未安装"
    echo ""
    echo "请安装 Python 3.8+:"
    echo "  Ubuntu/Debian: sudo apt install python3 python3-venv python3-pip"
    echo "  macOS: brew install python3"
    exit 1
fi
PYVER=$(python3 --version 2>&1 | cut -d' ' -f2)
echo "      Python $PYVER ✓"
echo ""

# 创建虚拟环境
echo "[2/5] 创建虚拟环境..."
if [ -d ".venv" ]; then
    echo "      虚拟环境已存在，跳过创建"
else
    python3 -m venv .venv
    echo "      虚拟环境创建成功 ✓"
fi
echo ""

# 激活虚拟环境
echo "[3/5] 激活虚拟环境..."
source .venv/bin/activate
echo "      虚拟环境已激活 ✓"
echo ""

# 安装依赖
echo "[4/5] 安装依赖包（可能需要几分钟）..."
pip install --upgrade pip > /dev/null 2>&1
pip install -r requirements.txt
echo "      依赖安装完成 ✓"
echo ""

# 配置环境变量
echo "[5/5] 配置环境..."
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        cp .env.example .env
        echo "      已创建 .env 配置文件"
        echo ""
        echo "⚠️  重要：请编辑 .env 文件，填入你的 API 密钥"
    else
        echo "[警告] 未找到 .env.example 模板"
    fi
else
    echo "      .env 配置文件已存在"
fi

# 创建必要目录
mkdir -p logs data
echo "      目录结构已就绪 ✓"
echo ""

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║                     安装完成！                               ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
echo "下一步:"
echo "  1. 编辑 .env 文件，配置你的 OKX API 密钥"
echo "  2. 运行以下命令启动系统:"
echo ""
echo "     source .venv/bin/activate"
echo "     streamlit run app.py"
echo ""
echo "或使用 Docker:"
echo "     docker-compose up -d"
echo ""
