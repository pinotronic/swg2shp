#!/usr/bin/env bash
set -euo pipefail

APP_NAME="dwg2shp"
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"

cd "$PROJECT_ROOT"

echo "[1/4] Instalando dependencias de build..."
"$PYTHON_BIN" -m pip install --upgrade pip
"$PYTHON_BIN" -m pip install -e ".[build]"

echo "[2/4] Generando artefactos Python (sdist + wheel)..."
"$PYTHON_BIN" -m build

echo "[3/4] Generando bundle Linux con PyInstaller..."
rm -rf build dist "${APP_NAME}.spec"
"$PYTHON_BIN" -m PyInstaller \
  --noconfirm \
  --clean \
  --console \
  --onedir \
  --name "$APP_NAME" \
  --collect-submodules osgeo \
  --collect-data osgeo \
  --collect-binaries osgeo \
  --runtime-hook "scripts/pyinstaller_runtime_hook.py" \
  "app/main.py"

echo "[4/4] Listo. Artefactos:"
echo " - Python package: dist/*.whl dist/*.tar.gz"
echo " - Linux binary: dist/${APP_NAME}/${APP_NAME}"
