"""
Tests d'intégration avec un mini-dataset réel.

Ces tests utilisent une fenêtre de vraies données Nezha
(2023-01-29 08_43, panne 'return' sur ts-contacts-service).
"""
import os
import sys
import yaml
import tempfile
import shutil
from pathlib import Path

import pytest

# Ajouter le projet au path
sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture(scope='module')
def config_test():
    """Prépare un config.yaml temporaire pointant vers le mini-dataset."""
    mini_data_path = str(Path(__file__).parent / 'mini_data')
    
    # Lire le config existant
    original_config = Path(__file__).parent.parent / 'config.yaml'
    with open(original_config) as f:
        config = yaml.safe_load(f)
    
    # Modifier le chemin de data
    config['data']['base_path'] = mini_data_path
    
    # Créer un fichier temporaire
    tmp = tempfile.NamedTemporaryFile(
        mode='w', suffix='.yaml', delete=False
    )
    yaml.dump(config, tmp)
    tmp.close()
    
    yield tmp.name
    
    # Cleanup
    os.unlink(tmp.name)


class TestDetectionReelle:
    """Tests de détection avec un mini-dataset."""
    
    def test_detection_panne_return(self, config_test):
        """
        Test que le pipeline détecte l'anomalie sur ts-contacts (panne return).
        """
        from pipeline.main import PipelineComplet
        
        pipeline = PipelineComplet(
            systeme='train_ticket',
            config_path=config_test,
        )
        
        resultat = pipeline.traiter_fenetre('2023-01-29', '08_43')
        
        # Vérifications
        assert resultat['systeme'] == 'train_ticket'
        assert resultat['fenetre'] == '2023-01-29 08_43'
        assert resultat['anomalie'] == True  # C'est une vraie panne
        assert resultat['severite'] in ['CRITICAL', 'WARNING', 'LOW']
        assert 0 < resultat['confiance'] <= 1
    
    def test_modalites_detectent(self, config_test):
        """Au moins une modalité doit détecter."""
        from pipeline.main import PipelineComplet
        
        pipeline = PipelineComplet(
            systeme='train_ticket',
            config_path=config_test,
        )
        resultat = pipeline.traiter_fenetre('2023-01-29', '08_43')
        
        # Au moins une modalité détecte
        modalites = resultat['modalites']
        assert any(modalites.values()), "Au moins une modalité devrait détecter"


class TestClassificationReelle:
    """Tests de classification avec un mini-dataset."""
    
    def test_classification_type_panne(self, config_test):
        """
        Test que la classification retourne un type valide.
        """
        from pipeline.main import PipelineComplet
        
        pipeline = PipelineComplet(
            systeme='train_ticket',
            config_path=config_test,
        )
        
        resultat = pipeline.traiter_fenetre('2023-01-29', '08_43')
        
        # Si anomalie, on doit avoir un type de panne
        if resultat['anomalie']:
            type_panne = resultat.get('type_panne')
            assert type_panne is not None
            assert 'type_predit' in type_panne
            assert type_panne['type_predit'] in [
                'cpu_problem', 'exception', 'network_delay', 'return'
            ]
            assert 0 <= type_panne['confiance'] <= 1
    
    def test_action_specifique(self, config_test):
        """Le type de panne doit avoir une action spécifique."""
        from pipeline.main import PipelineComplet
        
        pipeline = PipelineComplet(
            systeme='train_ticket',
            config_path=config_test,
        )
        resultat = pipeline.traiter_fenetre('2023-01-29', '08_43')
        
        if resultat.get('type_panne'):
            action = resultat['type_panne']['action_specifique']
            assert action  # Non vide
            assert len(action) > 10  # Au moins quelques mots


if __name__ == '__main__':
    pytest.main([__file__, '-v'])