"""
Module de détection d'anomalies multi-modale.

Charge les modèles pré-entraînés (LOF, TF-IDF, IF par service)
et détecte les anomalies par modalité, puis fusionne les résultats.
"""
import pickle
import numpy as np
from pathlib import Path
from sklearn.metrics.pairwise import cosine_similarity


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


class DetecteurAnomalies:
    """
    Détecteur d'anomalies multi-modale.
    
    Utilise 3 modèles pré-entraînés :
    - LOF sur les métriques (par service)
    - TF-IDF sur les logs (similarité cosinus)
    - Isolation Forest sur les traces (par service)
    """
    
    def __init__(self, systeme='train_ticket', models_dir='models'):
        """
        Args:
            systeme    : 'train_ticket' ou 'online_boutique'
            models_dir : chemin vers le dossier models/
        """
        self.systeme = systeme
        self.models_dir = Path(models_dir)
        self.suffix = 'tt' if systeme == 'train_ticket' else 'ob'
        self._charger_modeles()
    
    def _charger_modeles(self):
        """Charge les 3 modèles depuis models/."""
        with open(self.models_dir / f'lof_{self.suffix}.pkl', 'rb') as f:
            self.lof = pickle.load(f)
        
        with open(self.models_dir / f'tfidf_{self.suffix}.pkl', 'rb') as f:
            self.tfidf = pickle.load(f)
        
        with open(self.models_dir / f'if_traces_{self.suffix}.pkl', 'rb') as f:
            self.if_traces = pickle.load(f)
    
    def detecter_metriques(self, df_metriques):
        """
        Détecte les anomalies dans les métriques d'une fenêtre.
        
        Args:
            df_metriques : DataFrame avec colonnes service + METRIQUES
        
        Returns:
            bool : True si au moins un point est anormal
        """
        if df_metriques.empty:
            return False
        
        for service in df_metriques['service'].unique():
            if service not in self.lof['modeles']:
                continue
            df_svc = df_metriques[df_metriques['service'] == service][METRIQUES].dropna()
            if df_svc.empty:
                continue
            X = self.lof['scalers'][service].transform(df_svc)
            pred = self.lof['modeles'][service].predict(X)
            if (pred == -1).any():
                return True
        
        return False
    
    def detecter_logs(self, df_logs, service_cible=None):
        """
        Détecte les anomalies dans les logs d'une fenêtre.
        
        Args:
            df_logs       : DataFrame avec colonnes service + template
            service_cible : si spécifié, analyse uniquement ce service
        
        Returns:
            bool : True si la similarité est inférieure au seuil
        """
        if df_logs.empty:
            return False
        
        # Filtrer par service si spécifié
        if service_cible:
            df_logs = df_logs[df_logs['service'] == service_cible]
            if df_logs.empty:
                return False
        
        texte = ' '.join(df_logs['template'].tolist())
        if not texte.strip():
            return False
        
        vecteur = self.tfidf['vectorizer'].transform([texte])
        sim = cosine_similarity(vecteur, self.tfidf['vecteur_ref'].reshape(1, -1))[0, 0]
        
        seuil = SEUILS_TFIDF[self.systeme]
        return sim < seuil
    
    def detecter_traces(self, df_traces):
        """
        Détecte les anomalies dans les traces d'une fenêtre.
        
        Args:
            df_traces : DataFrame avec colonnes service + duration_ms
        
        Returns:
            bool : True si le taux de spans anormaux dépasse le seuil
        """
        if df_traces.empty:
            return False
        
        nb_anomalies = 0
        nb_total = 0
        
        for service in df_traces['service'].unique():
            if service not in self.if_traces['modeles']:
                continue
            df_svc = df_traces[df_traces['service'] == service][['duration_ms']].dropna()
            if df_svc.empty:
                continue
            X = self.if_traces['scalers'][service].transform(df_svc)
            pred = self.if_traces['modeles'][service].predict(X)
            nb_anomalies += (pred == -1).sum()
            nb_total     += len(pred)
        
        if nb_total == 0:
            return False
        
        taux = nb_anomalies / nb_total
        return taux > SEUIL_IF_TRACES
    
    def detecter_toutes(self, fenetre_data):
        """
        Applique les 3 détecteurs sur une fenêtre complète.
        
        Args:
            fenetre_data : dict avec clés 'metriques', 'logs', 'traces'
        
        Returns:
            dict avec 3 booléens (une clé par modalité)
        """
        return {
            'metriques': self.detecter_metriques(fenetre_data['metriques']),
            'logs'     : self.detecter_logs(fenetre_data['logs']),
            'traces'   : self.detecter_traces(fenetre_data['traces']),
        }


# ═══════════════════════════════════════════
# FONCTIONS DE FUSION ET CLASSIFICATION
# ═══════════════════════════════════════════

def fusionner(detections, strategie='or'):
    """
    Fusionne les détections des 3 modalités en une décision unique.
    
    Args:
        detections : dict avec 'metriques', 'logs', 'traces' → bool
        strategie  : 'or', 'vote_majoritaire' ou 'and'
    
    Returns:
        bool : True si anomalie détectée
    """
    valeurs = [
        detections['metriques'],
        detections['logs'],
        detections['traces'],
    ]
    
    if strategie == 'or':
        return any(valeurs)
    elif strategie == 'vote_majoritaire':
        return sum(valeurs) >= 2
    elif strategie == 'and':
        return all(valeurs)
    else:
        raise ValueError(f"Stratégie inconnue: {strategie}")


def classifier(detections):
    """
    Classifie la sévérité selon le nombre de modalités confirmant.
    
    Args:
        detections : dict avec 'metriques', 'logs', 'traces' → bool
    
    Returns:
        str : 'CRITICAL', 'WARNING', 'LOW' ou 'NORMAL'
    """
    nb = sum([detections['metriques'], detections['logs'], detections['traces']])
    if nb == 3:
        return 'CRITICAL'
    elif nb == 2:
        return 'WARNING'
    elif nb == 1:
        return 'LOW'
    else:
        return 'NORMAL'


def score_confiance(detections):
    """
    Calcule un score de confiance basé sur le nombre de modalités.
    
    Args:
        detections : dict avec 3 booléens
    
    Returns:
        float entre 0 et 1
    """
    nb = sum([detections['metriques'], detections['logs'], detections['traces']])
    return nb / 3.0


def obtenir_action(severite):
    """
    Retourne l'action recommandée selon la sévérité.
    
    Args:
        severite : 'CRITICAL', 'WARNING', 'LOW' ou 'NORMAL'
    
    Returns:
        str : action recommandée
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
    
    ingestion = IngestionEngine('/home/eunice/Bureau/Train_ticket/Intelligent_observability/data')
    detecteur = DetecteurAnomalies(systeme='train_ticket')
    
    print("Test — Détection sur fenêtre 08_43 de Train Ticket")
    donnees = ingestion.charger_fenetre_complete('anomalies', '2023-01-29', '08_43')
    detections = detecteur.detecter_toutes(donnees)
    
    print(f"\n  Détections : {detections}")
    print(f"  Fusion OR   : {fusionner(detections, 'or')}")
    print(f"  Classification : {classifier(detections)}")
    print(f"  Confiance   : {score_confiance(detections)*100:.0f}%")
    print(f"  Action      : {obtenir_action(classifier(detections))}")