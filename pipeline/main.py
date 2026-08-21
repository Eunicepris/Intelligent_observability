"""
Pipeline principal orchestrant toutes les étapes.

Charge une fenêtre → détecte les anomalies → fusionne → classifie → alerte.
Point d'entrée principal du pipeline automatique.
"""
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

from pipeline.ingestion import IngestionEngine
from pipeline.detection import (
    DetecteurAnomalies,
    fusionner,
    classifier,
    score_confiance,
    obtenir_action,
)
from pipeline.alertes import SystemeAlertes
from pipeline.classification_type import ClassificateurTypePanne
from pipeline.exceptions import PipelineError, ConfigurationError, DataError, ModelError
from pipeline.logger import setup_logging


logger = setup_logging(__name__)

# Racine du projet (calculée depuis l'emplacement de ce fichier)
# pipeline/main.py -> PROJECT_ROOT = Intelligent_observability/
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Sévérités qui déclenchent une alerte
SEVERITES_ALERTABLES = {'CRITICAL', 'WARNING', 'LOW'}


class PipelineComplet:
    """
    Pipeline complet de détection d'anomalies.
    
    Orchestre :
    1. Ingestion des données
    2. Détection par les 3 modalités (métriques, logs, traces)
    3. Fusion des détections
    4. Classification par sévérité (CRITICAL / WARNING / LOW / NORMAL)
    5. Classification supervisée du type de panne
    6. Enregistrement d'alerte si applicable
    
    Applique le pattern Facade avec injection de dépendances pour la testabilité.
    """
    
    def __init__(
        self,
        systeme: str = 'train_ticket',
        #config_path: str = 'config.yaml',
        config_path: Optional[str] = None,
        ingestion: Optional[IngestionEngine] = None,
        detecteur: Optional[DetecteurAnomalies] = None,
        alertes: Optional[SystemeAlertes] = None,
        classificateur: Optional[ClassificateurTypePanne] = None,
    ):
        """
        Initialise le pipeline.
        
        Les composants peuvent être injectés (utile pour les tests) ou créés
        par défaut à partir de la configuration.
        
        Args:
            systeme        : 'train_ticket' ou 'online_boutique'
            config_path    : chemin vers config.yaml
            ingestion      : optionnel, IngestionEngine à utiliser
            detecteur      : optionnel, DetecteurAnomalies à utiliser
            alertes        : optionnel, SystemeAlertes à utiliser
            classificateur : optionnel, ClassificateurTypePanne à utiliser
        
        Raises:
            ConfigurationError : si config_path est invalide
            DataError          : si le systeme est invalide
            ModelError         : si les modèles ne peuvent pas être chargés
        """
        # Chemin config par défaut : racine du projet
        if config_path is None:
            config_path = PROJECT_ROOT / 'config.yaml'
        
        self.systeme = systeme
        self.config = self._charger_config(config_path)
        
        # Résoudre base_path relatif à la racine du projet
        base_path = self.config['data']['base_path']
        if not Path(base_path).is_absolute():
            base_path = PROJECT_ROOT / base_path
        
        # Résoudre alertes_fichier de la même façon
        alertes_fichier = self.config.get('alertes', {}).get('fichier', 'alertes.json')
        if not Path(alertes_fichier).is_absolute():
            alertes_fichier = PROJECT_ROOT / alertes_fichier
        
        # Résoudre models_dir relatif à la racine du projet
        models_dir = PROJECT_ROOT / 'models'
        
        # Injection de dépendances avec valeurs par défaut
        self.ingestion = ingestion or IngestionEngine(str(base_path))
        self.detecteur = detecteur or DetecteurAnomalies(systeme=systeme, models_dir=str(models_dir))
        self.alertes = alertes or SystemeAlertes(fichier_alertes=str(alertes_fichier))
        self.classificateur = classificateur or ClassificateurTypePanne(models_dir=str(models_dir))
        
        self.strategie = self.config['fusion']['strategie']
        
        logger.info(
            f"Pipeline initialisé pour {systeme} (stratégie de fusion : {self.strategie})"
        )
    
    def _charger_config(self, config_path: str) -> Dict[str, Any]:
        """
        Charge la configuration depuis un fichier YAML.
        
        Args:
            config_path : chemin vers le fichier
        
        Returns:
            dictionnaire de configuration
        
        Raises:
            ConfigurationError : si le fichier est absent ou mal formé
        """
        try:
            with open(config_path) as f:
                config = yaml.safe_load(f)
        except FileNotFoundError:
            raise ConfigurationError(f"Fichier de configuration introuvable : {config_path}")
        except yaml.YAMLError as e:
            raise ConfigurationError(f"Erreur de parsing YAML : {e}")
        
        # Validation minimale de la configuration
        if 'data' not in config or 'base_path' not in config.get('data', {}):
            raise ConfigurationError(
                f"Configuration invalide : 'data.base_path' manquant dans {config_path}"
            )
        if 'fusion' not in config or 'strategie' not in config.get('fusion', {}):
            raise ConfigurationError(
                f"Configuration invalide : 'fusion.strategie' manquant dans {config_path}"
            )
        
        return config
    
    def traiter_fenetre(self, date: str, window: str) -> Dict[str, Any]:
        """
        Traite une fenêtre complète et retourne le résultat structuré.
        
        Args:
            date   : ex '2023-01-29'
            window : ex '08_43'
        
        Returns:
            dict contenant :
                - systeme, fenetre
                - anomalie (bool)
                - severite (CRITICAL/WARNING/LOW/NORMAL)
                - confiance (0-1)
                - modalites (dict des 3 détections)
                - type_panne (dict si anomalie, None sinon)
                - action (recommandation générale)
        
        Raises:
            PipelineError : si une étape critique échoue
        """
        logger.info(f"Traitement fenêtre : {self.systeme} / {date} / {window}")
        
        try:
            # 1. Ingestion
            donnees = self.ingestion.charger_fenetre_complete(
                'anomalies', date, window
            )
            
            # 2. Détection multi-modale
            detections = self.detecteur.detecter_toutes(donnees)
            
            # 3. Fusion
            est_anomalie = fusionner(detections, self.strategie)
            
            # 4. Classification par sévérité
            severite = classifier(detections)
            confiance = score_confiance(detections)
            action = obtenir_action(severite)
            
            # 5. Classification du type de panne (si anomalie)
            type_panne = None
            if est_anomalie:
                try:
                    type_panne = self.classificateur.predire(
                        donnees, self.detecteur, self.systeme
                    )
                except (ModelError, DataError) as e:
                    # Non bloquant : le pipeline continue sans le type de panne
                    logger.warning(f"Classification du type échouée : {e}")
            
            # 6. Construction du résultat
            resultat = {
                'systeme'  : self.systeme,
                'fenetre'  : f"{date} {window}",
                'anomalie' : bool(est_anomalie),
                'severite' : severite,
                'confiance': float(confiance),
                'modalites': {
                    'metriques': bool(detections['metriques']),
                    'logs'     : bool(detections['logs']),
                    'traces'   : bool(detections['traces']),
                },
                'type_panne': type_panne,
                'action'    : action,
            }
            
            # 7. Enregistrement d'alerte si sévérité pertinente
            if severite in SEVERITES_ALERTABLES:
                try:
                    self.alertes.enregistrer(resultat)
                except DataError as e:
                    logger.error(f"Enregistrement d'alerte échoué : {e}")
            
            logger.info(
                f"Fenêtre traitée : {severite} (confiance {confiance*100:.0f}%)"
            )
            return resultat
        
        except DataError as e:
            raise PipelineError(
                f"Erreur de données pour {date} {window} : {e}"
            ) from e
    
    def traiter_batch(
        self, liste_fenetres: List[Tuple[str, str]]
    ) -> List[Dict[str, Any]]:
        """
        Traite plusieurs fenêtres en batch.
        
        Continue le traitement même si certaines fenêtres échouent — les erreurs
        sont incluses dans les résultats sous forme de dict avec une clé 'erreur'.
        
        Args:
            liste_fenetres : liste de tuples (date, window)
        
        Returns:
            liste des résultats (résultats normaux ou erreurs par fenêtre)
        """
        logger.info(f"Traitement batch de {len(liste_fenetres)} fenêtres")
        
        resultats = []
        for date, window in liste_fenetres:
            try:
                resultats.append(self.traiter_fenetre(date, window))
            except PipelineError as e:
                logger.error(f"Erreur sur {date} {window} : {e}")
                resultats.append({
                    'systeme': self.systeme,
                    'fenetre': f"{date} {window}",
                    'erreur' : str(e),
                })
        
        logger.info(
            f"Batch terminé : {len(resultats)} traitées, "
            f"{sum(1 for r in resultats if 'erreur' in r)} en erreur"
        )
        return resultats


