Param(
    [string]$CondaPrefix = "$PSScriptRoot/../.conda-gdal",
    [string]$AppName = "dwg2shp"
)

$ErrorActionPreference = "Stop"

$projectRoot = Resolve-Path "$PSScriptRoot/.."
$envPath = Resolve-Path $CondaPrefix
$pythonExe = Join-Path $envPath "python.exe"

if (-not (Test-Path $pythonExe)) {
    throw "No se encontro python en '$pythonExe'. Crea el entorno .conda-gdal primero."
}

Write-Host "[1/4] Instalando dependencias de build..."
& $pythonExe -m pip install --upgrade pip
& $pythonExe -m pip install -e ".[build]"

Write-Host "[2/4] Limpiando builds anteriores..."
$distDir = Join-Path $projectRoot "dist"
$buildDir = Join-Path $projectRoot "build"
$specFile = Join-Path $projectRoot "$AppName.spec"
if (Test-Path $distDir) { Remove-Item $distDir -Recurse -Force }
if (Test-Path $buildDir) { Remove-Item $buildDir -Recurse -Force }
if (Test-Path $specFile) { Remove-Item $specFile -Force }

Write-Host "[3/4] Generando ejecutable..."
Push-Location $projectRoot
& $pythonExe -m PyInstaller `
    --noconfirm `
    --clean `
    --console `
    --onedir `
    --name $AppName `
    --collect-submodules osgeo `
    --collect-data osgeo `
    --collect-binaries osgeo `
    --runtime-hook "scripts/pyinstaller_runtime_hook.py" `
    "app/main.py"
Pop-Location

Write-Host "[4/4] Build completado. Ejecutable en: dist/$AppName/$AppName.exe"
