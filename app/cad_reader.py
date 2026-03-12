"""
Modulo de lectura de archivos CAD usando GDAL/OGR.

Notas sobre el driver OGR para DXF:
- El dataset suele exponer una capa 'entities' con todas las entidades.
- Cada feature tiene un campo 'Layer' con el nombre de la capa CAD.
- El tipo de geometria OGR determina si es punto, linea o poligono.

Soporte DWG:
- Depende de la compilacion de GDAL (driver OGR_DWG o DWG no siempre disponible).
- Si no se puede abrir, se registra el error y se marca como 'fallido recuperable'.
"""
import logging
from pathlib import Path
from typing import Iterator, List, Optional, Tuple

logger = logging.getLogger(__name__)

try:
    from osgeo import ogr, gdal
    GDAL_AVAILABLE = True
except ImportError:
    GDAL_AVAILABLE = False
    logger.warning("GDAL/OGR no disponible. Instala las librerias con: conda install gdal")


def check_gdal() -> bool:
    """Retorna True si GDAL/OGR esta disponible."""
    return GDAL_AVAILABLE


def open_cad_dataset(path: Path) -> Tuple[object, str]:
    """
    Abre un archivo CAD y retorna (dataset, nombre_driver).

    Para DXF usa el driver 'DXF' directamente (mas estable).
    Para DWG intenta varios drivers disponibles.
    Si ninguno funciona lanza RuntimeError con instrucciones de recuperacion.
    """
    if not GDAL_AVAILABLE:
        raise RuntimeError(
            "GDAL no esta instalado.\n"
            "  conda: conda install -c conda-forge gdal\n"
            "  pip:   pip install gdal"
        )

    ext = path.suffix.lower()
    str_path = str(path)

    if ext == ".dxf":
        drivers_to_try = ["DXF"]
    elif ext == ".dwg":
        drivers_to_try = ["DWG", "OGR_DWG"]
    else:
        drivers_to_try = ["DXF", "DWG"]

    last_error: Optional[Exception] = None

    for driver_name in drivers_to_try:
        drv = ogr.GetDriverByName(driver_name)
        if drv is None:
            logger.debug(f"Driver '{driver_name}' no disponible en esta instalacion de GDAL")
            continue
        try:
            ds = drv.Open(str_path, 0)
            if ds is not None:
                logger.debug(f"Abierto '{path.name}' con driver '{driver_name}'")
                return ds, driver_name
        except Exception as e:
            last_error = e
            logger.debug(f"Driver '{driver_name}' fallo para '{path.name}': {e}")

    # Ultimo recurso: deteccion automatica de GDAL
    try:
        ds = ogr.Open(str_path, 0)
        if ds is not None:
            drv_name = ds.GetDriver().GetName() if ds.GetDriver() else "auto"
            logger.debug(f"Abierto '{path.name}' por auto-deteccion (driver: {drv_name})")
            return ds, drv_name
    except Exception as e:
        last_error = e

    msg = (
        f"No se pudo abrir '{path.name}' con ningun driver disponible. "
        f"Ultimo error: {last_error}."
    )
    if ext == ".dwg":
        msg += (
            "\nPara archivos DWG, considera preconvertir a DXF usando AutoCAD, "
            "FreeCAD u ODA File Converter."
        )
    raise RuntimeError(msg)


def list_ogr_layers(ds) -> List[str]:
    """Retorna los nombres de las capas OGR del dataset."""
    return [ds.GetLayer(i).GetName() for i in range(ds.GetLayerCount())]


def get_layer_field_names(ds, layer_idx: int = 0) -> List[str]:
    """Retorna los nombres de campos de atributos de una capa OGR."""
    layer = ds.GetLayer(layer_idx)
    if layer is None:
        return []
    defn = layer.GetLayerDefn()
    return [defn.GetFieldDefn(i).GetName() for i in range(defn.GetFieldCount())]


def get_feature_attributes(feat, field_names: List[str]) -> dict:
    """Extrae todos los atributos de un feature OGR."""
    attrs = {}
    for name in field_names:
        try:
            attrs[name] = feat.GetField(name)
        except Exception:
            attrs[name] = None
    return attrs


def iter_features(ds) -> Iterator[Tuple[object, str, str]]:
    """
    Itera sobre todas las features del dataset CAD.
    Yields: (ogr_feature, cad_layer_name, entity_type_str)

    En el driver DXF de OGR:
    - La capa OGR se llama 'entities' (o 'blocks')
    - Cada feature tiene el campo 'Layer' = nombre de capa CAD
    - 'SubClasses' puede indicar el tipo de entidad
    """
    for i in range(ds.GetLayerCount()):
        ogr_layer = ds.GetLayer(i)
        ogr_layer_name = ogr_layer.GetName().lower()

        # Omitir la capa de bloques (definitions, no instancias)
        if ogr_layer_name == "blocks":
            continue

        defn = ogr_layer.GetLayerDefn()
        field_names = [defn.GetFieldDefn(j).GetName() for j in range(defn.GetFieldCount())]

        ogr_layer.ResetReading()
        feat = ogr_layer.GetNextFeature()
        while feat is not None:
            cad_layer = _get_str_field(feat, field_names, ["Layer", "layer", "LAYER"], "0")
            entity_type = _get_str_field(feat, field_names, ["SubClasses", "EntityHandle", "Type"], "")
            yield feat, cad_layer, entity_type
            feat = ogr_layer.GetNextFeature()


def _get_str_field(feat, field_names: List[str], candidates: List[str], default: str) -> str:
    """Busca el primer campo disponible y retorna su valor como string."""
    for candidate in candidates:
        if candidate in field_names:
            val = feat.GetField(candidate)
            if val is not None:
                return str(val)
    return default
