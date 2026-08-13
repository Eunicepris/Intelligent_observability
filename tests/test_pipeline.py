"""
Tests unitaires pour le pipeline de détection d'anomalies.
"""
import pytest
import sys
from pathlib import Path

# Ajouter le projet au path
sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.detection import (
    fusionner,
    classifier,
    score_confiance,
    obtenir_action,
)


# 
# TESTS DE FUSION
# 

class TestFusion:
    """Tests des stratégies de fusion multi-modale."""
    
    def test_or_avec_une_detection(self):
        detections = {'metriques': True, 'logs': False, 'traces': False}
        assert fusionner(detections, 'or') == True
    
    def test_or_sans_detection(self):
        detections = {'metriques': False, 'logs': False, 'traces': False}
        assert fusionner(detections, 'or') == False
    
    def test_or_toutes_detections(self):
        detections = {'metriques': True, 'logs': True, 'traces': True}
        assert fusionner(detections, 'or') == True
    
    def test_vote_majoritaire_avec_2(self):
        detections = {'metriques': True, 'logs': True, 'traces': False}
        assert fusionner(detections, 'vote_majoritaire') == True
    
    def test_vote_majoritaire_avec_1(self):
        detections = {'metriques': True, 'logs': False, 'traces': False}
        assert fusionner(detections, 'vote_majoritaire') == False
    
    def test_and_toutes(self):
        detections = {'metriques': True, 'logs': True, 'traces': True}
        assert fusionner(detections, 'and') == True
    
    def test_and_partiel(self):
        detections = {'metriques': True, 'logs': True, 'traces': False}
        assert fusionner(detections, 'and') == False
    
    def test_strategie_invalide(self):
        from pipeline.exceptions import DataError
        detections = {'metriques': True, 'logs': False, 'traces': False}
        with pytest.raises(DataError):
            fusionner(detections, 'strategie_inconnue')


# 
# TESTS DE CLASSIFICATION
# 

class TestClassification:
    """Tests de la classification en 4 niveaux."""
    
    def test_critical(self):
        detections = {'metriques': True, 'logs': True, 'traces': True}
        assert classifier(detections) == 'CRITICAL'
    
    def test_warning(self):
        detections = {'metriques': True, 'logs': True, 'traces': False}
        assert classifier(detections) == 'WARNING'
    
    def test_low(self):
        detections = {'metriques': True, 'logs': False, 'traces': False}
        assert classifier(detections) == 'LOW'
    
    def test_normal(self):
        detections = {'metriques': False, 'logs': False, 'traces': False}
        assert classifier(detections) == 'NORMAL'


# 
# TESTS DE SCORE DE CONFIANCE
# 

class TestScoreConfiance:
    """Tests du calcul de confiance."""
    
    def test_confiance_maximale(self):
        detections = {'metriques': True, 'logs': True, 'traces': True}
        assert score_confiance(detections) == 1.0
    
    def test_confiance_moyenne(self):
        detections = {'metriques': True, 'logs': True, 'traces': False}
        assert abs(score_confiance(detections) - 2/3) < 0.001
    
    def test_confiance_faible(self):
        detections = {'metriques': True, 'logs': False, 'traces': False}
        assert abs(score_confiance(detections) - 1/3) < 0.001
    
    def test_confiance_nulle(self):
        detections = {'metriques': False, 'logs': False, 'traces': False}
        assert score_confiance(detections) == 0.0


# 
# TESTS DES ACTIONS
# 

class TestActions:
    """Tests des actions recommandées."""
    
    def test_action_critical(self):
        action = obtenir_action('CRITICAL')
        assert 'immédiate' in action.lower()
    
    def test_action_warning(self):
        action = obtenir_action('WARNING')
        assert 'planifier' in action.lower()
    
    def test_action_low(self):
        action = obtenir_action('LOW')
        assert 'v' in action.lower()  # "vérifier"
    
    def test_action_normal(self):
        action = obtenir_action('NORMAL')
        assert 'passive' in action.lower() or 'aucune' in action.lower()


# 
# TESTS DES ALERTES
# 

class TestAlertes:
    """Tests du système d'alertes."""
    
    def test_creer_systeme_alertes(self, tmp_path):
        from pipeline.alertes import SystemeAlertes
        fichier = tmp_path / "test_alertes.json"
        alertes = SystemeAlertes(fichier_alertes=str(fichier))
        assert fichier.exists()
    
    def test_enregistrer_alerte(self, tmp_path):
        from pipeline.alertes import SystemeAlertes
        fichier = tmp_path / "test_alertes.json"
        alertes = SystemeAlertes(fichier_alertes=str(fichier))
        
        alertes.enregistrer({
            'systeme'  : 'train_ticket',
            'fenetre'  : '2023-01-29 08_43',
            'severite' : 'WARNING',
            'confiance': 0.67,
            'modalites': {'metriques': True, 'logs': False, 'traces': True},
            'action'   : 'test',
        })
        
        obtenues = alertes.obtenir()
        assert len(obtenues) == 1
        assert obtenues[0]['severite'] == 'WARNING'
    
    def test_statistiques_vides(self, tmp_path):
        from pipeline.alertes import SystemeAlertes
        fichier = tmp_path / "test_alertes.json"
        alertes = SystemeAlertes(fichier_alertes=str(fichier))
        stats = alertes.statistiques()
        assert stats['total'] == 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])