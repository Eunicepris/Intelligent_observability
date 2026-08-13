"""
Module de détection d'anomalies multi-modale.

Charge les modèles pré-entraînés (LOF, TF-IDF, IF par service)
et détecte les anomalies par modalité, puis fusionne les résultats.
"""
import pickle
from pathlib import Path
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity

from pipeline.exceptions import ModelError, DataError
from pipeline.logger import setup_logging


logger = setup_logging(__name__)



# CONSTANTES


METRIQUES = [
    'CpuUsageRate(%)',
    'MemoryUsageRate(%)',
    'PodServerLatencyP99(s)',
    'NetworkReceiveBytes',
    'NetworkTransmitBytes',
]

SEUILS_TFIDF = {
    'train_ticket'   : 0.95,
    'online_boutique': 0.7,
}

SEUIL_IF_TRACES = 0.12

# Systèmes supportés
SYSTEMES_VALIDES = {'train_ticket', 'online_boutique'}

# Stratégies de fusion supportées
STRATEGIES_VALIDES = {'or', 'vote_majoritaire', 'and'}

# Sévérités
SEVERITES = ['NORMAL', 'LOW', 'WARNING', 'CRITICAL']


class DetecteurAnomalies:
    """
    Détecteur d'anomalies multi-modale.
    
    Utilise 3 modèles pré-entraînés :
    - LOF sur les métriques (par service)
    - TF-IDF sur les logs (similarité cosinus)
    - Isolation Forest sur les traces (par service)
    """
    
    def __init__(self, systeme: str = 'train_ticket', models_dir: str = 'models'):
        """
        Initialise le détecteur en chargeant les modèles pré-entraînés.
        
        Args:
            systeme    : 'train_ticket' ou 'online_boutique'
            models_dir : chemin vers le dossier models/
        
        Raises:
            DataError  : si le systeme n'est pas supporté
            ModelError : si un modèle est introuvable ou corrompu
        """
        if systeme not in SYSTEMES_VALIDES:
            raise DataError(
                f"Systeme invalide : '{systeme}'. Valeurs autorisées : {SYSTEMES_VALIDES}"
            )
        
        self.systeme = systeme
        self.models_dir = Path(models_dir)
        self.suffix = 'tt' if systeme == 'train_ticket' else 'ob'
        
        if not self.models_dir.exists():
            raise ModelError(
                f"Dossier de modèles introuvable : {self.models_dir}"
            )
        
        self._charger_modeles()
        logger.info(f"DetecteurAnomalies initialisé pour {systeme}")
    
    def _charger_modeles(self) -> None:
        """
        Charge les 3 modèles depuis models/.
        
        Raises:
            ModelError : si un fichier est manquant ou illisible
        """
        modeles_a_charger = {
            'lof'      : f'lof_{self.suffix}.pkl',
            'tfidf'    : f'tfidf_{self.suffix}.pkl',
            'if_traces': f'if_traces_{self.suffix}.pkl',
        }
        
        for attribut, nom_fichier in modeles_a_charger.items():
            chemin = self.models_dir / nom_fichier
            
            if not chemin.exists():
                raise ModelError(
                    f"Modèle introuvable : {chemin}. "
                    f"Vérifiez que les modèles ont été entraînés (voir notebook 12)."
                )
            
            try:
                with open(chemin, 'rb') as f:
                    setattr(self, attribut, pickle.load(f))
                logger.debug(f"Modèle chargé : {nom_fichier}")
            except (pickle.UnpicklingError, EOFError) as e:
                raise ModelError(
                    f"Modèle corrompu ou incompatible : {chemin}. "
                    f"Erreur : {e}. "
                    f"Vérifiez la version de scikit-learn utilisée."
                )
    
    def detecter_metriques(self, df_metriques: pd.DataFrame) -> bool:
        """
        Détecte les anomalies dans les métriques d'une fenêtre.
        
        Args:
            df_metriques : DataFrame avec colonnes service + METRIQUES
        
        Returns:
            True si au moins un point est anormal
        """
        if df_metriques.empty:
            logger.debug("Métriques : DataFrame vide, pas d'anomalie détectable")
            return False
        
        for service in df_metriques['service'].unique():
            if service not in self.lof['modeles']:
                continue
            df_svc = df_metriques[df_metriques['service'] == service][METRIQUES].dropna()
            if df_svc.empty:
                continue
            
            try:
                X = self.lof['scalers'][service].transform(df_svc)
                pred = self.lof['modeles'][service].predict(X)
                if (pred == -1).any():
                    logger.debug(f"Anomalie métriques détectée sur {service}")
                    return True
            except (ValueError, KeyError) as e:
                logger.warning(f"Erreur détection métriques sur {service} : {e}")
                continue
        
        return False
    
    def detecter_logs(
        self,
        df_logs: pd.DataFrame,
        service_cible: Optional[str] = None,
    ) -> bool:
        """
        Détecte les anomalies dans les logs d'une fenêtre.
        
        Args:
            df_logs       : DataFrame avec colonnes service + template
            service_cible : si spécifié, analyse uniquement ce service
        
        Returns:
            True si la similarité est inférieure au seuil
        """
        if df_logs.empty:
            logger.debug("Logs : DataFrame vide, pas d'anomalie détectable")
            return False
        
        if service_cible:
            df_logs = df_logs[df_logs['service'] == service_cible]
            if df_logs.empty:
                return False
        
        texte = ' '.join(df_logs['template'].tolist())
        if not texte.strip():
            return False
        
        try:
            vecteur = self.tfidf['vectorizer'].transform([texte])
            sim = cosine_similarity(
                vecteur, self.tfidf['vecteur_ref'].reshape(1, -1)
            )[0, 0]
            
            seuil = SEUILS_TFIDF[self.systeme]
            anomalie = sim < seuil
            
            if anomalie:
                logger.debug(f"Anomalie logs détectée (similarité {sim:.3f} < {seuil})")
            
            return anomalie
        except (ValueError, KeyError) as e:
            logger.warning(f"Erreur détection logs : {e}")
            return False
    
    def detecter_traces(self, df_traces: pd.DataFrame) -> bool:
        """
        Détecte les anomalies dans les traces d'une fenêtre.
        
        Args:
            df_traces : DataFrame avec colonnes service + duration_ms
        
        Returns:
            True si le taux de spans anormaux dépasse le seuil
        """
        if df_traces.empty:
            logger.debug("Traces : DataFrame vide, pas d'anomalie détectable")
            return False
        
        nb_anomalies = 0
        nb_total = 0
        
        for service in df_traces['service'].unique():
            if service not in self.if_traces['modeles']:
                continue
            df_svc = df_traces[df_traces['service'] == service][['duration_ms']].dropna()
            if df_svc.empty:
                continue
            
            try:
                X = self.if_traces['scalers'][service].transform(df_svc)
                pred = self.if_traces['modeles'][service].predict(X)
                nb_anomalies += (pred == -1).sum()
                nb_total += len(pred)
            except (ValueError, KeyError) as e:
                logger.warning(f"Erreur détection traces sur {service} : {e}")
                continue
        
        if nb_total == 0:
            return False
        
        taux = nb_anomalies / nb_total
        anomalie = taux > SEUIL_IF_TRACES
        
        if anomalie:
            logger.debug(
                f"Anomalie traces détectée (taux {taux:.2%} > {SEUIL_IF_TRACES:.2%})"
            )
        
        return anomalie
    
    def detecter_toutes(self, fenetre_data: Dict[str, pd.DataFrame]) -> Dict[str, bool]:
        """
        Applique les 3 détecteurs sur une fenêtre complète.
        
        Args:
            fenetre_data : dict avec clés 'metriques', 'logs', 'traces'
        
        Returns:
            dict avec 3 booléens (une clé par modalité)
        
        Raises:
            DataError : si les clés attendues sont manquantes
        """
        cles_requises = {'metriques', 'logs', 'traces'}
        cles_manquantes = cles_requises - set(fenetre_data.keys())
        if cles_manquantes:
            raise DataError(
                f"Clés manquantes dans fenetre_data : {cles_manquantes}"
            )
        
        detections = {
            'metriques': self.detecter_metriques(fenetre_data['metriques']),
            'logs'     : self.detecter_logs(fenetre_data['logs']),
            'traces'   : self.detecter_traces(fenetre_data['traces']),
        }
        
        nb_detections = sum(detections.values())
        logger.info(
            f"Détections : {nb_detections}/3 modalités "
            f"(métriques={detections['metriques']}, "
            f"logs={detections['logs']}, "
            f"traces={detections['traces']})"
        )
        
        return detections



