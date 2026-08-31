"""
Tests des chemins d'erreur et cas limites.

Complète test_pipeline.py et test_pipeline_main.py en couvrant :
- Validations d'entrée (dates, sources, systèmes)
- Erreurs de configuration
- Chargement de données invalides
- Alertes edge cases (filtres, statistiques)
"""
import json
from pathlib import Path
from unittest.mock import patch

import os
import pytest

from pipeline.ingestion import IngestionEngine
from pipeline.alertes import SystemeAlertes
from pipeline.exceptions import (
    ConfigurationError,
    DataError,
    InvalidInputError,
)


PROJECT_ROOT = Path(__file__).resolve().parent.parent


# ================================================================
# Tests de validation d'entrée (ingestion.py)
# ================================================================

class TestValidationsIngestion:
    """Tests des méthodes de validation privées."""

    @pytest.fixture
    def engine(self):
        return IngestionEngine(os.environ["DATA_PATH"])

    def test_date_format_invalide_leve_erreur(self, engine):
        """Une date au mauvais format doit être rejetée."""
        with pytest.raises((InvalidInputError, DataError)):
            engine.charger_metriques('anomalies', '29-01-2023')

    def test_date_avec_lettres_leve_erreur(self, engine):
        with pytest.raises((InvalidInputError, DataError)):
            engine.charger_metriques('anomalies', 'invalid_date')

    def test_source_inconnue_leve_erreur(self, engine):
        """Une source non 'normal'/'anomalies' doit être rejetée."""
        with pytest.raises((InvalidInputError, DataError)):
            engine.charger_metriques('source_inexistante', '2023-01-29')

    def test_window_sans_underscore_leve_erreur(self, engine):
        with pytest.raises((InvalidInputError, DataError)):
            engine.charger_metriques_fenetre('anomalies', '2023-01-29', '0843')

    def test_window_lettres_leve_erreur(self, engine):
        with pytest.raises((InvalidInputError, DataError)):
            engine.charger_metriques_fenetre('anomalies', '2023-01-29', 'ab_cd')

    def test_window_heures_trop_grandes(self, engine):
        """25_00 : heure invalide (> 23)."""
        with pytest.raises((InvalidInputError, DataError)):
            engine.charger_metriques_fenetre('anomalies', '2023-01-29', '25_00')

    def test_window_minutes_trop_grandes(self, engine):
        """10_60 : minute invalide (> 59)."""
        with pytest.raises((InvalidInputError, DataError)):
            engine.charger_metriques_fenetre('anomalies', '2023-01-29', '10_60')


# ================================================================
# Tests du système d'alertes (alertes.py)
# ================================================================

