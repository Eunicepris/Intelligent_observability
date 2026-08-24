"""
Module d'ingestion des données.

Charge les métriques, logs et traces depuis les fichiers Nezha.
Utilisé par le pipeline de détection.
"""

import csv
import re
from datetime import timedelta
from pathlib import Path
from typing import Any, Dict

import pandas as pd

from pipeline.exceptions import DataError, InvalidInputError
from pipeline.logger import setup_logging

logger = setup_logging(__name__)

# Sources autorisées
SOURCES_VALIDES = {"normal", "anomalies"}

# Format attendu pour la date : YYYY-MM-DD
REGEX_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# Format attendu pour la fenêtre : HH_MM
# Format HH_MM avec HH dans [00, 23] et MM dans [00, 59]
REGEX_WINDOW = re.compile(r"^([01]\d|2[0-3])_[0-5]\d$")


class IngestionEngine:
    """
    Moteur de chargement des données pour le pipeline.

    Charge les 3 modalités (métriques, logs, traces) depuis les fichiers
    du dataset Nezha structuré en construct_data (normal) et rca_data (anomalies).
    """

    METRIQUES = [
        "CpuUsageRate(%)",
        "MemoryUsageRate(%)",
        "PodServerLatencyP99(s)",
        "NetworkReceiveBytes",
        "NetworkTransmitBytes",
    ]

    def __init__(self, base_path: str):
        """
        Initialise le moteur d'ingestion.

        Args:
            base_path : chemin vers le dossier data/ contenant normal/ et anomalies/

        Raises:
            DataError : si base_path n'existe pas
        """
        self.base_path = Path(base_path)

        if not self.base_path.exists():
            raise DataError(
                f"Chemin de données introuvable : {self.base_path}. "
                f"Vérifiez que le dossier data/ existe et contient normal/ et anomalies/."
            )

        self.normal_path = self.base_path / "normal"
        self.anomalies_path = self.base_path / "anomalies"

        logger.debug(f"IngestionEngine initialisé avec {self.base_path}")

    def _obtenir_chemin(self, source: str) -> Path:
        """
        Convertit 'normal' ou 'anomalies' en chemin réel.

        Args:
            source : 'normal' ou 'anomalies'

        Returns:
            Path vers le dossier correspondant

        Raises:
            DataError : si source n'est pas valide
        """
        if source not in SOURCES_VALIDES:
            raise DataError(f"Source inconnue : '{source}'. Valeurs autorisées : {SOURCES_VALIDES}")

        return self.normal_path if source == "normal" else self.anomalies_path

    def _valider_date(self, date: str) -> None:
        """Valide le format de la date (YYYY-MM-DD)."""
        if not REGEX_DATE.match(date):
            raise DataError(f"Format de date invalide : '{date}'. Format attendu : YYYY-MM-DD")

    # def _valider_window(self, window: str) -> None:
    #     """Valide le format de la fenêtre (HH_MM)."""
    #     if not REGEX_WINDOW.match(window):
    #         raise DataError(
    #             f"Format de fenêtre invalide : '{window}'. Format attendu : HH_MM"
    #         )

    def _valider_window(self, window: str) -> None:
        """Valide le format de la fenêtre (HH_MM avec HH∈[00,23] et MM∈[00,59])."""
        if not REGEX_WINDOW.match(window):
            raise InvalidInputError(
                f"Format de fenêtre invalide : '{window}'. "
                f"Format attendu : HH_MM avec HH entre 00 et 23 et MM entre 00 et 59."
            )

    def charger_metriques(self, source: str, date: str) -> pd.DataFrame:
        """
        Charge toutes les métriques d'une date pour tous les services.

        Args:
            source : 'normal' ou 'anomalies'
            date   : ex '2023-01-29'

        Returns:
            DataFrame avec colonnes : datetime, service, métriques.
            DataFrame vide si aucune donnée trouvée pour cette date.

        Raises:
            DataError : si source ou date sont invalides
        """
        self._valider_date(date)
        source_path = self._obtenir_chemin(source)
        metric_dir = source_path / date / "metric"

        if not metric_dir.exists():
            logger.warning(f"Dossier de métriques introuvable : {metric_dir}")
            return pd.DataFrame()

        dfs = []
        fichiers = sorted(metric_dir.glob("*_metric.csv"))

        if not fichiers:
            logger.warning(f"Aucun fichier de métriques dans {metric_dir}")
            return pd.DataFrame()

        for f in fichiers:
            try:
                service = f.stem.rsplit("-", 2)[0]
                df = pd.read_csv(f)
                df["service"] = service
                df["datetime"] = pd.to_datetime(df["TimeStamp"], unit="s", utc=True)

                for col in df.columns:
                    if col not in ["Time", "PodName", "service", "datetime"]:
                        df[col] = pd.to_numeric(df[col].replace("NaN", float("nan")), errors="coerce")
                dfs.append(df)
            except (pd.errors.EmptyDataError, KeyError) as e:
                logger.warning(f"Fichier ignoré {f.name} : {e}")
                continue

        if not dfs:
            return pd.DataFrame()

        resultat = pd.concat(dfs, ignore_index=True)
        logger.info(f"Métriques chargées : {len(resultat)} lignes, {len(dfs)} services")
        return resultat

    def charger_metriques_fenetre(self, source: str, date: str, window: str) -> pd.DataFrame:
        """
        Charge les métriques d'une fenêtre spécifique (1 minute).

        Args:
            source : 'normal' ou 'anomalies'
            date   : ex '2023-01-29'
            window : ex '08_43' (heure_minute)

        Returns:
            DataFrame filtré sur la fenêtre

        Raises:
            DataError : si les paramètres sont invalides
        """
        self._valider_window(window)

        df = self.charger_metriques(source, date)
        if df.empty:
            return df

        h, m = map(int, window.split("_"))
        t_debut = pd.Timestamp(f"{date} {h:02d}:{m:02d}:00").tz_localize("UTC")
        t_fin = t_debut + timedelta(minutes=1)

        mask = (df["datetime"] >= t_debut) & (df["datetime"] < t_fin)
        resultat = df[mask].copy()

        logger.debug(f"Métriques fenêtre {date} {window} : {len(resultat)} lignes")
        return resultat

    def charger_logs(self, source: str, date: str, window: str) -> pd.DataFrame:
        """
        Charge les logs d'une fenêtre spécifique.

        Args:
            source : 'normal' ou 'anomalies'
            date   : ex '2023-01-29'
            window : ex '08_43'

        Returns:
            DataFrame avec colonnes : Timestamp, PodName, service, Log, template.
            DataFrame vide si aucun log trouvé pour cette fenêtre.

        Raises:
            DataError : si les paramètres sont invalides
        """
        self._valider_date(date)
        self._valider_window(window)

        source_path = self._obtenir_chemin(source)
        chemin = source_path / date / "log" / f"{window}_log.csv"

        if not chemin.exists():
            logger.warning(f"Fichier de logs introuvable : {chemin}")
            return pd.DataFrame()

        colonnes = [
            "Timestamp",
            "TimeUnixNano",
            "Node",
            "PodName",
            "Container",
            "TraceID",
            "SpanID",
            "Log",
        ]

        rows = []
        try:
            with open(chemin, "r", encoding="utf-8", errors="replace") as f:
                reader = csv.reader(f)
                next(reader, None)  # skip header
                for row in reader:
                    if len(row) >= 8:
                        rows.append(row[:8])
        except (OSError, csv.Error) as e:
            raise DataError(f"Erreur de lecture du fichier de logs {chemin} : {e}")

        if not rows:
            logger.warning(f"Fichier de logs vide : {chemin}")
            return pd.DataFrame()

        df = pd.DataFrame(rows, columns=colonnes)
        df["service"] = df["PodName"].apply(lambda x: str(x).rsplit("-", 2)[0])
        df["template"] = df["Log"].apply(self.extraire_template)

        logger.debug(f"Logs chargés : {len(df)} lignes")
        return df

    def charger_traces(self, source: str, date: str, window: str) -> pd.DataFrame:
        """
        Charge les traces d'une fenêtre spécifique.

        Args:
            source : 'normal' ou 'anomalies'
            date   : ex '2023-01-29'
            window : ex '08_43'

        Returns:
            DataFrame avec colonnes : TraceID, SpanID, ParentID, service, duration_ms.
            DataFrame vide si aucune trace trouvée pour cette fenêtre.

        Raises:
            DataError : si les paramètres sont invalides
        """
        self._valider_date(date)
        self._valider_window(window)

        source_path = self._obtenir_chemin(source)
        chemin = source_path / date / "trace" / f"{window}_trace.csv"

        if not chemin.exists():
            logger.warning(f"Fichier de traces introuvable : {chemin}")
            return pd.DataFrame()

        try:
            df = pd.read_csv(chemin, on_bad_lines="skip")
        except (pd.errors.EmptyDataError, OSError) as e:
            raise DataError(f"Erreur de lecture du fichier de traces {chemin} : {e}")

        if df.empty:
            logger.warning(f"Fichier de traces vide : {chemin}")
            return df

        df["duration_ms"] = pd.to_numeric(df["Duration"], errors="coerce") / 1e6
        df["service"] = df["PodName"].apply(lambda x: str(x).rsplit("-", 2)[0])

        logger.debug(f"Traces chargées : {len(df)} lignes")
        return df

    # def charger_fenetre_complete(
    #     self, source: str, date: str, window: str
    # ) -> Dict[str, pd.DataFrame]:
    #     """
    #     Charge les 3 modalités pour une fenêtre donnée.

    #     Args:
    #         source : 'normal' ou 'anomalies'
    #         date   : ex '2023-01-29'
    #         window : ex '08_43'

    #     Returns:
    #         dict avec clés 'metriques', 'logs', 'traces' — chacune contenant un DataFrame

    #     Raises:
    #         DataError : si les paramètres sont invalides
    #     """
    #     logger.info(f"Chargement fenêtre complète : {source} / {date} / {window}")

    #     return {
    #         'metriques': self.charger_metriques_fenetre(source, date, window),
    #         'logs'     : self.charger_logs(source, date, window),
    #         'traces'   : self.charger_traces(source, date, window),
    #     }

    def charger_fenetre_complete(self, source: str, date: str, window: str) -> Dict[str, pd.DataFrame]:
        """
        Charge les 3 modalités pour une fenêtre donnée.

        Args:
            source : 'normal' ou 'anomalies'
            date   : ex '2023-01-29'
            window : ex '08_43'

        Returns:
            dict avec clés 'metriques', 'logs', 'traces' — chacune contenant un DataFrame

        Raises:
            DataError : si les paramètres sont invalides ou si la fenêtre n'existe
                        pas dans le dataset (logs ET traces introuvables)
        """
        logger.info(f"Chargement fenêtre complète : {source} / {date} / {window}")

        metriques = self.charger_metriques_fenetre(source, date, window)
        logs = self.charger_logs(source, date, window)
        traces = self.charger_traces(source, date, window)

        # Validation de l'existence de la fenêtre dans le dataset :
        # si logs ET traces sont vides, c'est que la fenêtre n'existe pas dans Nezha
        # (les métriques couvrent toute la journée, elles ne suffisent pas à valider
        # qu'une fenêtre spécifique est disponible dans le dataset)
        if logs.empty and traces.empty:
            raise DataError(
                f"Fenêtre {date}/{window} indisponible dans le dataset "
                f"(logs et traces introuvables). Cette fenêtre n'existe pas dans "
                f"Nezha pour ce système. Consultez le fichier fault_list.json "
                f"pour la liste des fenêtres disponibles."
            )

        return {
            "metriques": metriques,
            "logs": logs,
            "traces": traces,
        }

    @staticmethod
    def extraire_template(log_str: Any) -> str:
        """
        Extrait un template depuis un message de log.

        Remplace les identifiants variables (UUID, HEX, NUM) par des tokens
        pour permettre le regroupement des logs similaires.

        Args:
            log_str : chaîne de log (ou n'importe quel type convertible en str)

        Returns:
            template textuel du log
        """
        log_str = str(log_str)

        # Extraire le champ 'log' du JSON si présent
        match = re.search(r'"log"\s*:\s*"([^"]+)"', log_str)
        if match:
            log_str = match.group(1)

        # Remplacer UUID, hex, nombres
        log_str = re.sub(
            r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
            "<UUID>",
            log_str,
        )
        log_str = re.sub(r"[0-9a-f]{16,}", "<HEX>", log_str)
        log_str = re.sub(r"\b\d+\.?\d*\b", "<NUM>", log_str)

        # Extraire les crochets ou premiers mots
        crochets = re.findall(r"\[([^\]]+)\]", log_str)
        if crochets:
            return " | ".join(crochets[:3])

        return " ".join(log_str.split()[:6])


if __name__ == "__main__":
    # Test rapide
    print("Test — Chargement fenêtre 08_43 de Train Ticket (anomalies)")

    try:
        ingestion = IngestionEngine("data")

        donnees = ingestion.charger_fenetre_complete(source="anomalies", date="2023-01-29", window="08_43")

        print(f"\n  Métriques : {len(donnees['metriques'])} lignes")
        print(f"  Logs      : {len(donnees['logs'])} lignes")
        print(f"  Traces    : {len(donnees['traces'])} lignes")

        # Test des validations
        print("\n  Test des validations :")
        try:
            ingestion.charger_metriques("invalide", "2023-01-29")
        except DataError as e:
            print(f"    ✓ DataError capturée : {e}")

        try:
            ingestion.charger_metriques_fenetre("anomalies", "2023-01-29", "bad_format")
        except DataError as e:
            print(f"    ✓ DataError capturée : {e}")

        try:
            ingestion.charger_logs("anomalies", "bad-date", "08_43")
        except DataError as e:
            print(f"    ✓ DataError capturée : {e}")

    except DataError as e:
        print(f"\n❌ Erreur : {e}")
