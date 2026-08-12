@echo off
cd /d "%~dp0"
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
for /d /r %%D in (__pycache__) do @if exist "%%D" rmdir /s /q "%%D"
echo BUILD LIMPO.
pause