def afficher_resultat(resultat: Dict[str, Any]) -> None:
    """Affiche joliment un résultat de détection."""
    if 'erreur' in resultat:
        print(f"\n❌ Erreur sur {resultat['fenetre']} : {resultat['erreur']}")
        return
    
    print(f"\n{'='*60}")
    print(f"  Système  : {resultat['systeme']}")
    print(f"  Fenêtre  : {resultat['fenetre']}")
    print(f"{'='*60}")
    
    sev = resultat['severite']
    emoji = {'CRITICAL': '🚨', 'WARNING': '⚠️', 'LOW': '💡', 'NORMAL': '✓'}[sev]
    print(f"\n  {emoji} Sévérité   : {sev}")
    print(f"  Confiance  : {resultat['confiance']*100:.0f}%")
    print(f"  Anomalie   : {'OUI' if resultat['anomalie'] else 'NON'}")
    
    print(f"\n  Modalités :")
    for mod, det in resultat['modalites'].items():
        marker = '✓' if det else '○'
        print(f"    {marker} {mod:<12} : {'Détecte' if det else 'Normal'}")
    
    if resultat.get('type_panne'):
        tp = resultat['type_panne']
        print(f"\n  🔍 Type de panne prédit : {tp['type_predit']}")
        print(f"  Confiance classification : {tp['confiance']*100:.0f}%")
        print(f"  Action spécifique : {tp['action_specifique']}")
    
    print(f"\n  Action : {resultat['action']}")