# FONCTIONS DE FUSION ET CLASSIFICATION


def fusionner(detections: Dict[str, bool], strategie: str = 'or') -> bool:
    """
    Fusionne les détections des 3 modalités en une décision unique.
    
    Args:
        detections : dict avec 'metriques', 'logs', 'traces' → bool
        strategie  : 'or', 'vote_majoritaire' ou 'and'
    
    Returns:
        True si anomalie détectée
    
    Raises:
        DataError : si strategie est invalide ou detections mal formé
    """
    cles_requises = {'metriques', 'logs', 'traces'}
    cles_manquantes = cles_requises - set(detections.keys())
    if cles_manquantes:
        raise DataError(f"Clés manquantes dans detections : {cles_manquantes}")
    
    if strategie not in STRATEGIES_VALIDES:
        raise DataError(
            f"Stratégie inconnue : '{strategie}'. Valeurs autorisées : {STRATEGIES_VALIDES}"
        )
    
    valeurs = [
        detections['metriques'],
        detections['logs'],
        detections['traces'],
    ]
    
    if strategie == 'or':
        return any(valeurs)
    elif strategie == 'vote_majoritaire':
        return sum(valeurs) >= 2
    else:  # 'and'
        return all(valeurs)


def classifier(detections: Dict[str, bool]) -> str:
    """
    Classifie la sévérité selon le nombre de modalités confirmant.
    
    Args:
        detections : dict avec 'metriques', 'logs', 'traces' → bool
    
    Returns:
        'CRITICAL', 'WARNING', 'LOW' ou 'NORMAL'
    
    Raises:
        DataError : si detections mal formé
    """
    cles_requises = {'metriques', 'logs', 'traces'}
    cles_manquantes = cles_requises - set(detections.keys())
    if cles_manquantes:
        raise DataError(f"Clés manquantes dans detections : {cles_manquantes}")
    
    nb = sum([detections['metriques'], detections['logs'], detections['traces']])
    
    if nb == 3:
        return 'CRITICAL'
    elif nb == 2:
        return 'WARNING'
    elif nb == 1:
        return 'LOW'
    else:
        return 'NORMAL'


