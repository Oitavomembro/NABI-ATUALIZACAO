$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Wheelhouse = Join-Path $Root "build_output\wheelhouse"
$Lock = Join-Path $PSScriptRoot "requirements-windows.lock"

if ((python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')") -ne "3.14") {
    throw "Python 3.14.x é obrigatório na máquina de build."
}

New-Item -ItemType Directory -Force -Path $Wheelhouse | Out-Null
python -m pip download --only-binary=:all: --dest $Wheelhouse --requirement $Lock
if ($LASTEXITCODE -ne 0) { throw "Falha ao preparar wheelhouse." }

Get-ChildItem $Wheelhouse -File | Sort-Object Name | ForEach-Object {
    $Hash = (Get-FileHash $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
    "$Hash  $($_.Name)"
} | Set-Content -Encoding ascii (Join-Path $Wheelhouse "SHA256SUMS.txt")

Write-Host "Wheelhouse criado. Copie-o com o projeto para a máquina de build offline."
