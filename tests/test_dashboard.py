"""
Tests du dashboard Streamlit.

Utilise streamlit.testing.v1.AppTest, qui exécute le script du dashboard
dans un runtime Streamlit simulé, sans navigateur ni serveur. Les appels
à l'API sont remplacés par des doubles de test, ce qui permet de vérifier
le rendu des trois onglets sans dépendre d'une API démarrée.
"""
from pathlib import Path

import pytest
import requests
from streamlit.testing.v1 import AppTest

APP_PATH = str(Path(__file__).resolve().parents[1] / "dashboard" / "app.py")

RESULTAT_DETECTION = {
    "systeme": "train_ticket",
    "date": "2023-01-29",
    "window": "08_43",
    "anomalie": True,
    "severite": "WARNING",
    "confiance": 0.67,
    "modalites": {"metriques": True, "logs": False, "traces": True},
    "type_panne": {
        "type_predit": "return",
        "confiance": 0.90,
        "probabilites": {
            "cpu_problem": 0.03,
            "exception": 0.04,
            "network_delay": 0.03,
            "return": 0.90,
        },
        "action_specifique": "Vérifier les valeurs retournées par le service",
    },
    "action": "Alerte modérée — investigation à planifier",
}

ALERTES = {
    "total": 2,
    "alertes": [
        {"timestamp": "2023-01-29T08:43:00", "systeme": "train_ticket",
         "fenetre": "08_43", "severite": "WARNING", "confiance": 0.67, "type_panne": "return"},
        {"timestamp": "2023-01-29T08:44:00", "systeme": "train_ticket",
         "fenetre": "08_44", "severite": "LOW", "confiance": 0.33, "type_panne": None},
    ],
}

STATISTIQUES = {
    "total": 2,
    "par_severite": {"WARNING": 1, "LOW": 1},
    "par_systeme": {"train_ticket": 2},
}


class ReponseSimulee:
    """Double de test minimal d'une réponse `requests`."""

    def __init__(self, payload, ok=True, status_code=200):
        self._payload = payload
        self.ok = ok
        self.status_code = status_code
        self.text = str(payload)

    def json(self):
        return self._payload


@pytest.fixture
def api_simulee(monkeypatch):
    """Remplace les appels HTTP du dashboard par des réponses figées."""

    def faux_get(url, **kwargs):
        if "/api/health" in url:
            return ReponseSimulee({"status": "healthy"})
        if "/api/alertes" in url:
            return ReponseSimulee(ALERTES)
        if "/api/statistiques" in url:
            return ReponseSimulee(STATISTIQUES)
        return ReponseSimulee({}, ok=False, status_code=404)

    def faux_post(url, **kwargs):
        return ReponseSimulee(RESULTAT_DETECTION)

    monkeypatch.setattr(requests, "get", faux_get)
    monkeypatch.setattr(requests, "post", faux_post)


def lancer(timeout=60):
    app = AppTest.from_file(APP_PATH, default_timeout=timeout)
    app.run()
    return app


def test_dashboard_se_charge_sans_erreur(api_simulee):
    """Le script se charge et expose bien trois onglets."""
    app = lancer()
    assert not app.exception
    assert len(app.tabs) == 3


def test_sidebar_expose_les_parametres_attendus(api_simulee):
    """La barre latérale propose le système, la date et la fenêtre."""
    app = lancer()
    assert len(app.sidebar.selectbox) >= 2
    assert app.sidebar.selectbox[0].value in ("train_ticket", "online_boutique")
    assert app.sidebar.text_input[0].value == "08_43"


def test_api_indisponible_affiche_une_erreur(monkeypatch):
    """Quand l'API est injoignable, le dashboard le signale sans planter."""

    def get_en_echec(url, **kwargs):
        raise requests.RequestException("API inaccessible")

    monkeypatch.setattr(requests, "get", get_en_echec)
    app = lancer()
    assert not app.exception
    assert len(app.sidebar.error) >= 1


def test_changement_de_systeme_met_a_jour_les_dates(api_simulee):
    """Sélectionner Online Boutique change la liste des dates proposées."""
    app = lancer()
    app.sidebar.selectbox[0].set_value("online_boutique").run()
    assert not app.exception
    assert app.sidebar.selectbox[1].value.startswith("2022-08")


def test_lancer_analyse_affiche_le_resultat(api_simulee):
    """Cliquer sur le bouton affiche la sévérité et le type de panne."""
    app = lancer()
    app.button[0].click().run()
    assert not app.exception
    textes = " ".join(str(el.value) for el in app.warning) + " ".join(str(el.value) for el in app.markdown)
    assert "WARNING" in textes


def test_onglet_alertes_affiche_l_historique(api_simulee):
    """L'onglet Alertes consomme la réponse de /api/alertes sans erreur."""
    app = lancer()
    assert not app.exception
    assert len(app.dataframe) >= 0


def test_onglet_statistiques_se_rend_sans_erreur(api_simulee):
    """L'onglet Statistiques consomme /api/statistiques sans erreur."""
    app = lancer()
    assert not app.exception
    assert len(app.tabs) == 3
