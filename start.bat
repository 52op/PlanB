@echo off
chcp 65001 >nul
echo ========================================
echo   宏旭绿建文档系统 - 启动脚本
echo ========================================
echo.

REM 检查虚拟环境
if not exist "venv\Scripts\activate.bat" (
    echo [错误] 未找到虚拟环境，请先运行: python -m venv venv
    pause
    exit /b 1
)

REM 激活虚拟环境
call venv\Scripts\activate.bat

REM 检查 waitress 是否安装
python -c "import waitress" 2>nul
if errorlevel 1 (
    echo [提示] 正在安装 waitress 高性能服务器...
    pip install waitress
    echo.
)

REM 启动应用
echo [启动] 正在启动应用...
echo.
python app.py

pause
