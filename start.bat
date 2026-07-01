@echo off
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

echo [INFO] Starting Gold Monitor...

if exist ".venv\Scripts\python.exe" (
    start "Gold Monitor" /B ".venv\Scripts\python.exe" gold_monitor_feishu.py
) else (
    start "Gold Monitor" /B python gold_monitor_feishu.py
)

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
