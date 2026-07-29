"""
API REST pour la plateforme de détection d'anomalies.

Expose le pipeline via HTTP avec les endpoints :
- POST /api/detecter    : analyser une fenêtre
- GET  /api/alertes     : consulter les alertes
- GET  /api/statistiques : statistiques des alertes
- GET  /api/systemes    : systèmes supportés
- GET  /                : documentation
"""
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional, Dict

from pipeline.main import PipelineComplet
from pipeline.alertes import SystemeAlertes



# SCHÉMAS PYDANTIC (validation)


class RequeteDetection(BaseModel):
    """Requête pour analyser une fenêtre."""
    systeme: str = Field(..., description="'train_ticket' ou 'online_boutique'")
    date   : str = Field(..., description="Format YYYY-MM-DD")
    window : str = Field(..., description="Format HH_MM")
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "systeme": "train_ticket",
                    "date"   : "2023-01-29",
                    "window" : "08_43",
                }
            ]
        }
    }


class Modalites(BaseModel):
    metriques: bool
    logs     : bool
    traces   : bool


class ResultatDetection(BaseModel):
    """Résultat d'une détection."""
    systeme  : str
    fenetre  : str
    anomalie : bool
    severite : str
    confiance: float
    modalites: Modalites
    action   : str


class Alerte(BaseModel):
    """Une alerte enregistrée."""
    timestamp: str
    systeme  : str
    fenetre  : str
    severite : str
    confiance: float
    action   : str



# APPLICATION FASTAPI


app = FastAPI(
    title="Plateforme de détection d'anomalies",
    description=(
        "Détection multi-modale d'anomalies dans les systèmes microservices. "
        "Utilise la fusion de 3 modalités : métriques (LOF), logs (TF-IDF) "
        "et traces (Isolation Forest)."
    ),
    version="1.0.0",
)

# Autoriser CORS pour le dashboard
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)



# INITIALISATION DES PIPELINES


# Charger les pipelines au démarrage (une seule fois)
print("Chargement des pipelines...")
pipelines: Dict[str, PipelineComplet] = {
    'train_ticket'   : PipelineComplet(systeme='train_ticket'),
    'online_boutique': PipelineComplet(systeme='online_boutique'),
}
print("✓ Pipelines prêts")



# ENDPOINTS


@app.get("/")
def racine():
    """Page d'accueil avec description des endpoints."""
    return {
        "message": "Plateforme de détection d'anomalies multi-modale",
        "version": "1.0.0",
        "documentation": "/docs",
        "endpoints": {
            "POST /api/detecter"     : "Analyser une fenêtre",
            "GET  /api/alertes"      : "Consulter les alertes",
            "GET  /api/statistiques" : "Statistiques des alertes",
            "GET  /api/systemes"     : "Systèmes supportés",
        }
    }


@app.get("/api/systemes")
def obtenir_systemes():
    """Retourne la liste des systèmes supportés."""
    return {
        "systemes": [
            {
                "id"          : "train_ticket",
                "description" : "Train Ticket - 41 services Java Spring Boot",
                "dates_dispo" : ["2023-01-29", "2023-01-30"],
            },
            {
                "id"          : "online_boutique",
                "description" : "Online Boutique - 10 services Go/Python/Node.js",
                "dates_dispo" : ["2022-08-22", "2022-08-23"],
            },
        ]
    }


@app.post("/api/detecter", response_model=ResultatDetection)
def detecter_anomalie(requete: RequeteDetection):
    """
    Analyse une fenêtre temporelle et détecte les anomalies.
    
    Retourne le résultat de la détection avec :
    - Sévérité (CRITICAL / WARNING / LOW / NORMAL)
    - Confiance (0-1)
    - Détails par modalité
    - Action recommandée
    
    Les alertes CRITICAL / WARNING / LOW sont automatiquement enregistrées.
    """
    if requete.systeme not in pipelines:
        raise HTTPException(
            status_code=400,
            detail=f"Système inconnu : {requete.systeme}. Utilisez 'train_ticket' ou 'online_boutique'."
        )
    
    try:
        pipeline = pipelines[requete.systeme]
        resultat = pipeline.traiter_fenetre(requete.date, requete.window)
        return resultat
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erreur lors du traitement : {str(e)}"
        )


@app.get("/api/alertes")
def obtenir_alertes(
    limite  : int = Query(50, description="Nombre max d'alertes"),
    severite: Optional[str] = Query(None, description="Filtre par sévérité"),
    systeme : Optional[str] = Query(None, description="Filtre par système"),
):
    """
    Retourne les alertes enregistrées avec filtres optionnels.
    
    Paramètres :
    - limite   : nombre max d'alertes (défaut 50)
    - severite : filtrer par 'CRITICAL', 'WARNING', 'LOW' ou 'NORMAL'
    - systeme  : filtrer par 'train_ticket' ou 'online_boutique'
    """
    alertes_engine = SystemeAlertes()
    alertes = alertes_engine.obtenir(
        limite=limite,
        severite=severite,
        systeme=systeme,
    )
    return {
        "total"   : len(alertes),
        "filtres" : {"severite": severite, "systeme": systeme},
        "alertes" : alertes,
    }


@app.get("/api/statistiques")
def obtenir_statistiques():
    """Retourne les statistiques globales des alertes."""
    alertes_engine = SystemeAlertes()
    return alertes_engine.statistiques()


@app.get("/api/health")
def health_check():
    """Endpoint de santé pour monitoring."""
    return {
        "status": "healthy",
        "pipelines_charges": list(pipelines.keys()),
    }