"""
Pruebas unitarias para el modulo layer_filter.
"""
from app.layer_filter import LayerFilter
from app.config import AppConfig


def _make_filter(exclude=None, include=None, patterns=None) -> LayerFilter:
    cfg = AppConfig(
        exclude_layers=exclude or [],
        include_layers=include or [],
        exclude_layer_patterns=patterns or [],
    )
    return LayerFilter(cfg)


class TestBlacklist:
    def test_excludes_exact_match(self):
        f = _make_filter(exclude=["TEXT", "DIM"])
        assert not f.should_include("TEXT")
        assert not f.should_include("DIM")

    def test_case_insensitive_exclusion(self):
        f = _make_filter(exclude=["TEXT"])
        assert not f.should_include("text")
        assert not f.should_include("Text")
        assert not f.should_include("TEXT")

    def test_includes_unlisted_layer(self):
        f = _make_filter(exclude=["TEXT", "DIM"])
        assert f.should_include("TUBERIA")
        assert f.should_include("RED_AGUA_POTABLE")

    def test_empty_exclude_includes_all(self):
        f = _make_filter(exclude=[])
        assert f.should_include("CUALQUIER_CAPA")


class TestWhitelist:
    def test_whitelist_allows_listed(self):
        f = _make_filter(include=["TUBERIA", "VALVULAS"])
        assert f.should_include("TUBERIA")
        assert f.should_include("VALVULAS")

    def test_whitelist_blocks_unlisted(self):
        f = _make_filter(include=["TUBERIA"])
        assert not f.should_include("RED")
        assert not f.should_include("NODOS")

    def test_whitelist_case_insensitive(self):
        f = _make_filter(include=["TUBERIA"])
        assert f.should_include("tuberia")
        assert f.should_include("Tuberia")


class TestPatterns:
    def test_pattern_prefix_exclusion(self):
        f = _make_filter(patterns=["^TEXT_"])
        assert not f.should_include("TEXT_LABELS")
        assert not f.should_include("TEXT_NOTAS")
        assert f.should_include("TUBERIA_TEXTO")

    def test_pattern_suffix_exclusion(self):
        f = _make_filter(patterns=["_ANNO$"])
        assert not f.should_include("LAYER_ANNO")
        assert f.should_include("ANNOTATION_LAYER")

    def test_multiple_patterns(self):
        f = _make_filter(patterns=["^TEXT_", "^DIM_", "_ANNO$"])
        assert not f.should_include("TEXT_LABELS")
        assert not f.should_include("DIM_COTAS")
        assert not f.should_include("CAPA_ANNO")
        assert f.should_include("TUBERIA_PRINCIPAL")

    def test_invalid_pattern_does_not_crash(self):
        # Patron invalido debe ignorarse, no crashear
        f = _make_filter(patterns=["[invalid_regex"])
        assert f.should_include("TUBERIA")  # No crashea


class TestEdgeCases:
    def test_empty_layer_name(self):
        f = _make_filter(exclude=["0", ""])
        # La capa "0" es tipica en DXF para entidades sin capa asignada
        assert not f.should_include("0")

    def test_whitespace_layer_name(self):
        f = _make_filter(exclude=["TEXT"])
        # Nombres con espacios al inicio/fin se normalizan
        assert not f.should_include("  TEXT  ")
