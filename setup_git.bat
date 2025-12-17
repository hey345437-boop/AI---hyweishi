@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo ============================================
echo   何以为势 Trading Bot - Git 初始化脚本
echo ============================================
echo.

:: 检查 Git 是否安装
where git >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] Git 未安装，请先安装 Git
    echo 下载地址: https://git-scm.com/download/win
    pause
    exit /b 1
)

:: 检查是否已经是 Git 仓库
if exist ".git" (
    echo [提示] 当前目录已经是 Git 仓库
    set /p REINIT="是否重新初始化? (y/n): "
    if /i "!REINIT!" neq "y" (
        goto :ADD_REMOTE
    )
    echo [操作] 删除旧的 .git 目录...
    rmdir /s /q .git
)

:: 初始化 Git 仓库
echo.
echo [步骤 1/5] 初始化 Git 仓库...
git init
if %errorlevel% neq 0 (
    echo [错误] Git 初始化失败
    pause
    exit /b 1
)
echo [成功] Git 仓库初始化完成

:ADD_REMOTE
:: 添加远程仓库
echo.
echo [步骤 2/5] 配置远程仓库...
echo.
echo 请输入你的 GitHub 私有仓库地址
echo 格式示例: https://github.com/你的用户名/仓库名.git
echo 或 SSH: git@github.com:你的用户名/仓库名.git
echo.
set /p REMOTE_URL="远程仓库地址: "

if "!REMOTE_URL!"=="" (
    echo [警告] 未输入远程仓库地址，跳过此步骤
    echo [提示] 稍后可以手动执行: git remote add origin 你的仓库地址
) else (
    :: 检查是否已有 origin
    git remote get-url origin >nul 2>&1
    if %errorlevel% equ 0 (
        echo [提示] 已存在 origin 远程仓库，正在更新...
        git remote set-url origin !REMOTE_URL!
    ) else (
        git remote add origin !REMOTE_URL!
    )
    echo [成功] 远程仓库已配置: !REMOTE_URL!
)

:: 添加文件
echo.
echo [步骤 3/5] 添加文件到暂存区...
git add .
if %errorlevel% neq 0 (
    echo [错误] 添加文件失败
    pause
    exit /b 1
)

:: 显示将要提交的文件
echo.
echo [信息] 将要提交的文件:
git status --short
echo.

:: 检查大文件
echo [检查] 正在检查大文件...
for /f "tokens=*" %%i in ('git ls-files --cached') do (
    for %%j in ("%%i") do (
        set "size=%%~zj"
        if defined size (
            if !size! gtr 104857600 (
                echo [警告] 发现大文件 (>100MB): %%i - !size! bytes
                echo [提示] GitHub 不允许上传超过 100MB 的文件
                echo [建议] 请将该文件添加到 .gitignore 中
            )
        )
    )
)

:: 提交
echo.
echo [步骤 4/5] 提交更改...
set /p COMMIT_MSG="请输入提交信息 (默认: Initial commit): "
if "!COMMIT_MSG!"=="" set COMMIT_MSG=Initial commit

git commit -m "!COMMIT_MSG!"
if %errorlevel% neq 0 (
    echo [错误] 提交失败
    pause
    exit /b 1
)
echo [成功] 提交完成

:: 推送
echo.
echo [步骤 5/5] 推送到远程仓库...
if "!REMOTE_URL!"=="" (
    echo [跳过] 未配置远程仓库，跳过推送
    goto :END
)

:: 设置默认分支为 main
git branch -M main

echo [操作] 正在推送到 origin/main...
git push -u origin main
if %errorlevel% neq 0 (
    echo.
    echo [错误] 推送失败，可能的原因:
    echo   1. 远程仓库地址错误
    echo   2. 没有推送权限（检查 SSH key 或 Personal Access Token）
    echo   3. 远程仓库已有内容，需要先 pull
    echo   4. 文件过大（GitHub 限制单文件 100MB）
    echo.
    echo [提示] 如果是权限问题，请确保:
    echo   - HTTPS: 使用 Personal Access Token 作为密码
    echo   - SSH: 已配置 SSH key
    echo.
    set /p FORCE_PUSH="是否强制推送? (y/n): "
    if /i "!FORCE_PUSH!"=="y" (
        git push -u origin main --force
        if %errorlevel% neq 0 (
            echo [错误] 强制推送也失败了，请检查配置
        ) else (
            echo [成功] 强制推送完成
        )
    )
) else (
    echo [成功] 推送完成!
)

:END
echo.
echo ============================================
echo   操作完成!
echo ============================================
echo.
echo [后续操作提示]
echo   - 查看状态: git status
echo   - 查看日志: git log --oneline
echo   - 拉取更新: git pull
echo   - 推送更新: git add . ^&^& git commit -m "更新" ^&^& git push
echo.
pause
