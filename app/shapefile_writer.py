"""
Modulo de escritura de Shapefiles.

Genera tres archivos de salida por cada archivo CAD procesado:
  - nombre_base_puntos.shp
  - nombre_base_lineas.shp
  - nombre_base_poligonos.shp

Cada uno incluye: .shp, .shx, .dbf, .prj, .cpg
"""
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

try:
    from osgeo import ogr
    GDAL_AVAILABLE = True
except ImportError:
    GDAL_AVAILABLE = False

# Esquema de atributos de salida.
# Formato: (nombre_campo, tipo_ogr_nombre, ancho_maximo)
# Nombres limitados a 10 caracteres por la especificacion Shapefile/DBF.
FIELD_SCHEMA = [
    ("src_file",  "OFTString", 254),
    ("src_layer", "OFTString", 100),
    ("ent_type",  "OFTString",  50),
    ("feat_id",   "OFTString",  50),
    ("blk_name",  "OFTString", 100),
    ("color",     "OFTString",  20),
    ("linetype",  "OFTString",  50),
    ("status",    "OFTString",  20),
    ("obs",       "OFTString", 254),
]

SUFFIX_MAP = {
    "point":   "puntos",
    "line":    "lineas",
    "polygon": "poligonos",
}

WKB_TYPE_MAP = {
    "point":   1,  # wkbPoint
    "line":    2,  # wkbLineString
    "polygon": 3,  # wkbPolygon
}


class ShapefileWriter:
    """
    Administra la escritura de features a Shapefiles separados por tipo geometrico.
    Uso:
        writer = ShapefileWriter(output_dir, base_name, target_srs)
        writer.write_feature("point", geom, attrs, warnings)
        writer.close()
    """

    def __init__(
        self,
        output_dir: Path,
        base_name: str,
        target_srs,
        encoding: str = "UTF-8",
        overwrite: bool = True,
    ):
        self.output_dir = output_dir
        self.base_name = _safe_name(base_name)
        self.target_srs = target_srs
        self.encoding = encoding
        self.overwrite = overwrite
        self._datasets: Dict[str, object] = {}
        self._layers: Dict[str, object] = {}
        self._counts: Dict[str, int] = {"point": 0, "line": 0, "polygon": 0}

    def write_feature(
        self,
        geom_type: str,
        geometry,
        attributes: Dict[str, Any],
        warnings: List[str],
    ) -> bool:
        """
        Escribe una feature en el shapefile correspondiente al tipo geometrico.
        Retorna True si tuvo exito.
        """
        if not GDAL_AVAILABLE:
            return False
        try:
            layer = self._get_or_create_layer(geom_type)
            feat = ogr.Feature(layer.GetLayerDefn())
            feat.SetGeometry(geometry)

            feat.SetField("src_file",  _trunc(str(attributes.get("source_file",  "")), 254))
            feat.SetField("src_layer", _trunc(str(attributes.get("source_layer", "")), 100))
            feat.SetField("ent_type",  _trunc(str(attributes.get("entity_type",  "")),  50))
            feat.SetField("feat_id",   _trunc(str(attributes.get("EntityHandle", "")),  50))
            feat.SetField("blk_name",  _trunc(str(attributes.get("BlockName",    "")), 100))
            feat.SetField("color",     _trunc(str(attributes.get("Color",        "")),  20))
            feat.SetField("linetype",  _trunc(str(attributes.get("Linetype",     "")),  50))
            feat.SetField("status",    "warn" if warnings else "ok")
            feat.SetField("obs",       _trunc("; ".join(warnings), 254))

            err = layer.CreateFeature(feat)
            if err != 0:
                logger.warning(f"CreateFeature error {err} para tipo '{geom_type}'")
                return False

            self._counts[geom_type] = self._counts.get(geom_type, 0) + 1
            return True

        except Exception as e:
            logger.error(f"Error escribiendo feature ({geom_type}): {e}")
            return False

    def get_output_paths(self) -> Dict[str, Optional[str]]:
        """Retorna las rutas de los SHP generados (None si no se crearon)."""
        paths: Dict[str, Optional[str]] = {}
        for geom_type, suffix in SUFFIX_MAP.items():
            p = self.output_dir / f"{self.base_name}_{suffix}.shp"
            paths[geom_type] = str(p) if p.exists() else None
        return paths

    def get_counts(self) -> Dict[str, int]:
        return dict(self._counts)

    def close(self):
        """Vacia y cierra todos los datasets abiertos."""
        for ds in self._datasets.values():
            try:
                ds.FlushCache()
            except Exception:
                pass
        self._datasets.clear()
        self._layers.clear()

    def _get_or_create_layer(self, geom_type: str):
        """Obtiene o crea el layer/dataset para el tipo geometrico indicado."""
        if geom_type in self._layers:
            return self._layers[geom_type]

        if not GDAL_AVAILABLE:
            raise RuntimeError("GDAL no disponible")

        suffix = SUFFIX_MAP.get(geom_type, geom_type)
        shp_name = f"{self.base_name}_{suffix}.shp"
        shp_path = self.output_dir / shp_name

        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Eliminar archivos existentes si overwrite=True
        if self.overwrite and shp_path.exists():
            for ext in (".shp", ".shx", ".dbf", ".prj", ".cpg"):
                p = shp_path.with_suffix(ext)
                if p.exists():
                    try:
                        p.unlink()
                    except OSError as e:
                        logger.warning(f"No se pudo eliminar {p}: {e}")

        drv = ogr.GetDriverByName("ESRI Shapefile")
        if drv is None:
            raise RuntimeError("Driver 'ESRI Shapefile' no disponible en GDAL")

        ds = drv.CreateDataSource(str(shp_path))
        if ds is None:
            raise RuntimeError(f"No se pudo crear el Shapefile: {shp_path}")

        wkb_type = WKB_TYPE_MAP.get(geom_type, ogr.wkbUnknown)

        layer = ds.CreateLayer(
            self.base_name[:10],  # Nombre de capa limitado a 10 chars
            srs=self.target_srs,
            geom_type=wkb_type,
            options=[f"ENCODING={self.encoding}"],
        )
        if layer is None:
            raise RuntimeError(f"No se pudo crear la capa en {shp_path}")

        # Agregar campos segun esquema
        for field_name, field_type_name, field_width in FIELD_SCHEMA:
            field_type = getattr(ogr, field_type_name)
            fd = ogr.FieldDefn(field_name, field_type)
            fd.SetWidth(field_width)
            layer.CreateField(fd)

        # Escribir .cpg para indicar codificacion
        cpg_path = shp_path.with_suffix(".cpg")
        try:
            cpg_path.write_text(self.encoding, encoding="ascii")
        except OSError as e:
            logger.warning(f"No se pudo escribir .cpg: {e}")

        self._datasets[geom_type] = ds
        self._layers[geom_type] = layer
        logger.debug(f"Shapefile creado: {shp_path}")
        return layer


def _safe_name(name: str) -> str:
    """Reemplaza caracteres no validos en nombres de archivo."""
    import re
    safe = re.sub(r'[<>:"/\\|?*\s]', "_", name)
    return safe[:100] if safe else "output"


def _trunc(value: str, max_len: int) -> str:
    """Trunca un string al maximo permitido por el campo DBF."""
    return value[:max_len] if value else ""
