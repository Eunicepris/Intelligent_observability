"""
Tests du module pipeline/main.py (PipelineComplet).

Couvre l'orchestration : initialisation, traitement d'une fenêtre,
traitement en batch, gestion des erreurs.
"""
from pathlib import Path

import pytest

from pipeline.main import PipelineComplet
from pipeline.exceptions import (
    ConfigurationError,
    DataError,
    InvalidInputError,
    PipelineError,
)


PROJECT_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def pipeline_tt():
    """Pipeline Train Ticket réutilisé dans plusieurs tests."""
    return PipelineComplet(systeme='train_ticket')


class TestInitialisationPipeline:
    """Tests de l'initialisation du PipelineComplet."""
    
    def test_initialisation_train_ticket(self):
        pipeline = PipelineComplet(systeme='train_ticket')
        assert pipeline.systeme == 'train_ticket'
        assert pipeline.strategie in ('or', 'and', 'vote_majoritaire')
        assert pipeline.ingestion is not None
        assert pipeline.detecteur is not None
        assert pipeline.alertes is not None
        assert pipeline.classificateur is not None
    
    def test_initialisation_online_boutique(self):
        pipeline = PipelineComplet(systeme='online_boutique')
        assert pipeline.systeme == 'online_boutique'
    
    def test_config_path_inexistant_leve_erreur(self):
        with pytest.raises(ConfigurationError):
            PipelineComplet(
                systeme='train_ticket',
                config_path='/chemin/inexistant/config.yaml',
            )


class TestTraiterFenetre:
    """Tests de la méthode traiter_fenetre."""
    
    def test_fenetre_valide_retourne_resultat_structure(self, pipeline_tt):
        resultat = pipeline_tt.traiter_fenetre('2023-01-29', '08_43')
        
        # Structure attendue
        assert 'systeme' in resultat
        assert 'fenetre' in resultat
        assert 'anomalie' in resultat
        assert 'severite' in resultat
        assert 'confiance' in resultat
        assert 'modalites' in resultat
        assert 'action' in resultat
        
        # Types corrects
        assert isinstance(resultat['anomalie'], bool)
        assert isinstance(resultat['confiance'], float)
        assert 0 <= resultat['confiance'] <= 1
        
        # Sévérité valide
        assert resultat['severite'] in ('CRITICAL', 'WARNING', 'LOW', 'NORMAL')
    
    def test_fenetre_avec_anomalie_a_type_panne(self, pipeline_tt):
        """Si anomalie détectée, type_panne doit être renseigné."""
        resultat = pipeline_tt.traiter_fenetre('2023-01-29', '08_43')
        
        if resultat['anomalie']:
            assert resultat['type_panne'] is not None
            assert 'type_predit' in resultat['type_panne']
            assert 'confiance' in resultat['type_panne']
    
    def test_fenetre_format_invalide_leve_invalid_input_error(self, pipeline_tt):
        """'24_89' a un format impossible (HH>23)."""
        with pytest.raises(InvalidInputError):
            pipeline_tt.traiter_fenetre('2023-01-29', '24_89')
    
    def test_fenetre_absente_leve_data_error(self, pipeline_tt):
        """'11_51' a un format valide mais n'existe pas dans Nezha."""
        with pytest.raises(DataError):
            pipeline_tt.traiter_fenetre('2023-01-29', '11_51')


class TestTraiterBatch:
    """Tests de la méthode traiter_batch."""
    
    def test_batch_vide_retourne_liste_vide(self, pipeline_tt):
        resultats = pipeline_tt.traiter_batch([])
        assert resultats == []
    
    def test_batch_une_fenetre_valide(self, pipeline_tt):
        resultats = pipeline_tt.traiter_batch([('2023-01-29', '08_43')])
        assert len(resultats) == 1
        assert 'severite' in resultats[0]
    
    def test_batch_avec_erreur_continue(self, pipeline_tt):
        """Une fenêtre en erreur ne doit pas bloquer le batch."""
        fenetres = [
            ('2023-01-29', '08_43'),      # valide
            ('2023-01-29', '11_51'),      # absente (DataError)
            ('2023-01-29', '08_43'),      # valide
        ]
        resultats = pipeline_tt.traiter_batch(fenetres)
        
        assert len(resultats) == 3
        # La fenêtre en erreur a une clé 'erreur'
        assert 'erreur' in resultats[1]
        # Les autres sont des résultats normaux
        assert 'severite' in resultats[0]
        assert 'severite' in resultats[2]