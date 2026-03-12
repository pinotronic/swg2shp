"""
Pruebas unitarias para el modulo geometry_classifier.
Requieren GDAL instalado; se omiten automaticamente si no esta disponible.
"""
import pytest

try:
    from osgeo import ogr
    GDAL_AVAILABLE = True
except ImportError:
    GDAL_AVAILABLE = False

from app.config import GeometryRules
from app.geometry_classifier import classify_geometry

pytestmark = pytest.mark.skipif(
    not GDAL_AVAILABLE, reason="GDAL no instalado"
)


def _rules(**kwargs) -> GeometryRules:
    defaults = dict(
        closed_polyline_as_polygon=True,
        convert_blocks_to_points=True,
        snap_tolerance=0.01,
    )
    defaults.update(kwargs)
    return GeometryRules(**defaults)


class TestPointClassification:
    def test_wkb_point(self):
        geom = ogr.CreateGeometryFromWkt("POINT (10 20)")
        gtype, result = classify_geometry(geom, "POINT", _rules())
        assert gtype == "point"
        assert result is not None

    def test_multipoint(self):
        geom = ogr.CreateGeometryFromWkt("MULTIPOINT ((0 0), (1 1))")
        gtype, result = classify_geometry(geom, "POINT", _rules())
        assert gtype == "point"


class TestLineClassification:
    def test_linestring(self):
        geom = ogr.CreateGeometryFromWkt("LINESTRING (0 0, 1 1, 2 0)")
        gtype, result = classify_geometry(geom, "LINE", _rules())
        assert gtype == "line"

    def test_open_polyline_stays_line(self):
        geom = ogr.CreateGeometryFromWkt("LINESTRING (0 0, 1 0, 1 1, 2 1)")
        gtype, result = classify_geometry(geom, "LWPOLYLINE", _rules())
        assert gtype == "line"


class TestPolygonClassification:
    def test_polygon(self):
        geom = ogr.CreateGeometryFromWkt("POLYGON ((0 0, 1 0, 1 1, 0 1, 0 0))")
        gtype, result = classify_geometry(geom, "LWPOLYLINE", _rules())
        assert gtype == "polygon"

    def test_closed_linestring_converts_to_polygon(self):
        # Polilínea cerrada con al menos 4 puntos
        geom = ogr.CreateGeometryFromWkt("LINESTRING (0 0, 1 0, 1 1, 0 1, 0 0)")
        gtype, result = classify_geometry(geom, "LWPOLYLINE", _rules(closed_polyline_as_polygon=True))
        assert gtype == "polygon"

    def test_closed_linestring_stays_line_when_rule_off(self):
        geom = ogr.CreateGeometryFromWkt("LINESTRING (0 0, 1 0, 1 1, 0 1, 0 0)")
        gtype, result = classify_geometry(geom, "LWPOLYLINE", _rules(closed_polyline_as_polygon=False))
        assert gtype == "line"


class TestEdgeCases:
    def test_null_geometry(self):
        gtype, result = classify_geometry(None, "", _rules())
        assert gtype == "unknown"
        assert result is None

    def test_3d_geometry_flattened(self):
        geom = ogr.CreateGeometryFromWkt("POINT Z (10 20 30)")
        gtype, result = classify_geometry(geom, "POINT", _rules())
        assert gtype == "point"
        assert result is not None
        # Debe ser 2D
        assert result.GetGeometryType() in (ogr.wkbPoint, ogr.wkbPoint25D)

    def test_insert_entity_converts_to_point(self):
        geom = ogr.CreateGeometryFromWkt("POINT (5 10)")
        gtype, result = classify_geometry(geom, "INSERT", _rules(convert_blocks_to_points=True))
        assert gtype == "point"
