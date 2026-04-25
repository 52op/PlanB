@echo off
setlocal EnableExtensions

cd /d "%~dp0"

echo ========================================
echo   Planning Onefile Build Script
echo ========================================
echo.

if exist "venv\Scripts\python.exe" (
    set "PYTHON_EXE=%CD%\venv\Scripts\python.exe"
) else (
    set "PYTHON_EXE=python"
)

echo [1/4] Using Python:
echo     %PYTHON_EXE%
echo.

"%PYTHON_EXE%" -c "import PyInstaller" >nul 2>nul
if errorlevel 1 (
    echo [2/4] PyInstaller not found. Installing...
    "%PYTHON_EXE%" -m pip install pyinstaller
    if errorlevel 1 (
        echo.
        echo ERROR: Failed to install PyInstaller.
        pause
        exit /b 1
    )
) else (
    echo [2/4] PyInstaller is already installed.
)

echo.
echo [3/4] Cleaning old build output...
if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"

echo.
echo [4/4] Building onefile exe...
"%PYTHON_EXE%" -m PyInstaller --clean --noconfirm planning.spec
if errorlevel 1 (
    echo.
    echo ERROR: Build failed.
    pause
    exit /b 1
)

echo.
echo Build completed successfully.
echo Output: dist\PlanB.exe
echo.
echo Notes:
echo   1. The exe will create a data\ folder next to itself on first run.
echo   2. To reset the admin password, create a .changepassword file
echo      next to the exe and start it again.
echo.
pause
