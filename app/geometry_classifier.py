"""
Clasificador de geometrias CAD a tipos compatibles con Shapefile.

Mapea tipos de geometria OGR a: 'point', 'line', 'polygon', 'unknown'.
Aplica reglas configurables como: polilínea cerrada -> polígono, INSERT -> punto.
"""
import logging
from typing import Optional, Tuple

from app.config import GeometryRules

logger = logging.getLogger(__name__)

try:
    from osgeo import ogr
    # Mapa de tipo OGR -> tipo geometrico GIS
    _GEOM_TYPE_MAP = {
        ogr.wkbPoint:              "point",
        ogr.wkbMultiPoint:         "point",
        ogr.wkbPoint25D:           "point",
        ogr.wkbMultiPoint25D:      "point",
        ogr.wkbLineString:         "line",
        ogr.wkbMultiLineString:    "line",
        ogr.wkbLineString25D:      "line",
        ogr.wkbMultiLineString25D: "line",
        ogr.wkbPolygon:            "polygon",
        ogr.wkbMultiPolygon:       "polygon",
        ogr.wkbPolygon25D:         "polygon",
        ogr.wkbMultiPolygon25D:    "polygon",
    }
    GDAL_AVAILABLE = True
except ImportError:
    _GEOM_TYPE_MAP = {}
    GDAL_AVAILABLE = False


def classify_geometry(
    geom,
    entity_type: str,
    rules: GeometryRules,
) -> Tuple[str, Optional[object]]:
    """
    Clasifica una geometria OGR y retorna (tipo_geometrico, geometria_normalizada).

    Tipos posibles: 'point', 'line', 'polygon', 'unknown'.
    La geometria devuelta siempre es 2D para compatibilidad con Shapefile.
    """
    if geom is None:
        return "unknown", None

    if geom.IsEmpty():
        return "unknown", None

    # Aplanar a 2D (Shapefile no soporta Z nativamente)
    geom_2d = geom.Clone()
    geom_2d.FlattenTo2D()

    geom_type = geom_2d.GetGeometryType()

    # Mapeo directo por tipo OGR
    if geom_type in _GEOM_TYPE_MAP:
        classified = _GEOM_TYPE_MAP[geom_type]

        # Regla: polilínea cerrada -> polígono
        if classified == "line" and rules.closed_polyline_as_polygon:
            if _is_closed_linestring(geom_2d):
                polygon = _linestring_to_polygon(geom_2d)
                if polygon is not None:
                    logger.debug("Polilínea cerrada convertida a polígono")
                    return "polygon", polygon

        return classified, geom_2d

    # Coleccion de geometrias: clasificar por el primer sub-elemento
    if GDAL_AVAILABLE:
        try:
            if geom_type in (ogr.wkbGeometryCollection, ogr.wkbGeometryCollection25D):
                return _classify_collection(geom_2d, entity_type, rules)
        except Exception as e:
            logger.debug(f"Error clasificando coleccion: {e}")

    # Regla: INSERT/bloque -> punto si la opcion esta activa
    if rules.convert_blocks_to_points and "INSERT" in entity_type.upper():
        try:
            centroid = geom_2d.Centroid()
            if centroid and not centroid.IsEmpty():
                return "point", centroid
        except Exception:
            pass

    logger.debug(f"Geometria no clasificada: OGR type={geom_type}, entity='{entity_type}'")
    return "unknown", geom_2d


def _is_closed_linestring(geom) -> bool:
    """Verifica si un LineString es cerrado (primer == ultimo punto)."""
    if not GDAL_AVAILABLE:
        return False
    try:
        if geom.GetGeometryType() not in (ogr.wkbLineString, ogr.wkbLineString25D):
            return False
        n = geom.GetPointCount()
        if n < 4:  # Un poligono valido necesita al menos 4 puntos (3 + cierre)
            return False
        x0, y0 = geom.GetX(0), geom.GetY(0)
        xn, yn = geom.GetX(n - 1), geom.GetY(n - 1)
        return abs(x0 - xn) < 1e-9 and abs(y0 - yn) < 1e-9
    except Exception:
        return False


def _linestring_to_polygon(geom) -> Optional[object]:
    """Convierte un LineString cerrado en un Polygon."""
    if not GDAL_AVAILABLE:
        return None
    try:
        ring = ogr.Geometry(ogr.wkbLinearRing)
        for i in range(geom.GetPointCount()):
            ring.AddPoint_2D(geom.GetX(i), geom.GetY(i))
        poly = ogr.Geometry(ogr.wkbPolygon)
        poly.AddGeometry(ring)
        if poly.IsValid() and not poly.IsEmpty():
            return poly
    except Exception as e:
        logger.debug(f"linestring_to_polygon fallo: {e}")
    return None


def _classify_collection(geom, entity_type: str, rules: GeometryRules) -> Tuple[str, Optional[object]]:
    """Clasifica una coleccion de geometrias usando el primer sub-elemento."""
    try:
        n = geom.GetGeometryCount()
        if n == 0:
            return "unknown", None
        sub = geom.GetGeometryRef(0)
        if sub:
            return classify_geometry(sub.Clone(), entity_type, rules)
    except Exception as e:
        logger.debug(f"Error en _classify_collection: {e}")
    return "unknown", geom