if __name__ == '__main__':
    print("="*60)
    print("  PIPELINE COMPLET — Test end-to-end")
    print("="*60)
    
    try:
        # Train Ticket
        print("\n▶ Test 1 : Train Ticket — fenêtre 08_43")
        pipeline_tt = PipelineComplet(systeme='train_ticket')
        resultat_tt = pipeline_tt.traiter_fenetre('2023-01-29', '08_43')
        afficher_resultat(resultat_tt)
        
        # Online Boutique
        print("\n▶ Test 2 : Online Boutique — fenêtre 03_53 (panne cpu_contention)")
        pipeline_ob = PipelineComplet(systeme='online_boutique')
        resultat_ob = pipeline_ob.traiter_fenetre('2022-08-22', '03_53')
        afficher_resultat(resultat_ob)
        
        # Statistiques des alertes
        print("\n" + "="*60)
        print("  STATISTIQUES DES ALERTES")
        print("="*60)
        stats = pipeline_tt.alertes.statistiques()
        print(f"\n  Total alertes : {stats['total']}")
        print(f"  Par sévérité  : {stats['par_severite']}")
        print(f"  Par système   : {stats['par_systeme']}")
    
    except (PipelineError, ConfigurationError, DataError, ModelError) as e:
        print(f"\n❌ Erreur pipeline : {e}")