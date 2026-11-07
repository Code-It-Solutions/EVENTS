@echo off
REM KAYO Desktop App Build Script for Windows
REM This script builds KAYO into a standalone Windows executable

echo ============================================
echo    KAYO Desktop App Builder
echo ============================================
echo.

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    pause
    exit /b 1
)

REM Check if venv exists, if not create it
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
)

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat

REM Install/upgrade dependencies
echo Installing dependencies...
pip install -r requirements.txt
pip install pyinstaller

REM Build the executable
echo.
echo Building KAYO Desktop App...
echo This may take a few minutes...
echo.

pyinstaller kayo.spec --clean

if errorlevel 1 (
    echo.
    echo ERROR: Build failed!
    pause
    exit /b 1
)

echo.
echo ============================================
echo    Build Complete!
echo ============================================
echo.
echo The KAYO.exe file is located in: dist\KAYO.exe
echo.
echo You can distribute this file to users.
echo Make sure to include the 'instance' folder with the database.
echo.
pause
