"""Runtime hook para localizar datos de GDAL/PROJ dentro del bundle de PyInstaller."""
from __future__ import annotations

import os
import sys
from pathlib import Path


def _find_dir_with_marker(root: Path, marker: str) -> str | None:
    for candidate in root.rglob(marker):
        if candidate.is_file():
            return str(candidate.parent)
    return None


def _configure_gdal_env() -> None:
    meipass = getattr(sys, "_MEIPASS", None)
    if not meipass:
        return

    root = Path(meipass)

    if "GDAL_DATA" not in os.environ:
        gdal_data = _find_dir_with_marker(root, "gcs.csv")
        if gdal_data:
            os.environ["GDAL_DATA"] = gdal_data

    if "PROJ_LIB" not in os.environ:
        proj_lib = _find_dir_with_marker(root, "proj.db")
        if proj_lib:
            os.environ["PROJ_LIB"] = proj_lib


_configure_gdal_env()
