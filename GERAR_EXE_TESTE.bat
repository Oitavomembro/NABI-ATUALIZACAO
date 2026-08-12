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
  echo ERRO: requirements.txt nao encontrado.
  goto erro
)
%PYTHON_CMD% -m pip install -r requirements.txt
if errorlevel 1 goto erro
%PYTHON_CMD% developer_tools_cli.py validate
if errorlevel 1 goto erro
set /p VERSAO=<VERSAO.txt
set NOME=NabiCode_v%VERSAO:.=_%_TESTE
%PYTHON_CMD% -m unittest discover -s tests -v
if errorlevel 1 goto erro
%PYTHON_CMD% -m PyInstaller --noconfirm --clean --name %NOME% --onedir --windowed --add-data "VERSAO.txt;." --collect-all customtkinter main.py
if errorlevel 1 goto erro
set "SMOKE_FILE=%TEMP%\nabicode_%NOME%_smoke.txt"
del /q "%SMOKE_FILE%" >nul 2>nul
"dist\%NOME%\%NOME%.exe" --startup-smoke-test --smoke-output "%SMOKE_FILE%"
if errorlevel 1 goto erro
if not exist "%SMOKE_FILE%" goto erro
findstr /x /c:"%VERSAO%" "%SMOKE_FILE%" >nul
if errorlevel 1 goto erro
del /q "%SMOKE_FILE%" >nul 2>nul
echo TESTE DE INICIALIZACAO DO EXE: OK
echo EXE TESTE: dist\%NOME%\%NOME%.exe
pause
exit /b 0
:erro
echo FALHA AO GERAR EXE DE TESTE.
pause
exit /b 1
