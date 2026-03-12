"""
Modulo de filtrado de capas CAD.

Soporta:
- Lista negra por nombre exacto (case-insensitive)
- Lista blanca por nombre exacto (si se define, solo se incluyen esas capas)
- Exclusion por patrones regex
"""
import logging
import re
from typing import List

from app.config import AppConfig

logger = logging.getLogger(__name__)


class LayerFilter:
    """Filtra capas CAD segun reglas de inclusion/exclusion configurables."""

    def __init__(self, config: AppConfig):
        self.exclude_set = {l.strip().upper() for l in config.exclude_layers}
        self.include_set = {l.strip().upper() for l in config.include_layers}
        self.exclude_patterns = []
        for pattern in config.exclude_layer_patterns:
            try:
                self.exclude_patterns.append(re.compile(pattern, re.IGNORECASE))
            except re.error as e:
                logger.warning(f"Patron de exclusion invalido '{pattern}': {e}")

    def should_include(self, layer_name: str) -> bool:
        """
        Retorna True si la capa debe procesarse, False si debe excluirse.
        """
        name = layer_name.strip()
        upper = name.upper()

        # Lista blanca: si esta definida, solo se incluyen capas listadas
        if self.include_set and upper not in self.include_set:
            logger.debug(f"Capa excluida (no esta en lista blanca): '{layer_name}'")
            return False

        # Lista negra por nombre exacto
        if upper in self.exclude_set:
            logger.debug(f"Capa excluida (lista negra): '{layer_name}'")
            return False

        # Lista negra por patron regex
        for pat in self.exclude_patterns:
            if pat.search(name):
                logger.debug(f"Capa excluida (patron '{pat.pattern}'): '{layer_name}'")
                return False

        return True

    def get_stats(self) -> dict:
        return {
            "exclude_exact_count": len(self.exclude_set),
            "include_whitelist_count": len(self.include_set),
            "exclude_patterns_count": len(self.exclude_patterns),
        }
