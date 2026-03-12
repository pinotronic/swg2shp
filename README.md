# dwg2shp

Convertidor de archivos CAD (DWG/DXF) a Shapefile (.shp), separando entidades en:

- puntos
- lineas
- poligonos

Incluye filtrado por capas, configuracion de CRS, reportes por lote y modo CLI.

## Caracteristicas

- Conversion por lote de archivos `.dwg` y `.dxf`.
- Salida separada por tipo geometrico.
- Filtros por lista negra/lista blanca de capas.
- Reproyeccion por EPSG (origen/destino).
- Reporte JSON con resumen y detalle por archivo.
- Comando de diagnostico de entorno (`info`).

## Requisitos

- Python 3.9+
- GDAL/OGR disponible en el entorno de ejecucion
- Dependencia base de Python:
  - `pyyaml>=6.0`

Opcional:

- `shapely>=2.0` para limpieza geometrica avanzada.

## Instalacion (modo Python)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
```

Si quieres extras:

```powershell
pip install -e ".[dev,geometry]"
```

## Uso rapido

### 1) Informacion del entorno

```powershell
python -m app.main info
```

### 2) Escanear directorio de entrada

```powershell
python -m app.main scan --input .\entrada
```

### 3) Convertir CAD a Shapefile

```powershell
python -m app.main convert --input .\entrada --output .\salida
```

Opciones comunes:

```powershell
python -m app.main convert \
  --input .\entrada \
  --output .\salida \
  --config .\config.yml \
  --target-crs EPSG:32614 \
  --only-dxf \
  --workers 1
```

## Uso del ejecutable Windows

Si ya construiste el binario, ejecuta:

```powershell
.\dist\dwg2shp\dwg2shp.exe info
.\dist\dwg2shp\dwg2shp.exe convert --input .\entrada --output .\salida
```

Nota: distribuye la carpeta completa `dist/dwg2shp/`, no solo el `.exe`.

## Configuracion

El archivo [config.yml](config.yml) controla:

- `input_dir`, `output_dir`
- extensiones incluidas
- capas excluidas / patrones de exclusion
- reglas geometricas
- CRS origen/destino
- encoding y overwrite de salida
- workers y nivel de log

Los argumentos CLI tienen prioridad sobre el YAML.

## Salidas

Por cada archivo de entrada se generan hasta 3 shapefiles:

- `<base>_puntos.shp`
- `<base>_lineas.shp`
- `<base>_poligonos.shp`

Tambien se genera `batch_report.json` con:

- resumen de lote
- estatus por archivo (`ok`, `partial`, `failed`)
- conteos exportados y descartados
- warnings y errores

## Build

Consulta [BUILDING.md](BUILDING.md).

Resumen Windows:

```powershell
./scripts/build_windows_exe.ps1
```

Salida esperada:

- `dist/dwg2shp/dwg2shp.exe`

## Pruebas

```powershell
pytest -q
```

## Estructura principal

- [app](app): logica de lectura, clasificacion, limpieza, reproyeccion y escritura.
- [app/services/conversion_service.py](app/services/conversion_service.py): orquestacion del pipeline.
- [rules](rules): mapeos y reglas por defecto.
- [scripts](scripts): automatizacion de build.
- [tests](tests): pruebas unitarias e integracion.

## Licencia

Definir licencia del proyecto (pendiente).
