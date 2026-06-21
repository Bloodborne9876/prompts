@echo off
:: 管理者権限で実行されているか確認し、なければ昇格して再起動
net session >nul 2>&1
if %errorlevel% neq 0 (
    powershell -Command "Start-Process '%~f0' -Verb RunAs"
    exit /b
)

powershell -ExecutionPolicy Bypass -File "%~dp0process_stop.ps1"
pause
