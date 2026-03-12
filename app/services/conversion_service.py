"""
Servicio de conversion: orquesta el pipeline completo para un archivo CAD.

Pipeline:
  1. Apertura del archivo CAD
  2. Resolucion de CRS
  3. Iteracion de features
  4. Filtrado de capas
  5. Clasificacion geometrica
  6. Limpieza geometrica
  7. Reproyeccion (si aplica)
  8. Escritura de Shapefile
  9. Cierre y estadisticas
"""
import logging
import time
from pathlib import Path
from typing import Set

from app.models import InputJob, ConversionResult
from app.config import AppConfig
from app.cad_reader import (
    open_cad_dataset,
    iter_features,
    get_layer_field_names,
    get_feature_attributes,
)
from app.layer_filter import LayerFilter
from app.geometry_classifier import classify_geometry
from app.geometry_cleaner import clean_geometry
from app.crs_manager import resolve_srs, reproject_geometry, get_dataset_srs
from app.shapefile_writer import ShapefileWriter

logger = logging.getLogger(__name__)

# Cuantas advertencias por archivo se guardan en el resultado
_MAX_WARNINGS_IN_RESULT = 50


def process_file(job: InputJob, config: AppConfig) -> ConversionResult:
    """
    Procesa un archivo CAD completo a traves del pipeline y retorna
    un ConversionResult con las estadisticas y rutas de salida.

    Tolerante a errores: un fallo en una feature no detiene el proceso.
    Solo errores globales (no poder abrir el archivo, error de escritura
    critico) marcan el resultado como 'failed'.
    """
    start = time.time()
    result = ConversionResult(input_file=str(job.input_path))
    output_dir = Path(config.output_dir)

    layer_filter = LayerFilter(config)

    # ---------------------------------------------------------------
    # Paso 1: Abrir el archivo CAD
    # ---------------------------------------------------------------
    try:
        ds, driver_used = open_cad_dataset(job.input_path)
        logger.info(f"Abierto: '{job.input_path.name}' (driver: {driver_used})")
    except RuntimeError as e:
        logger.error(f"No se pudo abrir '{job.input_path.name}': {e}")
        result.status = "failed"
        result.errors.append(str(e))
        result.errors_count = 1
        result.processing_time = time.time() - start
        return result

    # ---------------------------------------------------------------
    # Paso 2: Resolver CRS
    # ---------------------------------------------------------------
    source_srs = None
    target_srs = None
    needs_reprojection = False
    try:
        dataset_srs = get_dataset_srs(ds)
        source_srs, target_srs, needs_reprojection = resolve_srs(
            config.crs.source_crs,
            config.crs.target_crs,
            dataset_srs,
            config.crs.assign_only_if_missing,
        )
    except Exception as e:
        msg = f"Error resolviendo CRS: {e}"
        logger.warning(msg)
        result.warnings.append(msg)
        result.warnings_count += 1

    # ---------------------------------------------------------------
    # Paso 3: Obtener esquema de atributos
    # ---------------------------------------------------------------
    try:
        field_names = get_layer_field_names(ds, 0)
    except Exception:
        field_names = []

    # ---------------------------------------------------------------
    # Paso 4: Inicializar el escritor de Shapefile
    # ---------------------------------------------------------------
    base_name = job.input_path.stem
    writer = ShapefileWriter(
        output_dir=output_dir,
        base_name=base_name,
        target_srs=target_srs,
        encoding=config.output.encoding,
        overwrite=config.output.overwrite,
    )

    # ---------------------------------------------------------------
    # Paso 5: Iterar features
    # ---------------------------------------------------------------
    features_read = 0
    features_discarded = 0
    layers_excluded_set: Set[str] = set()

    try:
        for feat, cad_layer, entity_type in iter_features(ds):
            features_read += 1

            # Filtrado de capas
            if not layer_filter.should_include(cad_layer):
                layers_excluded_set.add(cad_layer)
                features_discarded += 1
                continue

            # Geometria
            geom = feat.GetGeometryRef()
            if geom is None:
                features_discarded += 1
                continue

            # Clasificacion
            geom_type, normalized_geom = classify_geometry(
                geom, entity_type, config.geometry_rules
            )
            if geom_type == "unknown" or normalized_geom is None:
                features_discarded += 1
                logger.debug(
                    f"Feature no clasificada: capa='{cad_layer}' entidad='{entity_type}'"
                )
                continue

            # Limpieza
            cleaned_geom, clean_warnings = clean_geometry(
                normalized_geom,
                geom_type,
                config.geometry_rules.snap_tolerance,
            )
            if cleaned_geom is None:
                features_discarded += 1
                continue

            # Reproyeccion
            if needs_reprojection and source_srs and target_srs:
                try:
                    cleaned_geom = reproject_geometry(cleaned_geom, source_srs, target_srs)
                except Exception as e:
                    clean_warnings.append(f"Reproyeccion fallo: {e}")

            # Atributos
            attrs = get_feature_attributes(feat, field_names)
            attrs["source_file"] = job.input_path.name
            attrs["source_layer"] = cad_layer
            attrs["entity_type"] = entity_type

            # Escritura
            success = writer.write_feature(geom_type, cleaned_geom, attrs, clean_warnings)
            if not success:
                features_discarded += 1
            else:
                if clean_warnings:
                    result.warnings_count += len(clean_warnings)
                    if len(result.warnings) < _MAX_WARNINGS_IN_RESULT:
                        result.warnings.extend(
                            [f"[{cad_layer}] {w}" for w in clean_warnings[:3]]
                        )

    except Exception as e:
        msg = f"Error en pipeline: {e}"
        logger.error(f"{msg} — archivo: '{job.input_path.name}'", exc_info=True)
        result.errors.append(msg)
        result.errors_count += 1

    # ---------------------------------------------------------------
    # Paso 6: Finalizar
    # ---------------------------------------------------------------
    counts = writer.get_counts()
    writer.close()

    # Liberar dataset GDAL
    try:
        ds = None
    except Exception:
        pass

    output_paths = writer.get_output_paths()
    result.output_point_path = output_paths.get("point")
    result.output_line_path = output_paths.get("line")
    result.output_polygon_path = output_paths.get("polygon")
    result.points_exported = counts.get("point", 0)
    result.lines_exported = counts.get("line", 0)
    result.polygons_exported = counts.get("polygon", 0)
    result.features_discarded = features_discarded
    result.layers_excluded = len(layers_excluded_set)
    result.processing_time = time.time() - start

    total_exported = result.points_exported + result.lines_exported + result.polygons_exported

    if result.errors_count > 0 and total_exported == 0:
        result.status = "failed"
    elif result.errors_count > 0 or result.warnings_count > 0:
        result.status = "partial"
    else:
        result.status = "ok"

    logger.info(
        f"Completado: '{job.input_path.name}' | "
        f"pts={result.points_exported:,} "
        f"lin={result.lines_exported:,} "
        f"poly={result.polygons_exported:,} "
        f"descartados={features_discarded} "
        f"capas_excluidas={result.layers_excluded} "
        f"tiempo={result.processing_time:.2f}s "
        f"estado={result.status}"
    )

    if layers_excluded_set:
        logger.debug(f"  Capas excluidas: {sorted(layers_excluded_set)}")

    return result
