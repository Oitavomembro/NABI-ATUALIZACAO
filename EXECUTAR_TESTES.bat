@echo off
setlocal
cd /d "%~dp0"
set "PYTHON_CMD="
where py >nul 2>nul && set "PYTHON_CMD=py"
if not defined PYTHON_CMD where python >nul 2>nul && set "PYTHON_CMD=python"
if not defined PYTHON_CMD (
    echo ERRO: Python nao encontrado.
    exit /b 1
)
%PYTHON_CMD% developer_tools_cli.py tests
set RESULTADO=%ERRORLEVEL%
if not "%RESULTADO%"=="0" echo FALHA NOS TESTES.
exit /b %RESULTADO%
