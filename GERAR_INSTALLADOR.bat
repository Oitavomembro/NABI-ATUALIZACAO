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
%PYTHON_CMD% build_tools\build_windows.py installer
exit /b %ERRORLEVEL%
