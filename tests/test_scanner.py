"""
Pruebas unitarias para el modulo scanner.
"""
import tempfile
from pathlib import Path

import pytest

from app.scanner import scan_input_directory
from app.config import AppConfig


def _make_cfg(tmpdir: str, extensions=None) -> AppConfig:
    cfg = AppConfig(input_dir=tmpdir)
    if extensions:
        cfg.include_extensions = extensions
    return cfg


def test_scan_finds_dxf_files():
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        (root / "plano.dxf").touch()
        (root / "readme.txt").touch()

        jobs = scan_input_directory(_make_cfg(tmpdir))
        assert len(jobs) == 1
        assert jobs[0].format == "dxf"


def test_scan_finds_dwg_files():
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        (root / "dibujo.dwg").touch()

        jobs = scan_input_directory(_make_cfg(tmpdir))
        assert len(jobs) == 1
        assert jobs[0].format == "dwg"


def test_scan_recursive():
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        (root / "a.dxf").touch()
        sub = root / "sub"
        sub.mkdir()
        (sub / "b.dxf").touch()
        (sub / "sub2").mkdir()
        (sub / "sub2" / "c.dxf").touch()

        jobs = scan_input_directory(_make_cfg(tmpdir))
        assert len(jobs) == 3


def test_scan_empty_directory():
    with tempfile.TemporaryDirectory() as tmpdir:
        jobs = scan_input_directory(_make_cfg(tmpdir))
        assert len(jobs) == 0


def test_scan_nonexistent_directory_raises():
    cfg = AppConfig(input_dir="/ruta/inexistente/xyz123")
    with pytest.raises(FileNotFoundError):
        scan_input_directory(cfg)


def test_scan_only_dxf_filter():
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        (root / "plano.dxf").touch()
        (root / "dibujo.dwg").touch()

        cfg = _make_cfg(tmpdir, extensions=[".dxf"])
        jobs = scan_input_directory(cfg)
        assert len(jobs) == 1
        assert jobs[0].format == "dxf"


def test_scan_relative_path():
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        sub = root / "proyecto" / "planos"
        sub.mkdir(parents=True)
        (sub / "red.dxf").touch()

        jobs = scan_input_directory(_make_cfg(tmpdir))
        assert len(jobs) == 1
        assert "red.dxf" in jobs[0].relative_path
