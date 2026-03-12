# Build multiplataforma (Windows y Linux)

Este proyecto puede distribuirse de dos formas:

- Como ejecutable nativo por sistema operativo (PyInstaller).
- Como paquete Python instalable (wheel/sdist, ideal para Linux/CI).

## Requisitos

- GDAL debe existir en el entorno de build.
- Para Windows se recomienda usar el entorno local `.conda-gdal`.
- Para Linux se recomienda usar un entorno con `gdal` instalado por `apt`, `conda` o `mamba`.

## Windows (.exe)

Comando:

```powershell
./scripts/build_windows_exe.ps1
```

Salida esperada:

- `dist/dwg2shp/dwg2shp.exe`

## Linux (binario + paquete Python)

Comando:

```bash
chmod +x scripts/build_linux.sh
./scripts/build_linux.sh
```

Salida esperada:

- `dist/dwg2shp/dwg2shp` (binario Linux)
- `dist/*.whl` y `dist/*.tar.gz` (paquetes Python)

## Publicacion recomendada

- Windows: distribuir carpeta `dist/dwg2shp/` completa (no solo el `.exe`).
- Linux:
  - Si el cliente usa Python: publicar `.whl`.
  - Si el cliente no usa Python: distribuir carpeta `dist/dwg2shp/` generada en Linux.

## Nota importante

No se debe compilar un binario Linux desde Windows ni viceversa para produccion.
Cada binario debe construirse en su propio sistema operativo objetivo.
