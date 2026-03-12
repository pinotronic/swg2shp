"""
Punto de entrada principal de dwg2shp.

Uso:
  python -m app.main convert --input ./entrada --output ./salida
  python -m app.main scan --input ./entrada
  python -m app.main info
"""
import sys
import time
import logging
from pathlib import Path

from app.cli import build_parser, apply_cli_overrides
from app.config import load_config
from app.scanner import scan_input_directory
from app.reporting import setup_logging, generate_batch_report, print_batch_summary
from app.cad_reader import check_gdal

logger = logging.getLogger(__name__)


# -----------------------------------------------------------------------
# Subcomando: info
# -----------------------------------------------------------------------

def cmd_info() -> int:
    """Muestra informacion del entorno de ejecucion."""
    import platform

    print("\ndwg2shp — informacion del entorno")
    print("=" * 50)
    print(f"  Python        : {platform.python_version()}")
    print(f"  Plataforma    : {platform.platform()}")

    # GDAL
    try:
        from osgeo import gdal, ogr
        print(f"  GDAL          : {gdal.__version__}")
        dxf_drv = ogr.GetDriverByName("DXF")
        dwg_drv = ogr.GetDriverByName("DWG") or ogr.GetDriverByName("OGR_DWG")
        print(f"  Driver DXF    : {'si' if dxf_drv else 'NO disponible'}")
        print(f"  Driver DWG    : {'si' if dwg_drv else 'NO disponible (solo DXF)'}")
        shp_drv = ogr.GetDriverByName("ESRI Shapefile")
        print(f"  Driver SHP    : {'si' if shp_drv else 'NO disponible'}")
    except ImportError:
        print("  GDAL          : NO instalado")
        print("    Instala con: conda install -c conda-forge gdal")

    # Shapely
    try:
        import shapely
        print(f"  Shapely       : {shapely.__version__}")
    except ImportError:
        print("  Shapely       : no instalado (opcional — pip install shapely)")

    # PyYAML
    try:
        import yaml
        print(f"  PyYAML        : {yaml.__version__}")
    except ImportError:
        print("  PyYAML        : NO instalado — pip install pyyaml")

    print("=" * 50)
    return 0


# -----------------------------------------------------------------------
# Subcomando: scan
# -----------------------------------------------------------------------

def cmd_scan(args) -> int:
    """Escanea un directorio y muestra los archivos detectados."""
    from app.config import AppConfig

    setup_logging("INFO")
    cfg = AppConfig(input_dir=args.input)
    if getattr(args, "only_dxf", False):
        cfg.include_extensions = [".dxf"]

    try:
        jobs = scan_input_directory(cfg)
    except (FileNotFoundError, NotADirectoryError) as e:
        print(f"\nError: {e}", file=sys.stderr)
        return 1

    if not jobs:
        print("No se encontraron archivos DWG/DXF en el directorio especificado.")
        return 0

    total_size = sum(j.file_size for j in jobs)
    print(f"\nArchivos encontrados: {len(jobs)}  (total: {total_size/1024:.1f} KB)\n")

    max_path_len = max(len(j.relative_path) for j in jobs)
    fmt = f"  {{:<6}} {{:<{max_path_len}}}  {{:>12}}"

    print(fmt.format("TIPO", "RUTA", "TAMAÑO"))
    print("  " + "-" * (max_path_len + 22))
    for j in jobs:
        print(fmt.format(
            f"[{j.format.upper()}]",
            j.relative_path,
            f"{j.file_size:,} bytes",
        ))
    print()
    return 0


# -----------------------------------------------------------------------
# Subcomando: convert
# -----------------------------------------------------------------------

def cmd_convert(args) -> int:
    """Convierte archivos DWG/DXF a Shapefile."""
    # Cargar configuracion base
    config_path = getattr(args, "config", None)
    try:
        config = load_config(config_path)
    except (FileNotFoundError, ImportError) as e:
        print(f"\nError cargando configuracion: {e}", file=sys.stderr)
        return 1

    # Aplicar overrides CLI
    config = apply_cli_overrides(config, args)

    # Setup logging
    log_file = getattr(args, "log_file", None)
    setup_logging(config.log_level, log_file)

    # Verificar GDAL
    if not check_gdal():
        print(
            "\nError: GDAL/OGR no esta instalado.\n"
            "  conda: conda install -c conda-forge gdal\n"
            "  pip:   pip install gdal\n",
            file=sys.stderr,
        )
        return 2

    logger.info("dwg2shp iniciando conversion...")
    logger.info(f"  Entrada   : {config.input_dir}")
    logger.info(f"  Salida    : {config.output_dir}")
    logger.info(f"  CRS obj.  : {config.crs.target_crs}")
    logger.info(f"  Workers   : {config.workers}")

    # Escaneo
    try:
        jobs = scan_input_directory(config)
    except (FileNotFoundError, NotADirectoryError) as e:
        logger.error(str(e))
        return 1

    if not jobs:
        logger.warning("No se encontraron archivos para procesar.")
        print("\nNo se encontraron archivos DWG/DXF en el directorio de entrada.")
        return 0

    logger.info(f"Archivos a procesar: {len(jobs)}")

    # Procesamiento
    start_time = time.time()
    results = []

    if config.workers > 1:
        results = _process_parallel(jobs, config)
    else:
        for idx, job in enumerate(jobs, 1):
            logger.info(f"[{idx}/{len(jobs)}] Procesando: {job.relative_path}")
            from app.services.conversion_service import process_file
            result = process_file(job, config)
            results.append(result)

    # Reporte
    report_dir = Path(config.output_dir)
    report = generate_batch_report(results, report_dir, start_time)
    print_batch_summary(report)

    summary = report["batch_summary"]
    all_failed = summary["failed"] == summary["total_files"]
    return 1 if all_failed else 0


def _process_parallel(jobs, config) -> list:
    """Procesamiento paralelo usando ProcessPoolExecutor."""
    from concurrent.futures import ProcessPoolExecutor, as_completed
    from app.services.conversion_service import process_file
    from app.models import ConversionResult

    results = []
    with ProcessPoolExecutor(max_workers=config.workers) as executor:
        future_to_job = {
            executor.submit(process_file, job, config): job
            for job in jobs
        }
        for future in as_completed(future_to_job):
            job = future_to_job[future]
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                logger.error(f"Worker error para '{job.input_path.name}': {e}")
                results.append(ConversionResult(
                    input_file=str(job.input_path),
                    status="failed",
                    errors=[str(e)],
                    errors_count=1,
                ))
    return results


# -----------------------------------------------------------------------
# Punto de entrada
# -----------------------------------------------------------------------

def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    if args.command == "info":
        sys.exit(cmd_info())
    elif args.command == "scan":
        sys.exit(cmd_scan(args))
    elif args.command == "convert":
        sys.exit(cmd_convert(args))
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
