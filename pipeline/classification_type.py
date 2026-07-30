"""
Module de classification du type de panne.

Utilise un Random Forest supervisé pour prédire le type de panne
(cpu_consumed, cpu_contention, exception, network_delay, return)
étant donnée une fenêtre anormale.

Performance : F1-weighted = 57.3% (cross-validation 5-fold)
"""
import pickle
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import timedelta
from sklearn.metrics.pairwise import cosine_similarity


METRIQUES = [
    'CpuUsageRate(%)',
    'MemoryUsageRate(%)',
    'PodServerLatencyP99(s)',
    'NetworkReceiveBytes',
    'NetworkTransmitBytes',
]

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


class ClassificateurTypePanne:
    """
    Classificateur supervisé du type de panne.
    
    Charge un Random Forest pré-entraîné et prédit le type
    parmi 5 catégories (cpu_consumed, cpu_contention, exception,
    network_delay, return).
    """
    
    def __init__(self, models_dir='models'):
        self.models_dir = Path(models_dir)
        self._charger_modele()
    
    def _charger_modele(self):
        """Charge le modèle Random Forest pré-entraîné."""
        with open(self.models_dir / 'classifier_type_panne.pkl', 'rb') as f:
            data = pickle.load(f)
        
        self.modele       = data['modele']
        self.features     = data['features']
        self.classes      = data['classes']
        self.f1_moyen     = data['f1_weighted']
        self.performances = data['performances']
    
    def extraire_features(self, fenetre_data, detecteur, systeme):
        """
        Extrait les 20 features nécessaires depuis les données brutes.
        
        Args:
            fenetre_data : dict {'metriques', 'logs', 'traces'}
            detecteur    : instance de DetecteurAnomalies
            systeme      : 'train_ticket' ou 'online_boutique'
        
        Returns:
            np.array de 20 features prêtes pour la prédiction
        """
        SEUILS_TFIDF = {'train_ticket': 0.95, 'online_boutique': 0.7}
        SEUIL_IF = 0.12
        
        features = {}
        
        # ─── MÉTRIQUES ───
        df_met = fenetre_data['metriques']
        features['metriques_detecte'] = 0
        features['score_metriques']   = 0.0
        features['cpu_mean']  = features['cpu_max']  = features['cpu_std'] = 0.0
        features['mem_mean']  = features['mem_max']  = 0.0
        features['lat_p99_mean'] = features['lat_p99_max'] = 0.0
        features['net_rx_total'] = features['net_tx_total'] = 0.0
        
        if not df_met.empty:
            # Détection LOF
            for service in df_met['service'].unique():
                if service not in detecteur.lof['modeles']:
                    continue
                df_svc = df_met[df_met['service'] == service][METRIQUES].dropna()
                if df_svc.empty:
                    continue
                X = detecteur.lof['scalers'][service].transform(df_svc)
                pred = detecteur.lof['modeles'][service].predict(X)
                scores = detecteur.lof['modeles'][service].decision_function(X)
                if (pred == -1).any():
                    features['metriques_detecte'] = 1
                features['score_metriques'] = max(features['score_metriques'], -scores.min())
            
            # Statistiques métriques
            cpu = df_met['CpuUsageRate(%)'].dropna()
            if len(cpu) > 0:
                features['cpu_mean'] = float(cpu.mean())
                features['cpu_max']  = float(cpu.max())
                features['cpu_std']  = float(cpu.std()) if len(cpu) > 1 else 0.0
            
            mem = df_met['MemoryUsageRate(%)'].dropna()
            if len(mem) > 0:
                features['mem_mean'] = float(mem.mean())
                features['mem_max']  = float(mem.max())
            
            lat = df_met['PodServerLatencyP99(s)'].dropna()
            if len(lat) > 0:
                features['lat_p99_mean'] = float(lat.mean())
                features['lat_p99_max']  = float(lat.max())
            
            net_rx = df_met['NetworkReceiveBytes'].dropna()
            if len(net_rx) > 0:
                features['net_rx_total'] = float(net_rx.sum())
            
            net_tx = df_met['NetworkTransmitBytes'].dropna()
            if len(net_tx) > 0:
                features['net_tx_total'] = float(net_tx.sum())
        
        # ─── LOGS ───
        df_logs = fenetre_data['logs']
        features['logs_detecte'] = 0
        features['score_logs']   = 0.0
        features['nb_logs']      = len(df_logs)
        
        if not df_logs.empty:
            texte = ' '.join(df_logs['template'].tolist())
            if texte.strip():
                vecteur = detecteur.tfidf['vectorizer'].transform([texte])
                sim = cosine_similarity(
                    vecteur, detecteur.tfidf['vecteur_ref'].reshape(1, -1)
                )[0, 0]
                features['score_logs'] = float(1 - sim)
                if sim < SEUILS_TFIDF[systeme]:
                    features['logs_detecte'] = 1
        
        # ─── TRACES ───
        df_traces = fenetre_data['traces']
        features['traces_detecte']  = 0
        features['score_traces']    = 0.0
        features['nb_spans']        = len(df_traces)
        features['duree_moy_spans'] = 0.0
        features['duree_max_spans'] = 0.0
        features['duree_std_spans'] = 0.0
        
        if not df_traces.empty:
            durees = df_traces['duration_ms'].dropna()
            if len(durees) > 0:
                features['duree_moy_spans'] = float(durees.mean())
                features['duree_max_spans'] = float(durees.max())
                features['duree_std_spans'] = float(durees.std()) if len(durees) > 1 else 0.0
            
            nb_anomalies, nb_total = 0, 0
            for service in df_traces['service'].unique():
                if service not in detecteur.if_traces['modeles']:
                    continue
                df_svc = df_traces[df_traces['service'] == service][['duration_ms']].dropna()
                if df_svc.empty:
                    continue
                X = detecteur.if_traces['scalers'][service].transform(df_svc)
                pred = detecteur.if_traces['modeles'][service].predict(X)
                nb_anomalies += (pred == -1).sum()
                nb_total += len(pred)
            
            if nb_total > 0:
                features['score_traces'] = float(nb_anomalies / nb_total)
                if features['score_traces'] > SEUIL_IF:
                    features['traces_detecte'] = 1
        
        # Convertir en array ordonné
        return np.array([features[f] for f in FEATURES_ORDER]).reshape(1, -1)
    
    def predire(self, fenetre_data, detecteur, systeme):
        """
        Prédit le type de panne d'une fenêtre anormale.
        
        Returns:
            dict avec 'type_predit', 'confiance', 'probabilites'
        """
        X = self.extraire_features(fenetre_data, detecteur, systeme)
        
        # Prédiction
        type_predit = self.modele.predict(X)[0]
        probabilites = self.modele.predict_proba(X)[0]
        
        # Confiance = probabilité de la classe prédite
        idx_predit = list(self.modele.classes_).index(type_predit)
        confiance = float(probabilites[idx_predit])
        
        return {
            'type_predit'  : str(type_predit),
            'confiance'    : confiance,
            'probabilites' : {
                str(c): float(p) for c, p in zip(self.modele.classes_, probabilites)
            },
            'action_specifique': self._obtenir_action(type_predit),
        }
    
    def _obtenir_action(self, type_panne):
        """Retourne une action spécifique selon le type de panne."""
        actions = {
            'cpu_problem'   : 'Analyser utilisation CPU (top, htop) — contention ou saturation',
            'exception'     : 'Consulter les logs applicatifs (stack traces)',
            'network_delay' : 'Vérifier latence réseau (ping, mtr)',
            'return'        : 'Vérifier valeurs retournées par le service',
        }
        return actions.get(type_panne, 'Investigation générale requise')

if __name__ == '__main__':
    # Test rapide
    from pipeline.ingestion import IngestionEngine
    from pipeline.detection import DetecteurAnomalies
    
    ingestion = IngestionEngine('/home/eunice/Bureau/Train_ticket/Intelligent_observability/data')
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