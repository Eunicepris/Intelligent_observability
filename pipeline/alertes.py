"""
Module de gestion des alertes.

Enregistre les anomalies détectées dans un fichier JSON persistant
et permet de les consulter (récentes, filtres, statistiques).
"""
import json
from datetime import datetime
from pathlib import Path


class SystemeAlertes:
    """
    Système d'enregistrement et de consultation des alertes.
    
    Stocke les alertes dans un fichier JSON pour persistance simple.
    En production, ce module pourrait être remplacé par une base de données
    ou un système de notification (email, Slack, PagerDuty).
    """
    
    def __init__(self, fichier_alertes='alertes.json'):
        """
        Args:
            fichier_alertes : chemin du fichier de stockage
        """
        self.fichier = Path(fichier_alertes)
        if not self.fichier.exists():
            self.fichier.write_text('[]')
    
    def enregistrer(self, resultat):
        """
        Enregistre une nouvelle alerte.
        
        Args:
            resultat : dict avec les clés systeme, fenetre, severite,
                       confiance, modalites, services_suspects (optionnel)
        """
        alerte = {
            'timestamp'        : datetime.now().isoformat(),
            'systeme'          : resultat.get('systeme'),
            'fenetre'          : resultat.get('fenetre'),
            'severite'         : resultat.get('severite'),
            'confiance'        : resultat.get('confiance'),
            'modalites'        : resultat.get('modalites'),
            'services_suspects': resultat.get('services_suspects', []),
            'action'           : resultat.get('action'),
        }
        
        alertes = self._charger()
        alertes.append(alerte)
        self._sauvegarder(alertes)
    
    def obtenir(self, limite=100, severite=None, systeme=None):
        """
        Retourne les alertes récentes avec filtres optionnels.
        
        Args:
            limite   : nombre max d'alertes à retourner (dernières)
            severite : filtrer par sévérité ('CRITICAL', 'WARNING', 'NORMAL')
            systeme  : filtrer par système ('train_ticket', 'online_boutique')
        
        Returns:
            liste des alertes correspondantes
        """
        alertes = self._charger()
        
        if severite:
            alertes = [a for a in alertes if a.get('severite') == severite]
        
        if systeme:
            alertes = [a for a in alertes if a.get('systeme') == systeme]
        
        return alertes[-limite:]
    
    def statistiques(self):
        """
        Calcule des statistiques sur les alertes enregistrées.
        
        Returns:
            dict avec compteurs par sévérité et système
        """
        alertes = self._charger()
        
        stats = {
            'total'          : len(alertes),
            'par_severite'   : {'CRITICAL': 0, 'WARNING': 0, 'LOW': 0, 'NORMAL': 0},
            'par_systeme'    : {},
        }
        
        for a in alertes:
            sev = a.get('severite', 'NORMAL')
            if sev in stats['par_severite']:
                stats['par_severite'][sev] += 1
            
            syst = a.get('systeme', 'inconnu')
            stats['par_systeme'][syst] = stats['par_systeme'].get(syst, 0) + 1
        
        return stats
    
    def effacer(self):
        """Efface toutes les alertes (utile pour reset)."""
        self._sauvegarder([])
    
    def _charger(self):
        """Charge les alertes depuis le fichier."""
        try:
            return json.loads(self.fichier.read_text())
        except (json.JSONDecodeError, FileNotFoundError):
            return []
    
    def _sauvegarder(self, alertes):
        """Sauvegarde les alertes dans le fichier."""
        self.fichier.write_text(json.dumps(alertes, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    # Test rapide
    print("Test — Système d'alertes")
    
    # Créer un système d'alertes temporaire
    alertes = SystemeAlertes(fichier_alertes='/tmp/test_alertes.json')
    alertes.effacer()  # Reset pour le test
    
    # Enregistrer une alerte CRITICAL
    alertes.enregistrer({
        'systeme'  : 'train_ticket',
        'fenetre'  : '2023-01-29 08_43',
        'severite' : 'CRITICAL',
        'confiance': 1.0,
        'modalites': {'metriques': True, 'logs': True, 'traces': True},
        'services_suspects': [{'service': 'ts-contacts-service', 'score': 0.85}],
        'action'   : 'Action immédiate requise',
    })
    
    # Enregistrer une alerte WARNING
    alertes.enregistrer({
        'systeme'  : 'train_ticket',
        'fenetre'  : '2023-01-29 08_44',
        'severite' : 'WARNING',
        'confiance': 0.67,
        'modalites': {'metriques': True, 'logs': False, 'traces': True},
        'services_suspects': [],
        'action'   : 'Alerte modérée',
    })
    
    # Consulter
    print(f"\n  Toutes les alertes : {len(alertes.obtenir())}")
    print(f"  Alertes CRITICAL   : {len(alertes.obtenir(severite='CRITICAL'))}")
    
    print(f"\n  Statistiques :")
    stats = alertes.statistiques()
    for k, v in stats.items():
        print(f"    {k}: {v}")