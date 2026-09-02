"""
Configuration commune aux tests.

Objectif : permettre à `pytest tests/` de passer sur un clone frais du dépôt,
sans que le dataset Nezha complet (plusieurs Go, non versionné) soit présent.

Stratégie :
- si data/ existe à la racine du projet, les tests l'utilisent ;
- sinon, ils basculent automatiquement sur tests/mini_data/, l'échantillon
  versionné dans le dépôt.

Le basculement se fait via la variable d'environnement DATA_PATH, lue par
PipelineComplet et prioritaire sur config.yaml.
"""

import os
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_COMPLET = PROJECT_ROOT / "data"
MINI_DATA = PROJECT_ROOT / "tests" / "mini_data"


def _dataset_utilisable(racine: Path) -> bool:
    """Vrai si racine/ contient réellement des données (pas un dossier vide)."""
    anomalies = racine / "anomalies"
    return anomalies.is_dir() and any(anomalies.iterdir())


DATASET_COMPLET_DISPONIBLE = _dataset_utilisable(DATA_COMPLET)

# Dataset réellement utilisé par les tests de cette session
DATA_DIR = DATA_COMPLET if DATASET_COMPLET_DISPONIBLE else MINI_DATA

# Rendre le choix visible pour tout le code qui lit DATA_PATH
os.environ["DATA_PATH"] = str(DATA_DIR)


@pytest.fixture(scope="session")
def data_dir() -> Path:
    """Racine des données utilisée par les tests (data/ ou tests/mini_data/)."""
    return DATA_DIR


@pytest.fixture(scope="session")
def dataset_complet() -> bool:
    """True si le dataset Nezha complet est disponible."""
    return DATASET_COMPLET_DISPONIBLE


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "requires_full_data: test qui exige le dataset Nezha complet (data/)",
    )


def pytest_collection_modifyitems(config, items):
    """Ignore proprement les tests qui exigent le dataset complet."""
    if DATASET_COMPLET_DISPONIBLE:
        return
    skip = pytest.mark.skip(reason="dataset Nezha complet absent (voir README, section Dataset)")
    for item in items:
        if "requires_full_data" in item.keywords:
            item.add_marker(skip)


def pytest_report_header(config):
    origine = "data/ (dataset complet)" if DATASET_COMPLET_DISPONIBLE else "tests/mini_data/ (échantillon)"
    return f"donnees de test : {origine}"
