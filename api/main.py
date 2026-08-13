"""
API REST pour la plateforme de détection d'anomalies.

Expose le pipeline via HTTP avec les endpoints :
- POST /api/detecter     : analyser une fenêtre
- GET  /api/alertes      : consulter les alertes
- GET  /api/statistiques : statistiques des alertes
- GET  /api/systemes     : systèmes supportés
- GET  /api/health       : santé du service
- GET  /                 : page d'accueil
"""
import time
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from pipeline.main import PipelineComplet
from pipeline.alertes import SystemeAlertes
from pipeline.exceptions import (
    PipelineError,
    ConfigurationError,
    DataError,
    ModelError,
)
from pipeline.logger import setup_logging


logger = setup_logging(__name__)



# SCHÉMAS PYDANTIC (validation)


class RequeteDetection(BaseModel):
    """Requête pour analyser une fenêtre."""
    systeme: str = Field(..., description="'train_ticket' ou 'online_boutique'")
    date: str = Field(..., description="Format YYYY-MM-DD", pattern=r'^\d{4}-\d{2}-\d{2}$')
    window: str = Field(..., description="Format HH_MM", pattern=r'^\d{2}_\d{2}$')
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "systeme": "train_ticket",
                    "date": "2023-01-29",
                    "window": "08_43",
                }
            ]
        }
    }


class Modalites(BaseModel):
    """Détections par modalité."""
    metriques: bool
    logs: bool
    traces: bool


class ResultatDetection(BaseModel):
    """Résultat complet d'une détection."""
    systeme: str
    fenetre: str
    anomalie: bool
    severite: str
    confiance: float
    modalites: Modalites
    type_panne: Optional[Dict[str, Any]] = None
    action: str


class Alerte(BaseModel):
    """Une alerte enregistrée."""
    timestamp: str
    systeme: str
    fenetre: str
    severite: str
    confiance: float
    action: str



# CYCLE DE VIE DE L'APPLICATION


# Instances des pipelines (chargées au démarrage)
pipelines: Dict[str, PipelineComplet] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Gère le cycle de vie de l'application.
    
    - Au démarrage : charge les pipelines
    - À l'arrêt    : nettoyage éventuel
    """
    logger.info("Démarrage de l'API — chargement des pipelines")
    
    try:
        pipelines['train_ticket'] = PipelineComplet(systeme='train_ticket')
        pipelines['online_boutique'] = PipelineComplet(systeme='online_boutique')
        logger.info(f"Pipelines chargés : {list(pipelines.keys())}")
    except (ConfigurationError, DataError, ModelError) as e:
        logger.error(f"Erreur de chargement des pipelines : {e}")
        raise
    
    yield  # L'application tourne
    
    logger.info("Arrêt de l'API")



# APPLICATION FASTAPI


app = FastAPI(
    title="Plateforme de détection d'anomalies",
    description=(
        "Détection multi-modale d'anomalies dans les systèmes microservices. "
        "Utilise la fusion de 3 modalités : métriques (LOF), logs (TF-IDF) "
        "et traces (Isolation Forest), plus une classification supervisée "
        "du type de panne (Random Forest)."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# CORS pour permettre l'accès depuis le dashboard
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)



# MIDDLEWARE DE LOGGING


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Middleware pour tracer toutes les requêtes HTTP."""
    debut = time.time()
    reponse = await call_next(request)
    duree_ms = (time.time() - debut) * 1000
    
    logger.info(
        f"{request.method} {request.url.path} "
        f"→ {reponse.status_code} ({duree_ms:.0f}ms)"
    )
    return reponse



# ENDPOINTS


@app.get("/", tags=["Général"])
def racine() -> Dict[str, Any]:
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
            "GET  /api/health"       : "Santé de l'API",
        }
    }


@app.get("/api/health", tags=["Général"])
def health_check() -> Dict[str, Any]:
    """
    Endpoint de santé pour le monitoring.
    
    Retourne l'état de l'API et la liste des pipelines chargés.
    Utilisé par le healthcheck Docker.
    """
    return {
        "status": "healthy",
        "pipelines_charges": list(pipelines.keys()),
    }


@app.get("/api/systemes", tags=["Systèmes"])
def obtenir_systemes() -> Dict[str, Any]:
    """Retourne la liste des systèmes supportés avec leurs métadonnées."""
    return {
        "systemes": [
            {
                "id": "train_ticket",
                "description": "Train Ticket - 41 services Java Spring Boot",
                "dates_dispo": ["2023-01-29", "2023-01-30"],
            },
            {
                "id": "online_boutique",
                "description": "Online Boutique - 10 services Go/Python/Node.js",
                "dates_dispo": ["2022-08-22", "2022-08-23"],
            },
        ]
    }


@app.post(
    "/api/detecter",
    response_model=ResultatDetection,
    tags=["Détection"],
    responses={
        400: {"description": "Système inconnu ou paramètres invalides"},
        404: {"description": "Données introuvables pour cette fenêtre"},
        500: {"description": "Erreur interne du serveur"},
    },
)
def detecter_anomalie(requete: RequeteDetection) -> Dict[str, Any]:
    """
    Analyse une fenêtre temporelle et détecte les anomalies.
    
    Retourne le résultat de la détection avec :
    - Sévérité (CRITICAL / WARNING / LOW / NORMAL)
    - Confiance (0-1)
    - Détails par modalité
    - Type de panne prédit (si anomalie)
    - Action recommandée
    
    Les alertes CRITICAL / WARNING / LOW sont automatiquement enregistrées.
    """
    if requete.systeme not in pipelines:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Système inconnu : {requete.systeme}. "
                f"Systèmes disponibles : {list(pipelines.keys())}"
            ),
        )
    
    pipeline = pipelines[requete.systeme]
    
    try:
        return pipeline.traiter_fenetre(requete.date, requete.window)
    
    except DataError as e:
        # Données introuvables ou invalides
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Données introuvables : {e}",
        )
    except (ModelError, PipelineError) as e:
        # Erreur interne du pipeline
        logger.error(f"Erreur pipeline : {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur pipeline : {e}",
        )
    except Exception as e:
        # Erreur inattendue
        logger.exception(f"Erreur inattendue : {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur inattendue : {e}",
        )


@app.get("/api/alertes", tags=["Alertes"])
def obtenir_alertes(
    limite: int = Query(50, ge=1, le=1000, description="Nombre max d'alertes"),
    severite: Optional[str] = Query(None, description="Filtre par sévérité"),
    systeme: Optional[str] = Query(None, description="Filtre par système"),
) -> Dict[str, Any]:
    """
    Retourne les alertes enregistrées avec filtres optionnels.
    
    Paramètres :
    - limite   : nombre max d'alertes (1-1000, défaut 50)
    - severite : filtrer par 'CRITICAL', 'WARNING', 'LOW' ou 'NORMAL'
    - systeme  : filtrer par 'train_ticket' ou 'online_boutique'
    """
    alertes_engine = SystemeAlertes()
    
    try:
        alertes = alertes_engine.obtenir(
            limite=limite,
            severite=severite,
            systeme=systeme,
        )
    except DataError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    
    return {
        "total": len(alertes),
        "filtres": {"severite": severite, "systeme": systeme},
        "alertes": alertes,
    }


@app.get("/api/statistiques", tags=["Alertes"])
def obtenir_statistiques() -> Dict[str, Any]:
    """Retourne les statistiques globales des alertes enregistrées."""
    alertes_engine = SystemeAlertes()
    return alertes_engine.statistiques()