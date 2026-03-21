@echo off
chcp 65001 >nul
setlocal

echo ========================================
echo   Planning 单文件打包脚本
echo ========================================
echo.

if exist "venv\Scripts\python.exe" (
    set "PYTHON=venv\Scripts\python.exe"
) else (
    set "PYTHON=python"
)

%PYTHON% -c "import PyInstaller" 2>nul
if errorlevel 1 (
    echo [提示] 未检测到 PyInstaller，正在安装...
    %PYTHON% -m pip install pyinstaller
    if errorlevel 1 (
        echo [错误] PyInstaller 安装失败
        pause
        exit /b 1
    )
)

echo [清理] 删除旧的 build/dist 目录...
if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"

echo [打包] 开始生成单文件 exe...
%PYTHON% -m PyInstaller --clean --noconfirm planning.spec
if errorlevel 1 (
    echo.
    echo [错误] 打包失败
    pause
    exit /b 1
)

echo.
echo [完成] 打包成功：dist\planning.exe
echo [提示] 程序首次运行会在 exe 同目录自动创建 data\ 目录
echo [提示] 如需重置 admin 密码，请在 exe 同目录创建 .changepassword 后重新启动
echo.
pause
