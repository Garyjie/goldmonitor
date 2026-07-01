@echo off
chcp 65001 >nul
title Restart Gold Monitor

cd /d "%~dp0"

echo [INFO] Restarting Gold Monitor...
echo.

if exist gold_monitor.pid (
    set /p PID=<gold_monitor.pid
    echo [INFO] Stopping old process (PID: %PID%)...
    taskkill /PID %PID% /F >nul 2>&1
    del gold_monitor.pid
    timeout /t 2 /nobreak >nul
)

echo [INFO] Starting Gold Monitor...

if exist ".venv\Scripts\python.exe" (
    start "Gold Monitor" /B ".venv\Scripts\python.exe" gold_monitor_feishu.py
) else (
    start "Gold Monitor" /B python gold_monitor_feishu.py
)

timeout /t 3 /nobreak >nul

for /f "tokens=2" %%i in ('tasklist /fi "WINDOWTITLE eq Gold Monitor" /fo list ^| findstr "PID"') do (
    echo %%i > gold_monitor.pid
    echo [OK] Gold Monitor restarted successfully (PID: %%i)
    echo [INFO] Log file: logs\gold_monitor.log
    goto :end
)

echo [ERROR] Failed to start Gold Monitor

:end
echo.
pause
