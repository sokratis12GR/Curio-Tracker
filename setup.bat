@echo off
SETLOCAL

where python >nul 2>nul
IF ERRORLEVEL 1 (
    echo.
    echo ❌ Python is not installed on this system.
    echo 🔄 Opening Python download page...
    start https://www.python.org/downloads/windows/
    pause
    exit /b
)

python -m ensurepip --default-pip
python -m pip install --upgrade pip
echo 📦 Installing required Python packages...
python -m pip install -r requirements.txt

echo.
echo ✅ All done! Press any key to close.
pause >nul