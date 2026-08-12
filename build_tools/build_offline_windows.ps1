$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Wheelhouse = Join-Path $Root "build_output\wheelhouse"
$BuildVenv = Join-Path $Root "build_output\.build-venv"
$Lock = Join-Path $PSScriptRoot "requirements-windows.lock"

if ($Root.Length -gt 80) {
    throw "Caminho do projeto excessivamente longo para o build Windows ($($Root.Length) caracteres). Use um caminho curto, por exemplo C:\NB\NabiCode."
}
Write-Host "Diretório canônico de build: $Root"

if (-not (Test-Path (Join-Path $Wheelhouse "SHA256SUMS.txt"))) {
    throw "Wheelhouse offline ausente ou sem SHA256SUMS.txt."
}

$WheelhouseRoot = [IO.Path]::GetFullPath($Wheelhouse).TrimEnd('\') + '\'
$ListedWheels = [System.Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
foreach ($Line in Get-Content (Join-Path $Wheelhouse "SHA256SUMS.txt")) {
    if ([String]::IsNullOrWhiteSpace($Line)) { continue }
    if ($Line -notmatch '^([0-9a-fA-F]{64})\s+\*?(.+)$') {
        throw "Linha inválida em wheelhouse\SHA256SUMS.txt: $Line"
    }
    $ExpectedHash = $Matches[1].ToLowerInvariant()
    $RelativeName = $Matches[2].Trim()
    $WheelPath = [IO.Path]::GetFullPath((Join-Path $Wheelhouse $RelativeName))
    if (-not $WheelPath.StartsWith($WheelhouseRoot, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Caminho inseguro em wheelhouse\SHA256SUMS.txt: $RelativeName"
    }
    if (-not (Test-Path -LiteralPath $WheelPath -PathType Leaf)) {
        throw "Arquivo listado no wheelhouse ausente: $RelativeName"
    }
    $ActualHash = (Get-FileHash -LiteralPath $WheelPath -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($ActualHash -ne $ExpectedHash) {
        throw "Hash divergente no wheelhouse: $RelativeName"
    }
    if ([IO.Path]::GetExtension($WheelPath) -ieq '.whl') {
        [void]$ListedWheels.Add([IO.Path]::GetFileName($WheelPath))
    }
}
foreach ($Wheel in Get-ChildItem -LiteralPath $Wheelhouse -Filter '*.whl' -File) {
    if (-not $ListedWheels.Contains($Wheel.Name)) {
        throw "Wheel sem hash registrado em SHA256SUMS.txt: $($Wheel.Name)"
    }
}
Write-Host "Wheelhouse validado por SHA-256: $($ListedWheels.Count) wheels."

if (Test-Path -LiteralPath $BuildVenv) {
    Remove-Item -LiteralPath $BuildVenv -Recurse -Force
}

python -m venv $BuildVenv
$Python = Join-Path $BuildVenv "Scripts\python.exe"
& $Python -m pip install --no-index --find-links $Wheelhouse --requirement $Lock
if ($LASTEXITCODE -ne 0) { throw "Falha ao instalar dependências do wheelhouse offline." }

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

Write-Host "Build onedir e instalador offline concluídos. A .build-venv é apenas de build e não será distribuída."
