@echo off
setlocal
cd /d "%~dp0"

set "PYTHON_CMD="
where py >nul 2>nul && set "PYTHON_CMD=py"
if not defined PYTHON_CMD where python >nul 2>nul && set "PYTHON_CMD=python"
if not defined PYTHON_CMD (
    echo.
    echo ERRO: Python nao encontrado.
    echo Instale o Python e marque "Add Python to PATH".
    pause
    exit /b 1
)

%PYTHON_CMD% build_tools\build_windows.py build
if errorlevel 1 goto erro
rem O build_windows.py executa: --startup-smoke-test --smoke-output
echo TESTE DE INICIALIZACAO DO EXE: OK
echo DISTRIBUICAO ONEDIR FINAL: build_output\dist
if /I not "%~1"=="/nopause" pause
exit /b 0
:erro
echo FALHA AO GERAR DISTRIBUICAO FINAL.
if /I not "%~1"=="/nopause" pause
exit /b 1
