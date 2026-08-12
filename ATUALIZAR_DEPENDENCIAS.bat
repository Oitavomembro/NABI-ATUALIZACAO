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

if not exist requirements.txt (
  echo ERRO: requirements.txt nao foi encontrado em:
  echo %CD%
  pause
  exit /b 1
)

%PYTHON_CMD% -m pip install --upgrade pip
if errorlevel 1 goto erro
%PYTHON_CMD% -m pip install --upgrade -r requirements.txt
if errorlevel 1 goto erro

echo Dependencias instaladas com sucesso.
exit /b 0

:erro
echo FALHA AO INSTALAR AS DEPENDENCIAS.
pause
exit /b 1
