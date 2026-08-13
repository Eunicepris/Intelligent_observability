"""
Module de classification du type de panne.

Utilise un Random Forest supervisé pour prédire le type de panne
(cpu_problem, exception, network_delay, return) étant donnée une fenêtre anormale.

Performance : F1-weighted = 63% (cross-validation 5-fold, version V3 à 4 classes)
"""
import pickle
from pathlib import Path
from typing import Any, Dict

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

# Ordre des 20 features pour le modèle
FEATURES_ORDER = [
    'metriques_detecte', 'score_metriques',
    'cpu_mean', 'cpu_max', 'cpu_std',
    'mem_mean', 'mem_max',
    'lat_p99_mean', 'lat_p99_max',
    'net_rx_total', 'net_tx_total',
    'logs_detecte', 'score_logs', 'nb_logs',
    'traces_detecte', 'score_traces',
    'nb_spans', 'duree_moy_spans',
    'duree_max_spans', 'duree_std_spans',
]

# Seuils utilisés lors de l'extraction des features (identiques à detection.py)
SEUILS_TFIDF = {
    'train_ticket'   : 0.95,
    'online_boutique': 0.7,
}
SEUIL_IF_TRACES = 0.12

# Systèmes supportés
SYSTEMES_VALIDES = {'train_ticket', 'online_boutique'}

# Actions recommandées par type de panne
ACTIONS_PAR_TYPE = {
    'cpu_problem'   : 'Analyser utilisation CPU (top, htop) — contention ou saturation',
    'exception'     : 'Consulter les logs applicatifs (stack traces)',
    'network_delay' : 'Vérifier latence réseau (ping, mtr)',
    'return'        : 'Vérifier valeurs retournées par le service',
}


