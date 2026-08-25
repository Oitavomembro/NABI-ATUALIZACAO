$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Wheelhouse = Join-Path $Root "build_output\wheelhouse"
$BuildVenv = Join-Path $Root "build_output\.build-venv"
$Lock = Join-Path $PSScriptRoot "requirements-windows.lock"

if ($Root.Length -gt 80) {
    throw "Caminho do projeto excessivamente longo para o build Windows ($($Root.Length) caracteres). Use um caminho curto, por exemplo C:\NB\NabiCode."
}
Write-Host "Diretório canônico de build: $Root"

if (-not (Test-Path -LiteralPath $Lock -PathType Leaf)) {
    throw "Lock aprovado ausente."
}
python -m build_tools.supply_chain $Lock $Wheelhouse
if ($LASTEXITCODE -ne 0) { throw "Wheelhouse não corresponde exatamente ao lock aprovado." }
python -m build_tools.third_party_notices
if ($LASTEXITCODE -ne 0) { throw "Avisos/licenças de terceiros ausentes ou sem revisão aprovada." }

if (Test-Path -LiteralPath $BuildVenv) {
    Remove-Item -LiteralPath $BuildVenv -Recurse -Force
}

python -m venv $BuildVenv
$Python = Join-Path $BuildVenv "Scripts\python.exe"
& $Python -m pip install --no-index --find-links $Wheelhouse --only-binary=:all: --no-deps --require-hashes --requirement $Lock
if ($LASTEXITCODE -ne 0) { throw "Falha ao instalar dependências do wheelhouse offline." }

$Sbom = Join-Path $Root "build_output\SBOM.cyclonedx.json"
& (Join-Path $BuildVenv "Scripts\cyclonedx-py.exe") requirements $Lock --spec-version 1.6 --output-reproducible --output-format JSON --output-file $Sbom --validate
if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $Sbom -PathType Leaf)) {
    throw "Falha ao gerar/validar o SBOM CycloneDX com a ferramenta homologada."
}

Push-Location $Root
try {
    & $Python -m compileall -q .
    if ($LASTEXITCODE -ne 0) { throw "Compileall reprovado antes do build." }

    & $Python -m pytest -q
    if ($LASTEXITCODE -ne 0) { throw "Suíte reprovada antes do build." }

    & $Python (Join-Path $PSScriptRoot "build_windows.py") build
    if ($LASTEXITCODE -ne 0) { throw "Build Windows reprovado." }

    & $Python (Join-Path $PSScriptRoot "build_windows.py") installer
    if ($LASTEXITCODE -ne 0) { throw "Instalador offline reprovado." }
}
finally {
    Pop-Location
}

Write-Host "Build onedir, instalador offline e SBOM CycloneDX concluídos. A .build-venv é apenas de build e não será distribuída."
