"""
Tests des chemins d'erreur de l'API.

Complète test_errors.py en couvrant les branches d'exception qui ne peuvent
pas être atteintes avec des données réelles : erreur de modèle, exception
inattendue et erreur de données lors de la consultation des alertes.
Le pipeline est remplacé par un double de test au moyen de monkeypatch.
"""
import pytest
from fastapi.testclient import TestClient

from api.main import app, pipelines
from pipeline.exceptions import DataError, ModelError

REQUETE_VALIDE = {"date": "2023-01-29", "systeme": "train_ticket", "window": "08_43"}


@pytest.fixture(scope="module")
def client():
    """Client de test déclenchant le lifespan (chargement des pipelines)."""
    with TestClient(app) as c:
        yield c


class TestErreursInternes:
    """Vérifie la traduction des exceptions du pipeline en codes HTTP."""

    def test_erreur_de_modele_retourne_500(self, client, monkeypatch):
        """Un ModelError doit produire un 500 et non remonter brut."""

        def leve_model_error(*args, **kwargs):
            raise ModelError("modèle introuvable ou incompatible")

        monkeypatch.setattr(pipelines["train_ticket"], "traiter_fenetre", leve_model_error)

        reponse = client.post("/api/detecter", json=REQUETE_VALIDE)

        assert reponse.status_code == 500
        assert "Erreur pipeline" in reponse.json()["detail"]

    def test_exception_inattendue_retourne_500(self, client, monkeypatch):
        """Une exception non prévue est capturée par le gestionnaire générique."""

        def leve_runtime_error(*args, **kwargs):
            raise RuntimeError("défaillance imprévue")

        monkeypatch.setattr(pipelines["train_ticket"], "traiter_fenetre", leve_runtime_error)

        reponse = client.post("/api/detecter", json=REQUETE_VALIDE)

        assert reponse.status_code == 500
        assert "Erreur inattendue" in reponse.json()["detail"]

    def test_erreur_de_donnees_sur_alertes_retourne_400(self, client, monkeypatch):
        """Un DataError lors de la lecture des alertes produit un 400."""
        import api.main as module_api

        cible = module_api.pipelines["train_ticket"].alertes

        def leve_data_error(*args, **kwargs):
            raise DataError("paramètre de filtrage invalide")

        monkeypatch.setattr(cible, "obtenir", leve_data_error)

        reponse = client.get("/api/alertes", params={"limite": 10})

        assert reponse.status_code == 400