class ClassificateurTypePanne:
    """
    Classificateur supervisé du type de panne.
    
    Charge un Random Forest pré-entraîné et prédit le type parmi
    4 catégories (cpu_problem, exception, network_delay, return).
    """
    
    def __init__(self, models_dir: str = 'models'):
        """
        Initialise le classificateur en chargeant le modèle pré-entraîné.
        
        Args:
            models_dir : chemin vers le dossier models/
        
        Raises:
            ModelError : si le modèle est introuvable ou corrompu
        """
        self.models_dir = Path(models_dir)
        
        if not self.models_dir.exists():
            raise ModelError(f"Dossier de modèles introuvable : {self.models_dir}")
        
        self._charger_modele()
        logger.info(
            f"ClassificateurTypePanne initialisé "
            f"(F1-weighted moyen : {self.f1_moyen*100:.1f}%)"
        )
    
    def _charger_modele(self) -> None:
        """
        Charge le modèle Random Forest pré-entraîné.
        
        Raises:
            ModelError : si le fichier est introuvable, corrompu ou mal formé
        """
        chemin = self.models_dir / 'classifier_type_panne.pkl'
        
        if not chemin.exists():
            raise ModelError(
                f"Modèle de classification introuvable : {chemin}. "
                f"Vérifiez que le notebook 14 a été exécuté."
            )
        
        try:
            with open(chemin, 'rb') as f:
                data = pickle.load(f)
        except (pickle.UnpicklingError, EOFError) as e:
            raise ModelError(
                f"Modèle corrompu ou incompatible : {chemin}. "
                f"Erreur : {e}. Vérifiez la version de scikit-learn utilisée."
            )
        
        # Validation de la structure du pickle
        cles_requises = {'modele', 'features', 'classes', 'f1_weighted', 'performances'}
        cles_manquantes = cles_requises - set(data.keys())
        if cles_manquantes:
            raise ModelError(
                f"Structure du modèle invalide : clés manquantes {cles_manquantes}"
            )
        
        self.modele = data['modele']
        self.features = data['features']
        self.classes = data['classes']
        self.f1_moyen = data['f1_weighted']
        self.performances = data['performances']
        
        logger.debug(f"Modèle chargé : {len(self.classes)} classes, {len(self.features)} features")
    
    def extraire_features(
        self,
        fenetre_data: Dict[str, pd.DataFrame],
        detecteur: Any,
        systeme: str,
    ) -> np.ndarray:
        """
        Extrait les 20 features nécessaires depuis les données brutes.
        
        Args:
            fenetre_data : dict {'metriques', 'logs', 'traces'}
            detecteur    : instance de DetecteurAnomalies (avec modèles chargés)
            systeme      : 'train_ticket' ou 'online_boutique'
        
        Returns:
            np.array de 20 features prêtes pour la prédiction (shape [1, 20])
        
        Raises:
            DataError : si systeme invalide ou clés manquantes
        """
        if systeme not in SYSTEMES_VALIDES:
            raise DataError(
                f"Systeme invalide : '{systeme}'. Valeurs autorisées : {SYSTEMES_VALIDES}"
            )
        
        cles_requises = {'metriques', 'logs', 'traces'}
        cles_manquantes = cles_requises - set(fenetre_data.keys())
        if cles_manquantes:
            raise DataError(f"Clés manquantes dans fenetre_data : {cles_manquantes}")
        
        features: Dict[str, float] = {}
        
        # ─── MÉTRIQUES ───
        self._extraire_features_metriques(features, fenetre_data['metriques'], detecteur)
        
        # ─── LOGS ───
        self._extraire_features_logs(features, fenetre_data['logs'], detecteur, systeme)
        
        # ─── TRACES ───
        self._extraire_features_traces(features, fenetre_data['traces'], detecteur)
        
        # Convertir en array ordonné
        return np.array([features[f] for f in FEATURES_ORDER]).reshape(1, -1)
    
    def _extraire_features_metriques(
        self,
        features: Dict[str, float],
        df_met: pd.DataFrame,
        detecteur: Any,
    ) -> None:
        """Extrait les features liées aux métriques."""
        # Valeurs par défaut
        features['metriques_detecte'] = 0
        features['score_metriques'] = 0.0
        features['cpu_mean'] = features['cpu_max'] = features['cpu_std'] = 0.0
        features['mem_mean'] = features['mem_max'] = 0.0
        features['lat_p99_mean'] = features['lat_p99_max'] = 0.0
        features['net_rx_total'] = features['net_tx_total'] = 0.0
        
        if df_met.empty:
            return
        
        # Détection LOF par service
        for service in df_met['service'].unique():
            if service not in detecteur.lof['modeles']:
                continue
            df_svc = df_met[df_met['service'] == service][METRIQUES].dropna()
            if df_svc.empty:
                continue
            
            try:
                X = detecteur.lof['scalers'][service].transform(df_svc)
                pred = detecteur.lof['modeles'][service].predict(X)
                scores = detecteur.lof['modeles'][service].decision_function(X)
                if (pred == -1).any():
                    features['metriques_detecte'] = 1
                features['score_metriques'] = max(
                    features['score_metriques'], -scores.min()
                )
            except (ValueError, KeyError) as e:
                logger.warning(f"Erreur extraction features LOF sur {service} : {e}")
                continue
        
        # Statistiques métriques (agrégées sur tous les services)
        for col_data, prefix in [
            ('CpuUsageRate(%)', 'cpu'),
            ('MemoryUsageRate(%)', 'mem'),
            ('PodServerLatencyP99(s)', 'lat_p99'),
        ]:
            serie = df_met[col_data].dropna()
            if len(serie) > 0:
                features[f'{prefix}_mean'] = float(serie.mean())
                features[f'{prefix}_max'] = float(serie.max())
                if prefix == 'cpu':  # seul CPU a un std dans les features
                    features['cpu_std'] = float(serie.std()) if len(serie) > 1 else 0.0
        
        # Réseau (somme)
        for col, target in [
            ('NetworkReceiveBytes', 'net_rx_total'),
            ('NetworkTransmitBytes', 'net_tx_total'),
        ]:
            serie = df_met[col].dropna()
            if len(serie) > 0:
                features[target] = float(serie.sum())
    
    def _extraire_features_logs(
        self,
        features: Dict[str, float],
        df_logs: pd.DataFrame,
        detecteur: Any,
        systeme: str,
    ) -> None:
        """Extrait les features liées aux logs."""
        features['logs_detecte'] = 0
        features['score_logs'] = 0.0
        features['nb_logs'] = len(df_logs)
        
        if df_logs.empty:
            return
        
        texte = ' '.join(df_logs['template'].tolist())
        if not texte.strip():
            return
        
        try:
            vecteur = detecteur.tfidf['vectorizer'].transform([texte])
            sim = cosine_similarity(
                vecteur, detecteur.tfidf['vecteur_ref'].reshape(1, -1)
            )[0, 0]
            features['score_logs'] = float(1 - sim)
            if sim < SEUILS_TFIDF[systeme]:
                features['logs_detecte'] = 1
        except (ValueError, KeyError) as e:
            logger.warning(f"Erreur extraction features logs : {e}")
    
    def _extraire_features_traces(
        self,
        features: Dict[str, float],
        df_traces: pd.DataFrame,
        detecteur: Any,
    ) -> None:
        """Extrait les features liées aux traces."""
        features['traces_detecte'] = 0
        features['score_traces'] = 0.0
        features['nb_spans'] = len(df_traces)
        features['duree_moy_spans'] = 0.0
        features['duree_max_spans'] = 0.0
        features['duree_std_spans'] = 0.0
        
        if df_traces.empty:
            return
        
        durees = df_traces['duration_ms'].dropna()
        if len(durees) > 0:
            features['duree_moy_spans'] = float(durees.mean())
            features['duree_max_spans'] = float(durees.max())
            features['duree_std_spans'] = float(durees.std()) if len(durees) > 1 else 0.0
        
        # Détection par service
        nb_anomalies, nb_total = 0, 0
        for service in df_traces['service'].unique():
            if service not in detecteur.if_traces['modeles']:
                continue
            df_svc = df_traces[df_traces['service'] == service][['duration_ms']].dropna()
            if df_svc.empty:
                continue
            
            try:
                X = detecteur.if_traces['scalers'][service].transform(df_svc)
                pred = detecteur.if_traces['modeles'][service].predict(X)
                nb_anomalies += (pred == -1).sum()
                nb_total += len(pred)
            except (ValueError, KeyError) as e:
                logger.warning(f"Erreur extraction features traces sur {service} : {e}")
                continue
        
        if nb_total > 0:
            features['score_traces'] = float(nb_anomalies / nb_total)
            if features['score_traces'] > SEUIL_IF_TRACES:
                features['traces_detecte'] = 1
    
    def predire(
        self,
        fenetre_data: Dict[str, pd.DataFrame],
        detecteur: Any,
        systeme: str,
    ) -> Dict[str, Any]:
        """
        Prédit le type de panne d'une fenêtre anormale.
        
        Args:
            fenetre_data : dict {'metriques', 'logs', 'traces'}
            detecteur    : instance de DetecteurAnomalies
            systeme      : 'train_ticket' ou 'online_boutique'
        
        Returns:
            dict avec :
            - type_predit       : classe prédite
            - confiance         : probabilité de la classe prédite (0-1)
            - probabilites      : dict {classe: probabilité}
            - action_specifique : action recommandée
        
        Raises:
            DataError  : si les paramètres sont invalides
            ModelError : si la prédiction échoue
        """
        X = self.extraire_features(fenetre_data, detecteur, systeme)
        
        try:
            type_predit = self.modele.predict(X)[0]
            probabilites = self.modele.predict_proba(X)[0]
        except (ValueError, RuntimeError) as e:
            raise ModelError(f"Erreur de prédiction : {e}")
        
        # Confiance = probabilité de la classe prédite
        idx_predit = list(self.modele.classes_).index(type_predit)
        confiance = float(probabilites[idx_predit])
        
        resultat = {
            'type_predit'  : str(type_predit),
            'confiance'    : confiance,
            'probabilites' : {
                str(c): float(p) for c, p in zip(self.modele.classes_, probabilites)
            },
            'action_specifique': self._obtenir_action(str(type_predit)),
        }
        
        logger.info(
            f"Type prédit : {resultat['type_predit']} "
            f"(confiance {confiance*100:.0f}%)"
        )
        
        return resultat
    
    def _obtenir_action(self, type_panne: str) -> str:
        """
        Retourne une action spécifique selon le type de panne.
        
        Args:
            type_panne : type de panne prédit
        
        Returns:
            action recommandée en langage naturel
        """
        return ACTIONS_PAR_TYPE.get(type_panne, 'Investigation générale requise')


