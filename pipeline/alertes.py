"""
Module de gestion des alertes.

Enregistre les anomalies détectées dans un fichier JSON persistant
et permet de les consulter (récentes, filtres, statistiques).
"""
import json
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from pipeline.exceptions import DataError
from pipeline.logger import setup_logging


logger = setup_logging(__name__)

# Sévérités valides
SEVERITES_VALIDES = {'CRITICAL', 'WARNING', 'LOW', 'NORMAL'}

# Clés requises dans un résultat pour être enregistré
CLES_REQUISES = {'systeme', 'fenetre', 'severite'}


class SystemeAlertes:
    """
    Système d'enregistrement et de consultation des alertes.
    
    Stocke les alertes dans un fichier JSON pour persistance simple.
    En production, ce module pourrait être remplacé par une base de données
    ou un système de notification (email, Slack, PagerDuty).
    """
    
    def __init__(self, fichier_alertes: str = 'alertes.json'):
        """
        Initialise le système d'alertes.
        
        Args:
            fichier_alertes : chemin du fichier de stockage JSON
        
        Raises:
            DataError : si le fichier existe mais est illisible
        """
        self.fichier = Path(fichier_alertes)
        
        # Créer le fichier s'il n'existe pas
        if not self.fichier.exists():
            try:
                self.fichier.parent.mkdir(parents=True, exist_ok=True)
                self.fichier.write_text('[]')
                logger.info(f"Fichier d'alertes créé : {self.fichier}")
            except OSError as e:
                raise DataError(
                    f"Impossible de créer le fichier d'alertes {self.fichier} : {e}"
                )
        
        logger.debug(f"SystemeAlertes initialisé avec {self.fichier}")
    
    def enregistrer(self, resultat: Dict[str, Any]) -> None:
        """
        Enregistre une nouvelle alerte.
        
        Args:
            resultat : dict contenant au minimum les clés systeme, fenetre, severite.
                       Autres clés supportées : confiance, modalites, services_suspects,
                       type_panne, action
        
        Raises:
            DataError : si des clés requises manquent ou si la sévérité est invalide
        """
        # Validation
        cles_manquantes = CLES_REQUISES - set(resultat.keys())
        if cles_manquantes:
            raise DataError(
                f"Clés requises manquantes dans le résultat : {cles_manquantes}"
            )
        
        severite = resultat.get('severite')
        if severite not in SEVERITES_VALIDES:
            raise DataError(
                f"Sévérité invalide '{severite}'. Valeurs autorisées : {SEVERITES_VALIDES}"
            )
        
        # Construction de l'alerte
        alerte = {
            'timestamp'        : datetime.now().isoformat(),
            'systeme'          : resultat.get('systeme'),
            'fenetre'          : resultat.get('fenetre'),
            'severite'         : resultat.get('severite'),
            'confiance'        : resultat.get('confiance'),
            'modalites'        : resultat.get('modalites'),
            'services_suspects': resultat.get('services_suspects', []),
            'type_panne'       : resultat.get('type_panne'),
            'action'           : resultat.get('action'),
        }
        
        alertes = self._charger()
        alertes.append(alerte)
        self._sauvegarder(alertes)
        
        logger.info(
            f"Alerte {severite} enregistrée : {alerte['systeme']} / {alerte['fenetre']}"
        )
    
    def obtenir(
        self,
        limite: int = 100,
        severite: Optional[str] = None,
        systeme: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Retourne les alertes récentes avec filtres optionnels.
        
        Args:
            limite   : nombre max d'alertes à retourner (dernières)
            severite : filtrer par sévérité ('CRITICAL', 'WARNING', 'LOW', 'NORMAL')
            systeme  : filtrer par système ('train_ticket', 'online_boutique')
        
        Returns:
            liste des alertes correspondantes (copies pour éviter mutation externe)
        
        Raises:
            DataError : si la sévérité de filtre est invalide
        """
        if severite is not None and severite not in SEVERITES_VALIDES:
            raise DataError(
                f"Filtre severite invalide '{severite}'. Valeurs autorisées : {SEVERITES_VALIDES}"
            )
        
        if limite < 1:
            raise DataError(f"La limite doit être >= 1, reçu {limite}")
        
        alertes = self._charger()
        
        if severite:
            alertes = [a for a in alertes if a.get('severite') == severite]
        
        if systeme:
            alertes = [a for a in alertes if a.get('systeme') == systeme]
        
        # Retourner des copies pour éviter les mutations externes
        return [deepcopy(a) for a in alertes[-limite:]]
    
    def statistiques(self) -> Dict[str, Any]:
        """
        Calcule des statistiques sur les alertes enregistrées.
        
        Returns:
            dict avec :
            - total          : nombre total d'alertes
            - par_severite   : compteurs par niveau
            - par_systeme    : compteurs par système
        """
        alertes = self._charger()
        
        stats: Dict[str, Any] = {
            'total'        : len(alertes),
            'par_severite' : {sev: 0 for sev in SEVERITES_VALIDES},
            'par_systeme'  : {},
        }
        
        for a in alertes:
            sev = a.get('severite', 'NORMAL')
            if sev in stats['par_severite']:
                stats['par_severite'][sev] += 1
            
            syst = a.get('systeme', 'inconnu')
            stats['par_systeme'][syst] = stats['par_systeme'].get(syst, 0) + 1
        
        return stats
    
    def effacer(self) -> None:
        """Efface toutes les alertes (utile pour reset)."""
        self._sauvegarder([])
        logger.warning("Toutes les alertes ont été effacées")
    
    def _charger(self) -> List[Dict[str, Any]]:
        """
        Charge les alertes depuis le fichier.
        
        Returns:
            liste des alertes (vide si le fichier est absent ou corrompu)
        """
        try:
            contenu = self.fichier.read_text()
            return json.loads(contenu)
        except FileNotFoundError:
            logger.warning(f"Fichier d'alertes introuvable : {self.fichier}")
            return []
        except json.JSONDecodeError as e:
            logger.error(f"Fichier d'alertes corrompu ({e}), retour d'une liste vide")
            return []
    
    def _sauvegarder(self, alertes: List[Dict[str, Any]]) -> None:
        """
        Sauvegarde les alertes dans le fichier.
        
        Args:
            alertes : liste des alertes à écrire
        
        Raises:
            DataError : si l'écriture échoue
        """
        try:
            self.fichier.write_text(
                json.dumps(alertes, indent=2, ensure_ascii=False)
            )
        except OSError as e:
            raise DataError(
                f"Impossible d'écrire dans le fichier d'alertes {self.fichier} : {e}"
            )


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
    
    # Test des validations
    print("\n  Test des validations :")
    try:
        alertes.enregistrer({'systeme': 'test'})  # Manque severite
    except DataError as e:
        print(f"    ✓ DataError capturée : {e}")
    
    try:
        alertes.obtenir(severite='INVALID')
    except DataError as e:
        print(f"    ✓ DataError capturée : {e}")