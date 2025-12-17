@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ==========================================
echo     启动量化交易系统（后端 + 前端）
echo ==========================================
echo.

REM 创建日志目录
if not exist "logs" mkdir logs

REM 激活虚拟环境
if exist ".venv\Scripts\activate.bat" (
  call ".venv\Scripts\activate.bat"
  echo [1/4] 虚拟环境已激活 (.venv)
) else if exist "trade_env\Scripts\activate.bat" (
  call "trade_env\Scripts\activate.bat"
  echo [1/4] 虚拟环境已激活 (trade_env)
) else (
  echo [1/4] 使用系统 Python
)

REM 检查 Python
python --version >nul 2>&1
if errorlevel 1 (
  echo [错误] Python 不可用，请安装 Python 3.8+
  pause
  exit /b 1
)
echo [2/4] Python 检查通过

REM 启动 Market API 服务
echo [3/5] 启动 Market API 服务...
if exist "market_api.py" (
  start "Market API" cmd /k "python market_api.py"
  echo       Market API: http://localhost:8000
) else (
  echo [警告] 未找到 market_api.py，跳过 API 服务启动
)

REM 等待 API 初始化
timeout /t 2 /nobreak >nul

REM 启动后端
echo [4/5] 启动后端引擎...
if exist "separated_system\trade_engine.py" (
  start "Trading Bot Backend" cmd /k "python separated_system\trade_engine.py"
) else if exist "trade_engine.py" (
  start "Trading Bot Backend" cmd /k "python trade_engine.py"
) else (
  echo [警告] 未找到后端入口文件，跳过后端启动
)

REM 等待后端初始化
timeout /t 3 /nobreak >nul

REM 启动前端
echo [5/5] 启动前端界面...
start "Trading Bot Frontend" cmd /k "streamlit run app.py --server.port 8501"

REM 等待前端启动
timeout /t 5 /nobreak >nul

REM 打开浏览器
echo.
echo ==========================================
echo     系统启动完成
echo ==========================================
echo.
echo 前端地址: http://localhost:8501
echo API 地址: http://localhost:8000
echo API 文档: http://localhost:8000/docs
echo.
echo 提示：
echo   - Market API 窗口：K线数据服务（端口8000）
echo   - 后端窗口：显示交易引擎日志
echo   - 前端窗口：显示 Streamlit 日志
echo   - 关闭窗口即可停止对应服务
echo.

start "" "http://localhost:8501"

echo 按任意键关闭此窗口（不影响已启动的服务）...
pause >nul