if __name__ == '__main__':
    # Test rapide
    from pipeline.ingestion import IngestionEngine
    from pipeline.detection import DetecteurAnomalies
    
    try:
        ingestion = IngestionEngine('data')
        detecteur = DetecteurAnomalies(systeme='train_ticket')
        classificateur = ClassificateurTypePanne()
        
        print(f"Classes possibles : {classificateur.classes}")
        print(f"F1-weighted moyen : {classificateur.f1_moyen*100:.1f}%")
        print(f"\nTest sur fenêtre 08_43 de Train Ticket (panne 'return')")
        
        donnees = ingestion.charger_fenetre_complete('anomalies', '2023-01-29', '08_43')
        resultat = classificateur.predire(donnees, detecteur, 'train_ticket')
        
        print(f"\n  Type prédit : {resultat['type_predit']}")
        print(f"  Confiance   : {resultat['confiance']*100:.0f}%")
        print(f"  Action      : {resultat['action_specifique']}")
        print(f"\n  Probabilités par classe :")
        for classe, prob in sorted(resultat['probabilites'].items(), key=lambda x: -x[1]):
            print(f"    {classe:<20} : {prob*100:.0f}%")
        
        # Test des validations
        print("\n  Test des validations :")
        try:
            classificateur.extraire_features(donnees, detecteur, 'invalide')
        except DataError as e:
            print(f"    ✓ DataError capturée : {e}")
        
        try:
            classificateur.extraire_features({}, detecteur, 'train_ticket')
        except DataError as e:
            print(f"    ✓ DataError capturée : {e}")
    
    except (DataError, ModelError) as e:
        print(f"\n❌ Erreur : {e}")