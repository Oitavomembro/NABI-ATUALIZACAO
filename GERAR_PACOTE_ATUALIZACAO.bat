@echo off
setlocal
cd /d "%~dp0"
set "PYTHON_CMD="
where py >nul 2>&1 && set "PYTHON_CMD=py"
if not defined PYTHON_CMD where python >nul 2>&1 && set "PYTHON_CMD=python"
if not defined PYTHON_CMD (
  echo Python nao encontrado.
  pause
  exit /b 1
)
%PYTHON_CMD% gerar_pacote_atualizacao.py --minimum-source 2.4.36 --accepted-source 2.4.36
if errorlevel 1 (
  echo Falha ao gerar pacote.
  pause
  exit /b 1
)
echo Pacote gerado com sucesso.
pause
