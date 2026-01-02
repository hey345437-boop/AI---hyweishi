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
    echo "请安装 Python 3.9+:"
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
echo "      尝试使用国内镜像源加速..."
pip install --upgrade pip -i https://pypi.tuna.tsinghua.edu.cn/simple --trusted-host pypi.tuna.tsinghua.edu.cn > /dev/null 2>&1 || pip install --upgrade pip > /dev/null 2>&1

# 首先尝试国内镜像（清华源）
if pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple --trusted-host pypi.tuna.tsinghua.edu.cn; then
    echo "      依赖安装完成 ✓"
else
    echo ""
    echo "      清华源安装失败，尝试阿里云镜像..."
    if pip install -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple --trusted-host mirrors.aliyun.com; then
        echo "      依赖安装完成 ✓"
    else
        echo ""
        echo "      阿里云镜像也失败，尝试官方源..."
        if pip install -r requirements.txt --trusted-host pypi.org --trusted-host files.pythonhosted.org; then
            echo "      依赖安装完成 ✓"
        else
            echo ""
            echo "[错误] 依赖安装失败"
            echo ""
            echo "可能的解决方案:"
            echo "  1. 检查网络连接"
            echo "  2. 关闭VPN或代理软件后重试"
            echo "  3. 检查系统时间是否正确"
            echo "  4. 手动运行: pip install -r requirements.txt"
            exit 1
        fi
    fi
fi
echo ""

# 配置环境变量
echo "[5/5] 配置环境..."
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        cp .env.example .env
        echo "      已创建 .env 配置文件"
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
echo "  1. 运行以下命令启动系统:"
echo ""
echo "     source .venv/bin/activate"
echo "     streamlit run app.py"
echo ""
echo "  2. 在 Web 界面中配置 API 密钥"
echo ""
echo "或使用 Docker:"
echo "     docker-compose up -d"
echo ""
