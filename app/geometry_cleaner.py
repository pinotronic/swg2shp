"""
Modulo de limpieza y validacion de geometrias.

Estrategia:
1. Si Shapely esta disponible: validacion robusta con make_valid().
2. Si no: usa el truco buffer(0) de OGR para corregir geometrias invalidas.

IMPORTANTE: No toda reparacion se hace automaticamente.
Las que no se pueden corregir se registran como advertencias para revision humana.
"""
import logging
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)

try:
    from osgeo import ogr
    GDAL_AVAILABLE = True
except ImportError:
    GDAL_AVAILABLE = False

try:
    from shapely import wkt as shapely_wkt
    from shapely.validation import make_valid
    SHAPELY_AVAILABLE = True
except ImportError:
    SHAPELY_AVAILABLE = False


def clean_geometry(
    geom,
    geometry_type: str,
    snap_tolerance: float = 0.01,
) -> Tuple[Optional[object], List[str]]:
    """
    Limpia y valida una geometria OGR.
    Retorna (geometria_limpia, lista_de_advertencias).
    Si la geometria no puede recuperarse, retorna (None, advertencias).
    """
    warnings: List[str] = []

    if geom is None:
        return None, ["Geometria nula"]

    if geom.IsEmpty():
        return None, ["Geometria vacia"]

    if SHAPELY_AVAILABLE:
        return _clean_with_shapely(geom, geometry_type, warnings)

    return _clean_ogr_only(geom, geometry_type, warnings)


def _clean_with_shapely(geom, geometry_type: str, warnings: List[str]) -> Tuple[Optional[object], List[str]]:
    """Usa Shapely para validar y reparar la geometria."""
    try:
        wkt = geom.ExportToWkt()
        shp_geom = shapely_wkt.loads(wkt)

        if not shp_geom.is_valid:
            reason = _shapely_validation_reason(shp_geom)
            warnings.append(f"Geometria invalida, reparando: {reason}")
            shp_geom = make_valid(shp_geom)

        if shp_geom.is_empty:
            return None, warnings + ["Geometria vacia despues de reparacion"]

        # Validaciones especificas por tipo
        if geometry_type == "polygon":
            if hasattr(shp_geom, "area") and shp_geom.area < 1e-10:
                warnings.append("Poligono con area casi cero")
        elif geometry_type == "line":
            if hasattr(shp_geom, "length") and shp_geom.length < 1e-6:
                warnings.append("Linea extremadamente corta (posible duplicado o artefacto)")

        # Reconvertir a OGR
        from osgeo import ogr as _ogr
        cleaned = _ogr.CreateGeometryFromWkt(shp_geom.wkt)
        if cleaned is None:
            warnings.append("No se pudo reconvertir a OGR despues de reparacion Shapely")
            return geom, warnings
        return cleaned, warnings

    except Exception as e:
        warnings.append(f"Error en limpieza Shapely: {e}")
        return geom, warnings


def _clean_ogr_only(geom, geometry_type: str, warnings: List[str]) -> Tuple[Optional[object], List[str]]:
    """Limpieza basica usando solo OGR (sin Shapely)."""
    try:
        if not geom.IsValid():
            warnings.append("Geometria invalida (OGR), aplicando buffer(0)")
            buffered = geom.Buffer(0)
            if buffered and not buffered.IsEmpty():
                return buffered, warnings
            warnings.append("buffer(0) no pudo reparar la geometria")
            return geom, warnings  # Retornar original con advertencia, no descartar
        return geom, warnings
    except Exception as e:
        warnings.append(f"Error en limpieza OGR: {e}")
        return geom, warnings


def _shapely_validation_reason(geom) -> str:
    """Obtiene la razon de invalidez de una geometria Shapely."""
    try:
        from shapely.validation import explain_validity
        return explain_validity(geom)
    except Exception:
        return "razon desconocida"


def detect_duplicate_indices(wkt_list: List[str]) -> List[int]:
    """
    Recibe una lista de WKT strings y retorna los indices duplicados.
    El primero de cada grupo NO se marca como duplicado.
    """
    seen = set()
    duplicates = []
    for i, wkt in enumerate(wkt_list):
        if wkt in seen:
            duplicates.append(i)
        else:
            seen.add(wkt)
    return duplicates
