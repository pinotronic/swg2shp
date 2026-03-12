"""
Modulo de escaneo de directorios de entrada.
Localiza archivos DWG/DXF de forma recursiva.
"""
import logging
from pathlib import Path
from typing import List

from app.models import InputJob
from app.config import AppConfig

logger = logging.getLogger(__name__)


def scan_input_directory(config: AppConfig) -> List[InputJob]:
    """
    Escanea recursivamente el directorio de entrada y devuelve
    una lista de InputJob con los archivos detectados.

    Raises:
        FileNotFoundError: si el directorio no existe.
        NotADirectoryError: si la ruta no es un directorio.
    """
    root = Path(config.input_dir)

    if not root.exists():
        raise FileNotFoundError(f"Directorio de entrada no encontrado: {root}")
    if not root.is_dir():
        raise NotADirectoryError(f"La ruta de entrada no es un directorio: {root}")

    extensions = set(config.include_extensions)
    jobs: List[InputJob] = []

    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        ext = path.suffix.lower()
        if ext not in extensions:
            continue

        relative = str(path.relative_to(root))
        fmt = ext.lstrip(".")
        try:
            size = path.stat().st_size
        except OSError:
            size = 0

        jobs.append(InputJob(
            input_path=path,
            relative_path=relative,
            format=fmt,
            file_size=size,
        ))
        logger.debug(f"Detectado: {relative} ({size:,} bytes)")

    logger.info(f"Escaneo completo: {len(jobs)} archivo(s) encontrado(s) en '{root}'")
    return jobs
