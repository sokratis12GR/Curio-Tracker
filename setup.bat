@echo off
SETLOCAL

where python >nul 2>nul
IF ERRORLEVEL 1 (
    echo.
    echo Python is not installed on this system.
    echo Opening Python download page...
    start https://www.python.org/downloads/windows/
    pause
    exit /b
)

echo Python found.
echo Creating virtual environment...
python -m venv venv

if NOT EXIST venv\Scripts\activate.bat (
    echo Failed to create virtual environment.
    pause
    exit /b
)

echo Activating virtual environment...
call venv\Scripts\activate.bat

echo Installing required packages...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

echo.
echo Setup complete. Virtual environment is ready.
echo To activate it manually later, run: venv\Scripts\activate
pause