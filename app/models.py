"""
Modelos de datos internos del pipeline de conversion DWG/DXF -> SHP.
"""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List, Dict, Any


@dataclass
class InputJob:
    """Representa un archivo CAD a procesar."""
    input_path: Path
    relative_path: str
    format: str          # 'dwg' o 'dxf'
    file_size: int       # bytes


@dataclass
class FeatureRecord:
    """Representa una entidad geometrica leida del archivo CAD."""
    source_file: str
    source_layer: str
    entity_type: str
    geometry_type: str   # 'point', 'line', 'polygon', 'unknown'
    geometry: Any        # objeto OGR Geometry
    attributes: Dict[str, Any]
    warnings: List[str] = field(default_factory=list)


@dataclass
class LayerStats:
    """Estadisticas de procesamiento por capa CAD."""
    name: str
    features_read: int = 0
    features_excluded: int = 0
    features_classified: int = 0
    features_exported: int = 0


@dataclass
class ConversionResult:
    """Resultado de la conversion de un archivo CAD."""
    input_file: str
    status: str = "pending"          # 'ok', 'partial', 'failed', 'pending'
    output_point_path: Optional[str] = None
    output_line_path: Optional[str] = None
    output_polygon_path: Optional[str] = None
    warnings_count: int = 0
    errors_count: int = 0
    points_exported: int = 0
    lines_exported: int = 0
    polygons_exported: int = 0
    features_discarded: int = 0
    layers_excluded: int = 0
    processing_time: float = 0.0
    summary: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
