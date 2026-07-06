@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul
title Gold Monitor

cd /d "%~dp0"

if exist gold_monitor.pid (
    echo [WARN] PID file exists, checking if process is running...
    for /f %%i in (gold_monitor.pid) do (
        tasklist /FI "PID eq %%i" 2>nul | findstr /i "python" >nul
        if not errorlevel 1 (
            echo [INFO] Gold Monitor is already running (PID: %%i)
            pause
            exit /b
        )
    )
    del gold_monitor.pid
)

echo [INFO] Checking Python environment...

set BASE_PYTHON=python
where python >nul 2>&1
if errorlevel 1 (
    where python3 >nul 2>&1
    if not errorlevel 1 (
        set BASE_PYTHON=python3
    ) else (
        echo [ERROR] Python not found in PATH. Please install Python first.
        pause
        exit /b 1
    )
)

set PYTHON_CMD=.venv\Scripts\python.exe
if exist "!PYTHON_CMD!" (
    "!PYTHON_CMD!" --version >nul 2>&1
    if not errorlevel 1 (
        echo [INFO] Using virtual environment Python
        goto :deps_check
    )
    echo [WARN] .venv exists but Python is broken, recreating...
    rmdir /s /q .venv
)

echo [INFO] Creating virtual environment...
%BASE_PYTHON% -m venv .venv
if errorlevel 1 (
    echo [ERROR] Failed to create virtual environment
    pause
    exit /b 1
)
set PYTHON_CMD=.venv\Scripts\python.exe
echo [OK] Virtual environment created

:deps_check

echo [INFO] Upgrading pip...
!PYTHON_CMD! -m pip install --upgrade pip -i https://pypi.tuna.tsinghua.edu.cn/simple >nul 2>&1

echo [INFO] Installing dependencies...
!PYTHON_CMD! -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
if errorlevel 1 (
    echo [ERROR] Failed to install dependencies. Please check your network
    pause
    exit /b 1
)
echo [OK] Dependencies ready

echo [INFO] Starting Gold Monitor...

start "Gold Monitor" /B !PYTHON_CMD! gold_monitor_feishu.py

timeout /t 3 /nobreak >nul

for /f "tokens=2" %%i in ('tasklist /fi "WINDOWTITLE eq Gold Monitor" /fo list ^| findstr "PID"') do (
    echo %%i > gold_monitor.pid
    echo [OK] Gold Monitor started successfully (PID: %%i)
    echo [INFO] Log file: logs\gold_monitor.log
    goto :end
)

echo [ERROR] Failed to start Gold Monitor
echo [INFO] Check logs\gold_monitor.log for details

:end
echo.
pause
