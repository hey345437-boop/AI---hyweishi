@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ==========================================
echo     停止量化交易系统所有服务
echo ==========================================
echo.

REM 杀死占用 8000 端口的进程（Market API）
echo [1/3] 停止 Market API (端口 8000)...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000.*LISTENING"') do (
    echo       终止进程 PID: %%a
    taskkill /F /PID %%a >nul 2>&1
)

REM 杀死占用 8501 端口的进程（Streamlit）
echo [2/3] 停止 Streamlit 前端 (端口 8501)...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8501.*LISTENING"') do (
    echo       终止进程 PID: %%a
    taskkill /F /PID %%a >nul 2>&1
)

REM 杀死所有 python.exe 中包含 trade_engine 的进程
echo [3/3] 停止后端引擎...
for /f "tokens=2 delims=," %%a in ('wmic process where "commandline like '%%trade_engine%%'" get processid /format:csv ^| findstr /r "[0-9]"') do (
    echo       终止后端进程 PID: %%a
    taskkill /F /PID %%a >nul 2>&1
)

REM 额外：杀死窗口标题匹配的进程
taskkill /F /FI "WINDOWTITLE eq Market API*" >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq Trading Bot Backend*" >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq Trading Bot Frontend*" >nul 2>&1

echo.
echo ==========================================
echo     所有服务已停止
echo ==========================================
echo.
echo 提示：如果仍有残留进程，可以手动运行：
echo   taskkill /F /IM python.exe
echo.
pause
