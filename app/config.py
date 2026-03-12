"""
Carga y gestion de configuracion de la aplicacion.
"""
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Dict, Any

try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False


DEFAULT_EXCLUDE_LAYERS = [
    "TEXT", "DIM", "COTAS", "ANNO", "ANNOTATION",
    "LAYOUT", "VIEWPORT", "CARATULA", "CUADRO_DATOS",
    "SIMBOLOGIA", "TITLE", "TITLEBLOCK", "NOTES",
    "HATCH", "HATCHING", "DIMENSIONS", "DEFPOINTS",
    "LEADER", "MTEXT", "XREF", "TRAMAS", "TEXTOS",
    "ACOTACION",
]


@dataclass
class CrsConfig:
    source_crs: Optional[str] = None
    target_crs: str = "EPSG:6369"
    assign_only_if_missing: bool = True


@dataclass
class GeometryRules:
    closed_polyline_as_polygon: bool = True
    convert_blocks_to_points: bool = True
    snap_tolerance: float = 0.01


@dataclass
class OutputConfig:
    encoding: str = "UTF-8"
    overwrite: bool = True
    group_by_source_file: bool = True


@dataclass
class AppConfig:
    input_dir: str = "."
    output_dir: str = "./salida"
    include_extensions: List[str] = field(default_factory=lambda: [".dwg", ".dxf"])
    exclude_layers: List[str] = field(default_factory=list)
    exclude_layer_patterns: List[str] = field(default_factory=list)
    include_layers: List[str] = field(default_factory=list)
    geometry_rules: GeometryRules = field(default_factory=GeometryRules)
    crs: CrsConfig = field(default_factory=CrsConfig)
    output: OutputConfig = field(default_factory=OutputConfig)
    workers: int = 1
    log_level: str = "INFO"


def load_config(config_path: Optional[str] = None) -> AppConfig:
    """
    Carga la configuracion desde un archivo YAML.
    Si no se proporciona ruta, devuelve configuracion con valores por defecto.
    """
    raw: Dict[str, Any] = {}

    if config_path:
        path = Path(config_path)
        if not path.exists():
            raise FileNotFoundError(f"Archivo de configuracion no encontrado: {config_path}")
        if not YAML_AVAILABLE:
            raise ImportError("pyyaml no esta instalado. Ejecuta: pip install pyyaml")
        with open(path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}

    cfg = AppConfig()

    if "input_dir" in raw:
        cfg.input_dir = raw["input_dir"]
    if "output_dir" in raw:
        cfg.output_dir = raw["output_dir"]
    if "include_extensions" in raw:
        cfg.include_extensions = [str(e).lower() for e in raw["include_extensions"]]
    if "exclude_layers" in raw:
        cfg.exclude_layers = [str(l).upper() for l in raw["exclude_layers"]]
    if "exclude_layer_patterns" in raw:
        cfg.exclude_layer_patterns = list(raw["exclude_layer_patterns"])
    if "include_layers" in raw:
        cfg.include_layers = [str(l).upper() for l in raw["include_layers"]]
    if "workers" in raw:
        cfg.workers = int(raw["workers"])
    if "log_level" in raw:
        cfg.log_level = str(raw["log_level"]).upper()

    # Geometry rules
    gr = raw.get("geometry_rules", {})
    cfg.geometry_rules = GeometryRules(
        closed_polyline_as_polygon=gr.get("closed_polyline_as_polygon", True),
        convert_blocks_to_points=gr.get("convert_blocks_to_points", True),
        snap_tolerance=float(gr.get("snap_tolerance", 0.01)),
    )

    # CRS
    crs = raw.get("crs", {})
    cfg.crs = CrsConfig(
        source_crs=crs.get("source_crs") or None,
        target_crs=crs.get("target_crs", "EPSG:6369"),
        assign_only_if_missing=bool(crs.get("assign_only_if_missing", True)),
    )

    # Output
    out = raw.get("output", {})
    cfg.output = OutputConfig(
        encoding=out.get("encoding", "UTF-8"),
        overwrite=bool(out.get("overwrite", True)),
        group_by_source_file=bool(out.get("group_by_source_file", True)),
    )

    # Si no se configuraron capas excluidas, usar las de defecto
    if not cfg.exclude_layers:
        cfg.exclude_layers = DEFAULT_EXCLUDE_LAYERS.copy()

    return cfg
