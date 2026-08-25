$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Wheelhouse = Join-Path $Root "build_output\wheelhouse"
$Lock = Join-Path $PSScriptRoot "requirements-windows.lock"

if ((python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')") -ne "3.14") {
    throw "Python 3.14.x é obrigatório na máquina de build."
}

$Download = Join-Path $Root "build_output\wheelhouse-download"
if (Test-Path -LiteralPath $Download) { Remove-Item -LiteralPath $Download -Recurse -Force }
New-Item -ItemType Directory -Force -Path $Download | Out-Null
python -m pip download --only-binary=:all: --no-deps --require-hashes --dest $Download --requirement $Lock
if ($LASTEXITCODE -ne 0) { throw "Falha ao preparar wheelhouse." }
python -m build_tools.supply_chain $Lock $Download
if ($LASTEXITCODE -ne 0) { throw "Download não corresponde exatamente ao lock aprovado." }
if (Test-Path -LiteralPath $Wheelhouse) { Remove-Item -LiteralPath $Wheelhouse -Recurse -Force }
Move-Item -LiteralPath $Download -Destination $Wheelhouse

Write-Host "Wheelhouse criado. Copie-o com o projeto para a máquina de build offline."
