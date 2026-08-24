"""
Tests d'intégration de l'API FastAPI.

Utilise TestClient de Starlette pour appeler les endpoints sans démarrer
un vrai serveur HTTP. Les pipelines sont instanciés au startup via le lifespan.
"""
import pytest
from fastapi.testclient import TestClient

from api.main import app


@pytest.fixture(scope="module")
def client():
    """Client de test FastAPI qui déclenche le lifespan (chargement des pipelines)."""
    with TestClient(app) as c:
        yield c


class TestEndpointsGeneraux:
    """Tests des endpoints d'information générale."""
    
    def test_racine_retourne_description(self, client):
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "version" in data
    
    def test_health_retourne_healthy(self, client):
        response = client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert data["status"] in ("healthy", "degraded")
    
    def test_systemes_liste_deux_systemes(self, client):
        response = client.get("/api/systemes")
        assert response.status_code == 200
        data = response.json()
        assert "systemes" in data
        ids = [s["id"] for s in data["systemes"]]
        assert "train_ticket" in ids
        assert "online_boutique" in ids


class TestEndpointDetecter:
    """Tests de l'endpoint POST /api/detecter."""
    
    def test_fenetre_valide_retourne_200(self, client):
        response = client.post(
            "/api/detecter",
            json={
                "systeme": "train_ticket",
                "date": "2023-01-29",
                "window": "08_43",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["systeme"] == "train_ticket"
        assert data["fenetre"] == "2023-01-29 08_43"
        assert "severite" in data
        assert data["severite"] in ("CRITICAL", "WARNING", "LOW", "NORMAL")
    
    def test_systeme_inconnu_retourne_400(self, client):
        response = client.post(
            "/api/detecter",
            json={
                "systeme": "systeme_inexistant",
                "date": "2023-01-29",
                "window": "08_43",
            },
        )
        assert response.status_code == 400
        assert "Système inconnu" in response.json()["detail"]
    
    def test_format_fenetre_invalide_retourne_400(self, client):
        """La fenêtre '24_89' a un format impossible (HH>23)."""
        response = client.post(
            "/api/detecter",
            json={
                "systeme": "train_ticket",
                "date": "2023-01-29",
                "window": "24_89",
            },
        )
        assert response.status_code == 400
        assert "invalide" in response.json()["detail"].lower()
    
    def test_fenetre_absente_retourne_404(self, client):
        """La fenêtre '11_51' a un format valide mais n'existe pas dans Nezha."""
        response = client.post(
            "/api/detecter",
            json={
                "systeme": "train_ticket",
                "date": "2023-01-29",
                "window": "11_51",
            },
        )
        assert response.status_code == 404
        assert "indisponible" in response.json()["detail"].lower()


class TestEndpointsAlertes:
    """Tests des endpoints de gestion des alertes."""
    
    def test_alertes_liste_avec_limite(self, client):
        response = client.get("/api/alertes?limite=10")
        assert response.status_code == 200
        data = response.json()
        assert "alertes" in data
        assert "total" in data
        assert len(data["alertes"]) <= 10
    
    def test_alertes_filtre_par_severite(self, client):
        response = client.get("/api/alertes?severite=WARNING")
        assert response.status_code == 200
        data = response.json()
        # Toutes les alertes retournées doivent être WARNING (si non vide)
        for alerte in data["alertes"]:
            assert alerte["severite"] == "WARNING"
    
    def test_statistiques_retourne_structure_valide(self, client):
        response = client.get("/api/statistiques")
        assert response.status_code == 200
        data = response.json()
        assert "total" in data
        assert "par_severite" in data
        assert "par_systeme" in data