@echo off
python --version >nul 2>&1
if errorlevel 1 (
    echo Python not found. Please install Python from https://python.org
    pause
    exit /b 1
)
python -m pip install -r "%~dp0requirements.txt" --quiet
python "%~dp0__main__.py"
if errorlevel 1 pause
