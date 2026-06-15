@echo off
chcp 65001 >nul
title PC Media Remote Server

cd /d "%~dp0"

:: 检查 Python
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未找到 Python，请先安装 Python 3.12+
    echo 下载地址: https://www.python.org/downloads/
    pause
    exit /b 1
)

:: 检查依赖
python -c "import flask" >nul 2>&1
if %errorlevel% neq 0 (
    echo [信息] 正在安装依赖...
    pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
    if %errorlevel% neq 0 (
        echo [错误] 依赖安装失败
        pause
        exit /b 1
    )
)

:: 启动服务器
echo.
echo ╔══════════════════════════════════╗
echo ║   PC Media Remote 启动中...     ║
echo ║   关闭此窗口将停止服务           ║
echo ╚══════════════════════════════════╝
echo.

python app.py

pause
