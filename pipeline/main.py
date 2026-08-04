"""
Pipeline principal orchestrant toutes les étapes.

Charge une fenêtre → détecte les anomalies → fusionne → classifie → alerte.
Point d'entrée principal du pipeline automatique.
"""
import yaml
from pathlib import Path

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

class PipelineComplet:
    """
    Pipeline complet de détection d'anomalies.
    
    Orchestre :
    1. Ingestion des données
    2. Détection par les 3 modalités (métriques, logs, traces)
    3. Fusion des détections
    4. Classification (CRITICAL / WARNING / LOW / NORMAL)
    5. Enregistrement d'alerte si applicable
    """
    
    def __init__(self, systeme='train_ticket', config_path='config.yaml'):
        """
        Args:
            systeme     : 'train_ticket' ou 'online_boutique'
            config_path : chemin vers config.yaml
        """
        # Charger la configuration
        with open(config_path) as f:
            self.config = yaml.safe_load(f)
        
        self.systeme = systeme
        
        # Initialiser les composants
        self.ingestion = IngestionEngine(self.config['data']['base_path'])
        self.detecteur = DetecteurAnomalies(systeme=systeme)
        self.alertes   = SystemeAlertes()
        self.classificateur = ClassificateurTypePanne()
        self.strategie = self.config['fusion']['strategie']
    
    def traiter_fenetre(self, date, window):
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
                - action (recommandation)
        """
        # 1. Ingestion
        donnees = self.ingestion.charger_fenetre_complete(
            'anomalies', date, window
        )
        
        # 2. Détection multi-modale
        detections = self.detecteur.detecter_toutes(donnees)
        
        # 3. Fusion
        est_anomalie = fusionner(detections, self.strategie)
        
        # 4. Classification
        severite  = classifier(detections)
        confiance = score_confiance(detections)
        action    = obtenir_action(severite)

        # 5. Classification du type de panne (si anomalie)
        type_panne = None
        if est_anomalie:
            type_panne = self.classificateur.predire(donnees, self.detecteur, self.systeme)

        # 6. Construire le résultat
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
            'action'   : action,
        }
        
        # 6. Enregistrer alerte si CRITICAL, WARNING ou LOW
        if severite in ['CRITICAL', 'WARNING', 'LOW']:
            self.alertes.enregistrer(resultat)
        
        return resultat
    
    def traiter_batch(self, liste_fenetres):
        """
        Traite plusieurs fenêtres en batch.
        
        Args:
            liste_fenetres : liste de tuples (date, window)
        
        Returns:
            liste des résultats
        """
        return [self.traiter_fenetre(d, w) for d, w in liste_fenetres]


def afficher_resultat(resultat):
    """Affiche joliment un résultat de détection."""
    print(f"\n{'='*60}")
    print(f"  Système  : {resultat['systeme']}")
    print(f"  Fenêtre  : {resultat['fenetre']}")
    print(f"{'='*60}")
    
    # Statut principal
    sev = resultat['severite']
    emoji = {'CRITICAL': '🚨', 'WARNING': '⚠️', 'LOW': '💡', 'NORMAL': '✓'}[sev]
    print(f"\n  {emoji} Sévérité   : {sev}")
    print(f"  Confiance  : {resultat['confiance']*100:.0f}%")
    print(f"  Anomalie   : {'OUI' if resultat['anomalie'] else 'NON'}")
    
    # Modalités
    print(f"\n  Modalités :")
    for mod, det in resultat['modalites'].items():
        marker = '✓' if det else '○'
        print(f"    {marker} {mod:<12} : {'Détecte' if det else 'Normal'}")

    # Type de panne (NOUVEAU)
    if resultat.get('type_panne'):
        tp = resultat['type_panne']
        print(f"\n  🔍 Type de panne prédit : {tp['type_predit']}")
        print(f"  Confiance classification : {tp['confiance']*100:.0f}%")
        print(f"  Action spécifique : {tp['action_specifique']}")
        
    # Action
    print(f"\n  Action : {resultat['action']}")


if __name__ == '__main__':
    # Test end-to-end du pipeline complet
    print("="*60)
    print("  PIPELINE COMPLET — Test end-to-end")
    print("="*60)
    
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