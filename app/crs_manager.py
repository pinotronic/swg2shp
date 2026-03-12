"""
Modulo de gestion de sistema de coordenadas (CRS) y reproyeccion.

Soporta:
- Asignacion de CRS si el archivo no tiene uno.
- Reproyeccion al CRS objetivo configurado.
- Escribe correctamente el archivo .prj.

Recomendacion para Leon, Guanajuato:
  EPSG:6369 — Mexico ITRF2008 / UTM zone 14N  (cartografia oficial Mexico)
  EPSG:32614 — WGS 84 / UTM zone 14N           (si el flujo ya es WGS84)
"""
import logging
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

try:
    from osgeo import osr, ogr
    GDAL_AVAILABLE = True
except ImportError:
    GDAL_AVAILABLE = False


def build_srs(epsg_or_wkt: str):
    """
    Construye un objeto SpatialReference desde EPSG (ej: 'EPSG:6369') o WKT.
    Lanza ValueError si no se puede importar.
    """
    if not GDAL_AVAILABLE:
        raise RuntimeError("GDAL no disponible")

    srs = osr.SpatialReference()
    token = epsg_or_wkt.strip()

    if token.upper().startswith("EPSG:"):
        epsg = int(token.split(":")[1])
        ret = srs.ImportFromEPSG(epsg)
        if ret != 0:
            raise ValueError(f"No se pudo importar EPSG: {epsg_or_wkt}")
    else:
        ret = srs.ImportFromWkt(token)
        if ret != 0:
            raise ValueError(f"No se pudo parsear el SRS WKT: {epsg_or_wkt[:80]}...")

    # GDAL >= 3: asegurar orden tradicional X,Y (lon/lat o E/N)
    try:
        srs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    except AttributeError:
        pass  # GDAL < 3, no necesario

    return srs


def get_dataset_srs(ds) -> Optional[object]:
    """
    Intenta obtener el SRS del dataset OGR (primera capa).
    Retorna None si no hay SRS definido.
    """
    if not GDAL_AVAILABLE:
        return None
    try:
        layer = ds.GetLayer(0)
        if layer:
            srs = layer.GetSpatialRef()
            if srs and not srs.IsEmpty():
                logger.debug(f"SRS del dataset: {srs.GetAuthorityCode(None)}")
                return srs
    except Exception as e:
        logger.debug(f"No se pudo obtener SRS del dataset: {e}")
    return None


def reproject_geometry(geom, source_srs, target_srs):
    """
    Reproyecta una geometria OGR de source_srs a target_srs.
    Retorna un clon reproyectado.
    """
    if source_srs is None or target_srs is None:
        return geom
    if source_srs.IsSame(target_srs):
        return geom

    try:
        transform = osr.CoordinateTransformation(source_srs, target_srs)
        cloned = geom.Clone()
        err = cloned.Transform(transform)
        if err != 0:
            logger.warning(f"Error de reproyeccion OGR: codigo {err}")
        return cloned
    except Exception as e:
        logger.warning(f"Reproyeccion fallo: {e}. Se devuelve geometria original.")
        return geom


def resolve_srs(
    config_source_crs: Optional[str],
    config_target_crs: str,
    dataset_srs,
    assign_only_if_missing: bool,
) -> Tuple[Optional[object], Optional[object], bool]:
    """
    Determina el SRS de origen y destino para un dataset.

    Retorna: (source_srs, target_srs, needs_reprojection)

    Logica:
    1. target_srs siempre se construye desde config_target_crs.
    2. source_srs:
       - Si assign_only_if_missing=False y hay dataset_srs -> usa dataset_srs.
       - Si hay config_source_crs configurado -> usa config_source_crs.
       - Si hay dataset_srs -> usa dataset_srs.
       - Si no hay nada -> asigna target sin reproyectar (advertencia).
    """
    if not GDAL_AVAILABLE:
        return None, None, False

    # Construir CRS objetivo
    try:
        target_srs = build_srs(config_target_crs)
    except ValueError as e:
        logger.error(f"CRS objetivo invalido '{config_target_crs}': {e}")
        return None, None, False

    # Determinar CRS origen
    if not assign_only_if_missing and dataset_srs is not None:
        source_srs = dataset_srs
        logger.debug("Usando SRS del dataset como origen (assign_only_if_missing=False)")
    elif config_source_crs:
        try:
            source_srs = build_srs(config_source_crs)
            logger.debug(f"Usando SRS configurado como origen: {config_source_crs}")
        except ValueError as e:
            logger.warning(f"CRS origen invalido '{config_source_crs}': {e}. Usando dataset SRS.")
            source_srs = dataset_srs
    elif dataset_srs is not None:
        source_srs = dataset_srs
        logger.debug("Usando SRS detectado del dataset como origen")
    else:
        logger.warning(
            "No se encontro ni se configuro CRS de origen. "
            "Se asignara el CRS objetivo sin reproyectar."
        )
        return None, target_srs, False

    needs_reprojection = not source_srs.IsSame(target_srs)
    if needs_reprojection:
        src_code = source_srs.GetAuthorityCode(None) or "desconocido"
        tgt_code = target_srs.GetAuthorityCode(None) or "desconocido"
        logger.info(f"Reproyeccion necesaria: {src_code} -> {tgt_code}")

    return source_srs, target_srs, needs_reprojection
