"""
Modulo de reportes y observabilidad.

Genera:
- Log estructurado en consola y archivo.
- batch_report.json: resumen completo del lote.
- incidencias.csv: advertencias y errores por archivo.
"""
import csv
import json
import logging
import time
from pathlib import Path
from typing import Dict, Any, List, Optional

from app.models import ConversionResult


def setup_logging(log_level: str = "INFO", log_file: Optional[str] = None) -> None:
    """
    Configura el sistema de logging para la aplicacion.
    """
    level = getattr(logging, log_level.upper(), logging.INFO)

    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)-8s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    handlers: List[logging.Handler] = []

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    handlers.append(console_handler)

    if log_file:
        try:
            file_handler = logging.FileHandler(log_file, encoding="utf-8")
            file_handler.setFormatter(formatter)
            handlers.append(file_handler)
        except OSError as e:
            logging.warning(f"No se pudo crear el archivo de log '{log_file}': {e}")

    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Remover handlers anteriores para evitar duplicados
    for h in root_logger.handlers[:]:
        root_logger.removeHandler(h)
    for h in handlers:
        root_logger.addHandler(h)


def generate_batch_report(
    results: List[ConversionResult],
    output_dir: Path,
    start_time: float,
) -> Dict[str, Any]:
    """
    Genera el reporte de lote y lo escribe como JSON.
    Tambien genera el CSV de incidencias.
    Retorna el diccionario del reporte.
    """
    elapsed = time.time() - start_time

    total = len(results)
    ok = sum(1 for r in results if r.status == "ok")
    partial = sum(1 for r in results if r.status == "partial")
    failed = sum(1 for r in results if r.status == "failed")
    total_points = sum(r.points_exported for r in results)
    total_lines = sum(r.lines_exported for r in results)
    total_polygons = sum(r.polygons_exported for r in results)
    total_discarded = sum(r.features_discarded for r in results)
    total_warnings = sum(r.warnings_count for r in results)
    total_errors = sum(r.errors_count for r in results)

    report: Dict[str, Any] = {
        "batch_summary": {
            "total_files": total,
            "converted_ok": ok,
            "converted_partial": partial,
            "failed": failed,
            "total_points_exported": total_points,
            "total_lines_exported": total_lines,
            "total_polygons_exported": total_polygons,
            "features_discarded": total_discarded,
            "total_warnings": total_warnings,
            "total_errors": total_errors,
            "elapsed_seconds": round(elapsed, 2),
        },
        "files": [
            {
                "input_file": r.input_file,
                "status": r.status,
                "points_exported": r.points_exported,
                "lines_exported": r.lines_exported,
                "polygons_exported": r.polygons_exported,
                "features_discarded": r.features_discarded,
                "layers_excluded": r.layers_excluded,
                "warnings_count": r.warnings_count,
                "errors_count": r.errors_count,
                "processing_time_sec": round(r.processing_time, 3),
                "output_points": r.output_point_path,
                "output_lines": r.output_line_path,
                "output_polygons": r.output_polygon_path,
            }
            for r in results
        ],
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger(__name__)

    json_path = output_dir / "batch_report.json"
    try:
        json_path.write_text(
            json.dumps(report, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        logger.info(f"Reporte JSON escrito: {json_path}")
    except OSError as e:
        logger.error(f"No se pudo escribir batch_report.json: {e}")

    # CSV de incidencias
    incidencias = []
    for r in results:
        for msg in r.errors:
            incidencias.append({"archivo": r.input_file, "nivel": "ERROR", "mensaje": msg})
        for msg in r.warnings:
            incidencias.append({"archivo": r.input_file, "nivel": "WARNING", "mensaje": msg})

    if incidencias:
        csv_path = output_dir / "incidencias.csv"
        try:
            with open(csv_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=["archivo", "nivel", "mensaje"])
                writer.writeheader()
                writer.writerows(incidencias)
            logger.info(f"CSV de incidencias escrito: {csv_path} ({len(incidencias)} entradas)")
        except OSError as e:
            logger.error(f"No se pudo escribir incidencias.csv: {e}")

    return report


def print_batch_summary(report: Dict[str, Any]) -> None:
    """Imprime un resumen legible del lote en la consola."""
    s = report["batch_summary"]
    sep = "=" * 62
    print(f"\n{sep}")
    print("  RESUMEN DE LOTE — dwg2shp")
    print(sep)
    print(f"  Archivos detectados   : {s['total_files']}")
    print(f"  Convertidos OK        : {s['converted_ok']}")
    print(f"  Convertidos parcial   : {s['converted_partial']}")
    print(f"  Fallidos              : {s['failed']}")
    print(f"  ---")
    print(f"  Puntos exportados     : {s['total_points_exported']:,}")
    print(f"  Lineas exportadas     : {s['total_lines_exported']:,}")
    print(f"  Poligonos exportados  : {s['total_polygons_exported']:,}")
    print(f"  Features descartados  : {s['features_discarded']:,}")
    print(f"  ---")
    print(f"  Advertencias          : {s['total_warnings']}")
    print(f"  Errores               : {s['total_errors']}")
    print(f"  Tiempo total          : {s['elapsed_seconds']}s")
    print(sep)

    # Detalle por archivo si hay problemas
    files_with_issues = [
        f for f in report.get("files", [])
        if f["status"] != "ok"
    ]
    if files_with_issues:
        print("\n  Archivos con problemas:")
        for f in files_with_issues:
            print(
                f"  [{f['status'].upper():8s}] {Path(f['input_file']).name}"
                f" — errores:{f['errors_count']} advertencias:{f['warnings_count']}"
            )
        print()
