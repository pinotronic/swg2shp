"""
Pruebas unitarias para el modulo crs_manager.
Requieren GDAL instalado; se omiten automaticamente si no esta disponible.
"""
import pytest

try:
    from osgeo import osr
    GDAL_AVAILABLE = True
except ImportError:
    GDAL_AVAILABLE = False

from app.crs_manager import build_srs, resolve_srs, reproject_geometry

pytestmark = pytest.mark.skipif(
    not GDAL_AVAILABLE, reason="GDAL no instalado"
)


class TestBuildSrs:
    def test_build_from_epsg_6369(self):
        srs = build_srs("EPSG:6369")
        assert srs is not None
        assert not srs.IsEmpty()

    def test_build_from_epsg_32614(self):
        srs = build_srs("EPSG:32614")
        assert srs is not None

    def test_invalid_epsg_raises(self):
        with pytest.raises(ValueError):
            build_srs("EPSG:999999999")

    def test_epsg_case_insensitive(self):
        srs = build_srs("epsg:6369")
        assert srs is not None


class TestResolveSrs:
    def test_no_source_no_dataset(self):
        source, target, needs = resolve_srs(None, "EPSG:6369", None, True)
        assert source is None
        assert target is not None
        assert needs is False

    def test_same_source_target_no_reproj(self):
        srs = build_srs("EPSG:6369")
        source, target, needs = resolve_srs("EPSG:6369", "EPSG:6369", srs, True)
        assert needs is False

    def test_different_crs_needs_reproj(self):
        srs_src = build_srs("EPSG:32614")
        source, target, needs = resolve_srs("EPSG:32614", "EPSG:6369", srs_src, True)
        assert needs is True

    def test_config_source_overrides_dataset(self):
        dataset_srs = build_srs("EPSG:4326")
        source, target, needs = resolve_srs("EPSG:32614", "EPSG:6369", dataset_srs, True)
        # Con assign_only_if_missing=True y config_source_crs definido,
        # se usa el config
        assert source is not None


class TestReprojectGeometry:
    def test_reproject_point(self):
        from osgeo import ogr
        # Punto en coordenadas geograficas (WGS84)
        geom = ogr.CreateGeometryFromWkt("POINT (-101.68 21.12)")
        src_srs = build_srs("EPSG:4326")
        tgt_srs = build_srs("EPSG:32614")
        result = reproject_geometry(geom, src_srs, tgt_srs)
        assert result is not None
        # En UTM 14N, las coordenadas X deben ser ~300000-700000
        x = result.GetX()
        assert 200000 < x < 800000

    def test_same_srs_returns_original(self):
        from osgeo import ogr
        geom = ogr.CreateGeometryFromWkt("POINT (100 200)")
        srs = build_srs("EPSG:6369")
        result = reproject_geometry(geom, srs, srs)
        assert result.GetX() == pytest.approx(100.0)

    def test_none_srs_returns_original(self):
        from osgeo import ogr
        geom = ogr.CreateGeometryFromWkt("POINT (100 200)")
        result = reproject_geometry(geom, None, None)
        assert result is geom
