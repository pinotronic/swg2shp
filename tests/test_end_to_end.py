"""
Prueba de integracion end-to-end.

Crea un archivo DXF minimo en memoria y verifica que el pipeline completo
genera Shapefiles de salida correctos.

Requiere GDAL instalado.
"""
import tempfile
from pathlib import Path

import pytest

try:
    from osgeo import ogr, gdal
    GDAL_AVAILABLE = True
except ImportError:
    GDAL_AVAILABLE = False

pytestmark = pytest.mark.skipif(
    not GDAL_AVAILABLE, reason="GDAL no instalado"
)


def create_minimal_dxf(path: Path) -> None:
    """Crea un DXF minimo con un punto, una linea y un poligono en capas distintas."""
    drv = ogr.GetDriverByName("DXF")
    if drv is None:
        pytest.skip("Driver DXF no disponible")

    ds = drv.CreateDataSource(str(path))
    if ds is None:
        pytest.skip("No se pudo crear DXF de prueba")

    layer = ds.CreateLayer("entities")

    # Punto en capa NODOS
    feat_pt = ogr.Feature(layer.GetLayerDefn())
    feat_pt.SetGeometry(ogr.CreateGeometryFromWkt("POINT (100 200)"))
    layer.CreateFeature(feat_pt)

    # Linea en capa TUBERIAS
    feat_ln = ogr.Feature(layer.GetLayerDefn())
    feat_ln.SetGeometry(ogr.CreateGeometryFromWkt("LINESTRING (0 0, 1 0, 2 1)"))
    layer.CreateFeature(feat_ln)

    # Poligono en capa MANZANAS
    feat_poly = ogr.Feature(layer.GetLayerDefn())
    feat_poly.SetGeometry(
        ogr.CreateGeometryFromWkt("POLYGON ((0 0, 10 0, 10 10, 0 10, 0 0))")
    )
    layer.CreateFeature(feat_poly)

    ds.FlushCache()
    ds = None


class TestEndToEnd:
    def test_full_pipeline_creates_shapefiles(self):
        """Verifica que el pipeline produce archivos SHP de salida."""
        from app.config import load_config
        from app.models import InputJob
        from app.services.conversion_service import process_file

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            dxf_path = tmp / "test_red.dxf"
            out_dir = tmp / "salida"

            create_minimal_dxf(dxf_path)

            config = load_config()
            config.output_dir = str(out_dir)
            config.exclude_layers = []  # No excluir capas en el test

            job = InputJob(
                input_path=dxf_path,
                relative_path="test_red.dxf",
                format="dxf",
                file_size=dxf_path.stat().st_size,
            )

            result = process_file(job, config)

            assert result.status != "failed", f"Pipeline fallo: {result.errors}"
            total = result.points_exported + result.lines_exported + result.polygons_exported
            assert total > 0, "No se exporto ninguna entidad"

    def test_result_has_output_paths(self):
        """Verifica que el resultado incluye rutas de salida."""
        from app.config import load_config
        from app.models import InputJob
        from app.services.conversion_service import process_file

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            dxf_path = tmp / "plano.dxf"
            out_dir = tmp / "salida"

            create_minimal_dxf(dxf_path)

            config = load_config()
            config.output_dir = str(out_dir)
            config.exclude_layers = []

            job = InputJob(
                input_path=dxf_path,
                relative_path="plano.dxf",
                format="dxf",
                file_size=dxf_path.stat().st_size,
            )

            result = process_file(job, config)

            # Al menos uno de los tres tipos de output debe existir
            outputs = [
                result.output_point_path,
                result.output_line_path,
                result.output_polygon_path,
            ]
            assert any(p is not None for p in outputs)