def score_confiance(detections: Dict[str, bool]) -> float:
    """
    Calcule un score de confiance basé sur le nombre de modalités.
    
    Args:
        detections : dict avec 3 booléens
    
    Returns:
        float entre 0 et 1
    
    Raises:
        DataError : si detections mal formé
    """
    cles_requises = {'metriques', 'logs', 'traces'}
    cles_manquantes = cles_requises - set(detections.keys())
    if cles_manquantes:
        raise DataError(f"Clés manquantes dans detections : {cles_manquantes}")
    
    nb = sum([detections['metriques'], detections['logs'], detections['traces']])
    return nb / 3.0


def obtenir_action(severite: str) -> str:
    """
    Retourne l'action recommandée selon la sévérité.
    
    Args:
        severite : 'CRITICAL', 'WARNING', 'LOW' ou 'NORMAL'
    
    Returns:
        action recommandée en langage naturel
    """
    actions = {
        'CRITICAL': 'Action immédiate requise — investigation prioritaire',
        'WARNING' : 'Alerte modérée — investigation à planifier',
        'LOW'     : 'Signal faible — vérifier la modalité concernée',
        'NORMAL'  : 'Surveillance passive — aucune action requise',
    }
    return actions.get(severite, 'Statut inconnu')


if __name__ == '__main__':
    # Test rapide
    from pipeline.ingestion import IngestionEngine
    
    print("Test — Détection sur fenêtre 08_43 de Train Ticket")
    
    try:
        ingestion = IngestionEngine('data')
        detecteur = DetecteurAnomalies(systeme='train_ticket')
        
        donnees = ingestion.charger_fenetre_complete('anomalies', '2023-01-29', '08_43')
        detections = detecteur.detecter_toutes(donnees)
        
        print(f"\n  Détections : {detections}")
        print(f"  Fusion OR         : {fusionner(detections, 'or')}")
        print(f"  Fusion Vote maj.  : {fusionner(detections, 'vote_majoritaire')}")
        print(f"  Fusion AND        : {fusionner(detections, 'and')}")
        print(f"  Classification    : {classifier(detections)}")
        print(f"  Confiance         : {score_confiance(detections)*100:.0f}%")
        print(f"  Action            : {obtenir_action(classifier(detections))}")
        
        # Test des validations
        print("\n  Test des validations :")
        try:
            fusionner(detections, 'invalide')
        except DataError as e:
            print(f"    ✓ DataError capturée : {e}")
        
        try:
            fusionner({'metriques': True})  # clés manquantes
        except DataError as e:
            print(f"    ✓ DataError capturée : {e}")
    
    except (DataError, ModelError) as e:
        print(f"\n❌ Erreur : {e}")