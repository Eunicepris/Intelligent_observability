"""
Module d'ingestion des données.

Charge les métriques, logs et traces depuis les fichiers Nezha.
Utilisé par le pipeline de détection.
"""
import csv
import re
import pandas as pd
from pathlib import Path
from datetime import timedelta


class IngestionEngine:
    """
    Moteur de chargement des données pour le pipeline.
    
    Charge les 3 modalités (métriques, logs, traces) depuis les fichiers
    du dataset Nezha structuré en construct_data (normal) et rca_data (anomalies).
    """
    
    METRIQUES = [
        'CpuUsageRate(%)',
        'MemoryUsageRate(%)',
        'PodServerLatencyP99(s)',
        'NetworkReceiveBytes',
        'NetworkTransmitBytes',
    ]
    
    def __init__(self, base_path):
        """
        Args:
            base_path : chemin vers le dossier data/ contenant normal/ et anomalies/
        """
        self.base_path = Path(base_path)
        self.normal_path    = self.base_path / 'normal'
        self.anomalies_path = self.base_path / 'anomalies'
    
    def _obtenir_chemin(self, source):
        """Convertit 'normal' ou 'anomalies' en chemin réel."""
        if source == 'normal':
            return self.normal_path
        elif source == 'anomalies':
            return self.anomalies_path
        else:
            raise ValueError(f"Source inconnue: {source}. Utilisez 'normal' ou 'anomalies'.")
    
    def charger_metriques(self, source, date):
        """
        Charge toutes les métriques d'une date pour tous les services.
        
        Args:
            source : 'normal' ou 'anomalies'
            date   : ex '2023-01-29'
        
        Returns:
            DataFrame avec colonnes : datetime, service, métriques
        """
        source_path = self._obtenir_chemin(source)
        metric_dir  = source_path / date / 'metric'
        
        if not metric_dir.exists():
            return pd.DataFrame()
        
        dfs = []
        for f in sorted(metric_dir.glob('*_metric.csv')):
            service = f.stem.rsplit('-', 2)[0]
            df = pd.read_csv(f)
            df['service']  = service
            df['datetime'] = pd.to_datetime(df['TimeStamp'], unit='s', utc=True)
            
            for col in df.columns:
                if col not in ['Time', 'PodName', 'service', 'datetime']:
                    df[col] = pd.to_numeric(
                        df[col].replace('NaN', float('nan')), errors='coerce'
                    )
            dfs.append(df)
        
        return pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()
    
    def charger_metriques_fenetre(self, source, date, window):
        """
        Charge les métriques d'une fenêtre spécifique (1 minute).
        
        Args:
            source : 'normal' ou 'anomalies'
            date   : ex '2023-01-29'
            window : ex '08_43' (heure_minute)
        
        Returns:
            DataFrame filtré sur la fenêtre
        """
        df = self.charger_metriques(source, date)
        if df.empty:
            return df
        
        h, m = map(int, window.split('_'))
        t_debut = pd.Timestamp(f"{date} {h:02d}:{m:02d}:00").tz_localize('UTC')
        t_fin   = t_debut + timedelta(minutes=1)
        
        mask = (df['datetime'] >= t_debut) & (df['datetime'] < t_fin)
        return df[mask].copy()
    
    def charger_logs(self, source, date, window):
        """
        Charge les logs d'une fenêtre spécifique.
        
        Args:
            source : 'normal' ou 'anomalies'
            date   : ex '2023-01-29'
            window : ex '08_43'
        
        Returns:
            DataFrame avec colonnes : Timestamp, PodName, service, Log, template
        """
        source_path = self._obtenir_chemin(source)
        chemin = source_path / date / 'log' / f'{window}_log.csv'
        
        if not chemin.exists():
            return pd.DataFrame()
        
        colonnes = ['Timestamp', 'TimeUnixNano', 'Node', 'PodName',
                    'Container', 'TraceID', 'SpanID', 'Log']
        rows = []
        with open(chemin, 'r', encoding='utf-8', errors='replace') as f:
            reader = csv.reader(f)
            next(reader)
            for row in reader:
                if len(row) >= 8:
                    rows.append(row[:8])
        
        if not rows:
            return pd.DataFrame()
        
        df = pd.DataFrame(rows, columns=colonnes)
        df['service']  = df['PodName'].apply(lambda x: str(x).rsplit('-', 2)[0])
        df['template'] = df['Log'].apply(self.extraire_template)
        
        return df
    
    def charger_traces(self, source, date, window):
        """
        Charge les traces d'une fenêtre spécifique.
        
        Args:
            source : 'normal' ou 'anomalies'
            date   : ex '2023-01-29'
            window : ex '08_43'
        
        Returns:
            DataFrame avec colonnes : TraceID, SpanID, ParentID, service, duration_ms
        """
        source_path = self._obtenir_chemin(source)
        chemin = source_path / date / 'trace' / f'{window}_trace.csv'
        
        if not chemin.exists():
            return pd.DataFrame()
        
        df = pd.read_csv(chemin, on_bad_lines='skip')
        df['duration_ms'] = pd.to_numeric(df['Duration'], errors='coerce') / 1e6
        df['service']     = df['PodName'].apply(lambda x: str(x).rsplit('-', 2)[0])
        
        return df
    
    def charger_fenetre_complete(self, source, date, window):
        """
        Charge les 3 modalités pour une fenêtre donnée.
        
        Args:
            source : 'normal' ou 'anomalies'
            date   : ex '2023-01-29'
            window : ex '08_43'
        
        Returns:
            dict avec clés 'metriques', 'logs', 'traces'
        """
        return {
            'metriques': self.charger_metriques_fenetre(source, date, window),
            'logs'     : self.charger_logs(source, date, window),
            'traces'   : self.charger_traces(source, date, window),
        }
    
    @staticmethod
    def extraire_template(log_str):
        """
        Extrait un template depuis un message de log.
        Remplace les identifiants variables (UUID, HEX, NUM) par des tokens.
        """
        log_str = str(log_str)
        
        # Extraire le champ 'log' du JSON si présent
        match = re.search(r'"log"\s*:\s*"([^"]+)"', log_str)
        if match:
            log_str = match.group(1)
        
        # Remplacer UUID, hex, nombres
        log_str = re.sub(
            r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}',
            '<UUID>', log_str)
        log_str = re.sub(r'[0-9a-f]{16,}', '<HEX>', log_str)
        log_str = re.sub(r'\b\d+\.?\d*\b', '<NUM>', log_str)
        
        # Extraire les crochets ou premiers mots
        crochets = re.findall(r'\[([^\]]+)\]', log_str)
        if crochets:
            return ' | '.join(crochets[:3])
        
        return ' '.join(log_str.split()[:6])


if __name__ == '__main__':
    # Test rapide
    ingestion = IngestionEngine('/home/eunice/Bureau/Train_ticket/Intelligent_observability/data')
    
    print("Test — Chargement fenêtre 08_43 de Train Ticket (anomalies)")
    donnees = ingestion.charger_fenetre_complete(
        source='anomalies',
        date='2023-01-29',
        window='08_43'
    )
    
    print(f"\n  Métriques : {len(donnees['metriques'])} lignes")
    print(f"  Logs      : {len(donnees['logs'])} lignes")
    print(f"  Traces    : {len(donnees['traces'])} lignes")