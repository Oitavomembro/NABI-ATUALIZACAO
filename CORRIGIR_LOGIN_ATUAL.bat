@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if not errorlevel 1 (
  py -3 CORRIGIR_LOGIN_ATUAL.py
) else (
  python CORRIGIR_LOGIN_ATUAL.py
)
pause
