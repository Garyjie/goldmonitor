@echo off
chcp 65001 >nul
title Stop Gold Monitor

cd /d "%~dp0"

if not exist gold_monitor.pid (
    echo [INFO] No PID file found, searching for Gold Monitor process...
    for /f "tokens=2" %%i in ('tasklist /fi "WINDOWTITLE eq Gold Monitor" /fo list ^| findstr "PID"') do (
        echo %%i > gold_monitor.pid
    )
)

if not exist gold_monitor.pid (
    echo [WARN] Gold Monitor is not running
    pause
    exit /b
)

set /p PID=<gold_monitor.pid

echo [INFO] Stopping Gold Monitor (PID: %PID%)...

tasklist /FI "PID eq %PID%" 2>nul | findstr /i "python" >nul
if errorlevel 1 (
    echo [WARN] Process %PID% is not running
    del gold_monitor.pid
    pause
    exit /b
)

taskkill /PID %PID% /F >nul 2>&1

if not errorlevel 1 (
    echo [OK] Gold Monitor stopped successfully
    del gold_monitor.pid
) else (
    echo [ERROR] Failed to stop Gold Monitor
)

echo.
pause
