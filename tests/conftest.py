"""
Permet a `pytest tests/` de passer sur un clone frais, sans le dataset Nezha.
Si data/ contient des donnees, il est utilise ; sinon on bascule sur
tests/mini_data/, l'echantillon versionne dans le depot.
"""

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_COMPLET = PROJECT_ROOT / "data"
MINI_DATA = PROJECT_ROOT / "tests" / "mini_data"


def _dataset_utilisable(racine: Path) -> bool:
    """Vrai si racine/ contient reellement des donnees (pas un dossier vide)."""
    anomalies = racine / "anomalies"
    return anomalies.is_dir() and any(anomalies.iterdir())


DATASET_COMPLET_DISPONIBLE = _dataset_utilisable(DATA_COMPLET)
DATA_DIR = DATA_COMPLET if DATASET_COMPLET_DISPONIBLE else MINI_DATA

# Lu par PipelineComplet, prioritaire sur config.yaml
os.environ["DATA_PATH"] = str(DATA_DIR)


def pytest_report_header(config):
    origine = "data/ (dataset complet)" if DATASET_COMPLET_DISPONIBLE else "tests/mini_data/ (echantillon)"
    return f"donnees de test : {origine}"