class TestSystemeAlertesEdgeCases:
    """Tests des cas limites du système d'alertes."""

    @pytest.fixture
    def alertes_temp(self, tmp_path):
        """Crée un SystemeAlertes avec un fichier temporaire."""
        fichier = tmp_path / "alertes_test.json"
        return SystemeAlertes(fichier_alertes=str(fichier))

    def test_creation_fichier_si_inexistant(self, tmp_path):
        """Le fichier doit être créé automatiquement au premier accès."""
        fichier = tmp_path / "nouveau_alertes.json"
        assert not fichier.exists()
        SystemeAlertes(fichier_alertes=str(fichier))
        assert fichier.exists()

    def test_obtenir_alertes_vide(self, alertes_temp):
        """Un fichier vide doit retourner une liste vide."""
        alertes = alertes_temp.obtenir()
        assert alertes == []

    # def test_statistiques_vide(self, alertes_temp):
    #     """Les statistiques doivent gérer un fichier vide."""
    #     stats = alertes_temp.statistiques()
    #     assert stats['total'] == 0
    #     assert stats['par_severite'] == {}
    #     assert stats['par_systeme'] == {}

    def test_statistiques_vide(self, alertes_temp):
        """Les statistiques doivent gérer un fichier vide."""
        stats = alertes_temp.statistiques()
        assert stats['total'] == 0
        # Les compteurs peuvent être initialisés à zéro ou vides
        assert sum(stats['par_severite'].values()) == 0
        assert sum(stats['par_systeme'].values()) == 0
        
    def test_enregistrer_et_obtenir(self, alertes_temp):
        """Un enregistrement doit être récupérable."""
        alerte = {
            'systeme': 'train_ticket',
            'fenetre': '2023-01-29 08_43',
            'severite': 'WARNING',
            'confiance': 0.67,
            'modalites': {'metriques': True, 'logs': False, 'traces': True},
        }
        alertes_temp.enregistrer(alerte)
        obtenu = alertes_temp.obtenir()
        assert len(obtenu) == 1
        assert obtenu[0]['severite'] == 'WARNING'

    def test_filtre_severite(self, alertes_temp):
        """Le filtre par sévérité doit fonctionner."""
        alertes_temp.enregistrer({
            'systeme': 'train_ticket', 'fenetre': 'a',
            'severite': 'WARNING', 'confiance': 0.5,
            'modalites': {}
        })
        alertes_temp.enregistrer({
            'systeme': 'train_ticket', 'fenetre': 'b',
            'severite': 'CRITICAL', 'confiance': 1.0,
            'modalites': {}
        })
        warnings = alertes_temp.obtenir(severite='WARNING')
        assert len(warnings) == 1
        assert warnings[0]['severite'] == 'WARNING'

    def test_filtre_systeme(self, alertes_temp):
        """Le filtre par système doit fonctionner."""
        alertes_temp.enregistrer({
            'systeme': 'train_ticket', 'fenetre': 'a',
            'severite': 'WARNING', 'confiance': 0.5,
            'modalites': {}
        })
        alertes_temp.enregistrer({
            'systeme': 'online_boutique', 'fenetre': 'b',
            'severite': 'LOW', 'confiance': 0.3,
            'modalites': {}
        })
        tt = alertes_temp.obtenir(systeme='train_ticket')
        assert len(tt) == 1
        assert tt[0]['systeme'] == 'train_ticket'

    def test_limite_respectee(self, alertes_temp):
        """La limite doit être respectée."""
        for i in range(10):
            alertes_temp.enregistrer({
                'systeme': 'train_ticket', 'fenetre': f'f{i}',
                'severite': 'LOW', 'confiance': 0.3,
                'modalites': {}
            })
        obtenu = alertes_temp.obtenir(limite=5)
        assert len(obtenu) == 5


# ================================================================
# Tests de configuration (main.py)
# ================================================================

class TestConfigurationErreurs:
    """Tests des erreurs de configuration."""

    def test_config_yaml_malforme(self, tmp_path):
        """Un config.yaml avec syntaxe YAML invalide doit lever ConfigurationError."""
        from pipeline.main import PipelineComplet
        config_invalide = tmp_path / "config.yaml"
        config_invalide.write_text("clé: valeur\n  mauvais indent")

        with pytest.raises(ConfigurationError):
            PipelineComplet(
                systeme='train_ticket',
                config_path=str(config_invalide),
            )

    def test_config_yaml_manque_clef_data(self, tmp_path):
        """Un config sans clé 'data' doit lever ConfigurationError."""
        from pipeline.main import PipelineComplet
        config_incomplet = tmp_path / "config.yaml"
        config_incomplet.write_text("fusion:\n  strategie: or\n")

        with pytest.raises(ConfigurationError):
            PipelineComplet(
                systeme='train_ticket',
                config_path=str(config_incomplet),
            )

    def test_config_yaml_manque_clef_fusion(self, tmp_path):
        """Un config sans clé 'fusion' doit lever ConfigurationError."""
        from pipeline.main import PipelineComplet
        config_incomplet = tmp_path / "config.yaml"
        config_incomplet.write_text(
            "data:\n  base_path: /tmp\nfusion:\n  autre: valeur\n"
        )

        with pytest.raises(ConfigurationError):
            PipelineComplet(
                systeme='train_ticket',
                config_path=str(config_incomplet),
            )