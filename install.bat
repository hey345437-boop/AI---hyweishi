@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo.
echo ╔══════════════════════════════════════════════════════════════╗
echo ║                                                              ║
echo ║     何以为势 - Quantitative Trading System                   ║
echo ║     一键安装脚本 (Windows)                                   ║
echo ║                                                              ║
echo ╚══════════════════════════════════════════════════════════════╝
echo.

:: 检查 Python
echo [1/5] 检查 Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] Python 未安装
    echo.
    echo 请从以下地址下载安装 Python 3.8+:
    echo   https://www.python.org/downloads/
    echo.
    echo 安装时请勾选 "Add Python to PATH"
    pause
    exit /b 1
)
for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYVER=%%i
echo       Python %PYVER% ✓
echo.

:: 创建虚拟环境
echo [2/5] 创建虚拟环境...
if exist ".venv" (
    echo       虚拟环境已存在，跳过创建
) else (
    python -m venv .venv
    if errorlevel 1 (
        echo [错误] 创建虚拟环境失败
        pause
        exit /b 1
    )
    echo       虚拟环境创建成功 ✓
)
echo.

:: 激活虚拟环境
echo [3/5] 激活虚拟环境...
call .venv\Scripts\activate.bat
echo       虚拟环境已激活 ✓
echo.

:: 安装依赖
echo [4/5] 安装依赖包（可能需要几分钟）...
pip install --upgrade pip >nul 2>&1
pip install -r requirements.txt
if errorlevel 1 (
    echo [错误] 依赖安装失败
    echo 请检查网络连接或尝试使用国内镜像:
    echo   pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
    pause
    exit /b 1
)
echo       依赖安装完成 ✓
echo.

:: 配置环境变量
echo [5/5] 配置环境...
if not exist ".env" (
    if exist ".env.example" (
        copy .env.example .env >nul
        echo       已创建 .env 配置文件
        echo.
        echo ⚠️  重要：请编辑 .env 文件，填入你的 API 密钥
    ) else (
        echo [警告] 未找到 .env.example 模板
    )
) else (
    echo       .env 配置文件已存在
)

:: 创建必要目录
if not exist "logs" mkdir logs
if not exist "data" mkdir data
echo       目录结构已就绪 ✓
echo.

echo ╔══════════════════════════════════════════════════════════════╗
echo ║                     安装完成！                               ║
echo ╚══════════════════════════════════════════════════════════════╝
echo.
echo 下一步:
echo   1. 编辑 .env 文件，配置你的 OKX API 密钥
echo   2. 运行 启动机器人.bat 启动系统
echo.
echo 或者直接运行:
echo   .venv\Scripts\activate.bat
echo   streamlit run app.py
echo.
pause
