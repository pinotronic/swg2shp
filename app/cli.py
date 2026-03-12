"""
Interfaz de linea de comandos (CLI) para dwg2shp.

Subcomandos:
  convert  Convierte archivos DWG/DXF a Shapefile.
  scan     Escanea un directorio y lista archivos detectables.
  info     Muestra informacion del entorno (GDAL, Python, etc.).
"""
import argparse


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dwg2shp",
        description=(
            "Convertidor DWG/DXF a Shapefile (.shp)\n"
            "Separa geometrias en puntos, lineas y poligonos.\n"
            "Soporta configuracion de CRS, filtrado de capas y reportes."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
ejemplos:
  dwg2shp convert --input ./entrada --output ./salida
  dwg2shp convert --input ./entrada --output ./salida --config config.yml
  dwg2shp convert --input ./entrada --output ./salida --target-crs EPSG:32614
  dwg2shp scan --input ./entrada
  dwg2shp info
        """,
    )

    subparsers = parser.add_subparsers(dest="command", metavar="COMANDO")

    # ------------------------------------------------------------------
    # Subcomando: convert
    # ------------------------------------------------------------------
    convert = subparsers.add_parser(
        "convert",
        help="Convertir archivos DWG/DXF a Shapefile",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    convert.add_argument(
        "--input", "-i",
        required=True,
        metavar="DIRECTORIO",
        help="Directorio de entrada con archivos DWG/DXF",
    )
    convert.add_argument(
        "--output", "-o",
        required=True,
        metavar="DIRECTORIO",
        help="Directorio de salida para los Shapefiles generados",
    )
    convert.add_argument(
        "--config", "-c",
        metavar="ARCHIVO.yml",
        help="Archivo de configuracion YAML (opcional)",
    )
    convert.add_argument(
        "--source-crs",
        metavar="EPSG:XXXX",
        help="CRS de origen (ej: EPSG:6369). Sobreescribe el valor del config.",
    )
    convert.add_argument(
        "--target-crs",
        metavar="EPSG:XXXX",
        help="CRS de destino (ej: EPSG:32614). Sobreescribe el valor del config.",
    )
    convert.add_argument(
        "--overwrite",
        action="store_true",
        default=None,
        help="Sobreescribir Shapefiles de salida si ya existen",
    )
    convert.add_argument(
        "--only-dxf",
        action="store_true",
        help="Procesar solo archivos DXF (ignorar DWG)",
    )
    convert.add_argument(
        "--workers",
        type=int,
        default=None,
        metavar="N",
        help="Numero de workers para procesamiento paralelo (default: 1)",
    )
    convert.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default=None,
        metavar="NIVEL",
        help="Nivel de detalle del log: DEBUG, INFO, WARNING, ERROR",
    )
    convert.add_argument(
        "--log-file",
        metavar="ARCHIVO.log",
        help="Escribir log tambien a este archivo",
    )

    # ------------------------------------------------------------------
    # Subcomando: scan
    # ------------------------------------------------------------------
    scan = subparsers.add_parser(
        "scan",
        help="Escanear directorio y listar archivos DWG/DXF detectados",
    )
    scan.add_argument(
        "--input", "-i",
        required=True,
        metavar="DIRECTORIO",
        help="Directorio a escanear",
    )
    scan.add_argument(
        "--only-dxf",
        action="store_true",
        help="Listar solo archivos DXF",
    )

    # ------------------------------------------------------------------
    # Subcomando: info
    # ------------------------------------------------------------------
    subparsers.add_parser(
        "info",
        help="Mostrar informacion del entorno (GDAL, Shapely, Python)",
    )

    return parser


def apply_cli_overrides(config, args) -> object:
    """
    Aplica los argumentos CLI sobre la configuracion cargada desde YAML.
    Los argumentos CLI tienen prioridad.
    """
    if getattr(args, "input", None):
        config.input_dir = args.input
    if getattr(args, "output", None):
        config.output_dir = args.output
    if getattr(args, "source_crs", None):
        config.crs.source_crs = args.source_crs
    if getattr(args, "target_crs", None):
        config.crs.target_crs = args.target_crs
    if getattr(args, "overwrite", None) is not None and args.overwrite:
        config.output.overwrite = True
    if getattr(args, "only_dxf", False):
        config.include_extensions = [".dxf"]
    if getattr(args, "workers", None):
        config.workers = args.workers
    if getattr(args, "log_level", None):
        config.log_level = args.log_level
    return config
