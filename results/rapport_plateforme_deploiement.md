# Rapport — Plateforme de déploiement
## API REST, Dashboard, Docker, Tests et CI/CD

---

## 1. Introduction

Après avoir construit le pipeline de détection multi-modale (F1 = 100%) et ajouté la classification supervisée du type de panne (F1 = 63%), il fallait rendre le tout utilisable en vrai. Un script Python qu'on lance à la main dans un terminal, c'est bien pour explorer, mais ça ne suffit pas quand on veut qu'un opérateur SRE puisse s'en servir au quotidien ou qu'on puisse intégrer la détection dans un système existant.

C'est là que la partie "génie logiciel" du projet a pris tout son sens. Il a fallu construire autour du pipeline une vraie plateforme : une API pour accéder aux fonctionnalités programmatiquement, un dashboard pour visualiser les résultats, une conteneurisation pour pouvoir déployer facilement, des tests automatisés pour garantir que rien ne casse quand on modifie quelque chose, et un pipeline CI/CD pour tout ça fonctionne de manière continue.

Ce rapport documente cette phase de construction, avec les choix qui ont été faits, les difficultés rencontrées, et les évolutions du code au fil du projet.

---

## 2. Vue d'ensemble de la plateforme

### 2.1 Ce qui a été livré

Concrètement, la plateforme finale comprend :

- Un **pipeline modulaire** en Python (5 modules qui font chacun une chose précise)
- Une **API REST** avec FastAPI (7 endpoints)
- Un **dashboard interactif** avec Streamlit (3 onglets)
- Une **conteneurisation** avec Docker et docker-compose (2 services)
- **27 tests automatisés** (23 unitaires + 4 d'intégration)
- Un **pipeline CI/CD** sur GitHub Actions (5 jobs)
- La **publication automatique** de l'image Docker sur GitHub Container Registry

En une seule commande (`docker-compose up`), un utilisateur peut lancer toute la plateforme sur sa machine.

### 2.2 Architecture générale

L┌─────────────────────────────────────────────────────────────────────┐
│                          COUCHE PRÉSENTATION                        │
│                                                                     │
│                      Utilisateur (SRE / DevOps)                     │
│                              │                                      │
│                              ▼                                      │
│                    ┌──────────────────┐                             │
│                    │    DASHBOARD     │                             │
│                    │   (Streamlit)    │                             │
│                    │   Port 8501      │                             │
│                    └────────┬─────────┘                             │
└─────────────────────────────┼───────────────────────────────────────┘
                              │
                              │  Requêtes HTTP / JSON
                              │  (POST /api/detecter)
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                          COUCHE INTERFACE                           │
│                                                                     │
│                    ┌──────────────────┐                             │
│                    │      API REST    │                             │
│                    │    (FastAPI)     │                             │
│                    │   Port 8000      │                             │
│                    │                  │                             │
│                    │  Endpoints :     │                             │
│                    │  • /api/detecter │                             │
│                    │  • /api/alertes  │                             │
│                    │  • /api/health   │                             │
│                    └────────┬─────────┘                             │
└─────────────────────────────┼───────────────────────────────────────┘
                              │
                              │  Appels Python
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                          COUCHE MÉTIER                              │
│                                                                     │
│              ┌───────────────────────────────┐                      │
│              │       PIPELINE COMPLET        │                      │
│              │      (pipeline/main.py)       │                      │
│              │        (Pattern Facade)       │                      │
│              └───┬───────┬───────┬───────┬───┘                      │
│                  │       │       │       │                          │
│                  ▼       ▼       ▼       ▼                          │
│              ┌─────┐ ┌─────┐ ┌──────┐ ┌────────┐                    │
│              │ Ing │ │ Dét │ │Class │ │Alertes │                    │
│              │ ges │ │ ect │ │if.   │ │        │                    │
│              │ tion│ │ ion │ │Type  │ │        │                    │
│              └──┬──┘ └──┬──┘ └───┬──┘ └───┬────┘                    │
└─────────────────┼───────┼────────┼────────┼─────────────────────────┘
                  │       │        │        │
                  ▼       ▼        ▼        ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        COUCHE DONNÉES                               │
│                                                                     │
│    ┌─────────────┐   ┌──────────────┐   ┌───────────────┐           │
│    │  DONNÉES    │   │  MODÈLES ML  │   │   ALERTES     │           │
│    │  (Nezha)    │   │   (.pkl)     │   │  (JSON)       │           │
│    │             │   │              │   │               │           │
│    │  data/      │   │  models/     │   │  alertes.json │           │
│    │  ├anomalies │   │  ├lof_*.pkl  │   │               │           │
│    │  └normal    │   │  ├tfidf_*.pkl│   │               │           │
│    │             │   │  ├if_*.pkl   │   │               │           │
│    │             │   │  └classifier │   │               │           │
│    │             │   │    _type.pkl │   │               │           │
│    └─────────────┘   └──────────────┘   └───────────────┘           │
└─────────────────────────────────────────────────────────────────────┘
```

L'idée était de bien séparer les préoccupations : le dashboard ne fait que de l'affichage, l'API expose la logique métier via HTTP, et le pipeline gère toute l'analyse. Comme ça, on peut modifier une partie sans toucher aux autres — par exemple, si demain on veut remplacer le dashboard Streamlit par une interface React, on n'a rien à changer dans le pipeline ni dans l'API.

Explication de ce nouveau diagramme

Il montre 4 couches empilées :

Couche 1 — Présentation (en haut)

Ce que voit l'utilisateur : le dashboard Streamlit sur le port 8501.

Couche 2 — Interface

L'API FastAPI sur le port 8000, avec ses endpoints principaux exposés.

Couche 3 — Métier

Le pipeline complet qui orchestre 4 modules :

Ingestion : charge les données
Détection : applique les 3 algorithmes (LOF, TF-IDF, IF)
Classificateur Type : Random Forest pour le type de panne
Alertes : gère la persistance
Couche 4 — Données (en bas)

Les 3 sources persistantes :

Données Nezha : les CSV du dataset (métriques, logs, traces)
Modèles ML : les fichiers .pkl pré-entraînés
Alertes : le fichier JSON qui accumule les alertes
---

## 3. Le pipeline Python

### 3.1 Structure modulaire

Le pipeline est organisé en 5 modules dans le dossier `pipeline/` :

| Module | Rôle |
|---|---|
| `ingestion.py` | Charge les données Nezha (métriques, logs, traces) |
| `detection.py` | Applique les 3 algorithmes de détection (LOF, TF-IDF, IF) |
| `classification_type.py` | Prédit le type de panne avec Random Forest |
| `alertes.py` | Gère la persistance des alertes dans un fichier JSON |
| `main.py` | Orchestre tout (Facade sur les autres modules) |

Cette séparation vient naturellement quand on essaie de transformer des cellules de notebook en code propre : chaque grande étape devient un module, chaque grande responsabilité devient une classe.

### 3.2 Le pattern Facade avec injection de dépendances

La classe `PipelineComplet` (dans `pipeline/main.py`) applique un pattern Facade : elle expose une interface simple (`traiter_fenetre`, `traiter_batch`) qui cache toute la complexité de l'orchestration.

Voici à quoi ressemble son initialisation :

```python
class PipelineComplet:
    def __init__(
        self,
        systeme='train_ticket',
        config_path='config.yaml',
        ingestion=None,
        detecteur=None,
        alertes=None,
        classificateur=None,
    ):
        self.config = self._charger_config(config_path)
        
        # Injection de dépendances (avec valeurs par défaut)
        self.ingestion = ingestion or IngestionEngine(self.config['data']['base_path'])
        self.detecteur = detecteur or DetecteurAnomalies(systeme=systeme)
        self.alertes = alertes or SystemeAlertes()
        self.classificateur = classificateur or ClassificateurTypePanne()
```

L'astuce ici, c'est que les composants peuvent être **injectés** au constructeur. Pourquoi c'est important ? Parce que ça permet :

- **De tester en isolation** : dans un test, on peut passer un faux `IngestionEngine` qui retourne des données de test, sans avoir besoin des vrais fichiers Nezha.
- **D'échanger les implémentations** : si demain on veut ajouter un `DetecteurAnomaliesV2` avec un algorithme différent, on peut l'injecter sans modifier le pipeline.
- **De garder la simplicité** : si on ne passe rien, ça marche avec les valeurs par défaut, comme avant.

Au début du projet, cette injection n'existait pas — j'instanciais directement les composants dans le constructeur. Le refactoring pour ajouter cette injection s'est fait vers la fin, quand j'ai réalisé que c'était une pratique standard en génie logiciel.

### 3.3 Hiérarchie d'exceptions personnalisées

Une des choses qui m'a fait évoluer le code, c'était de me rendre compte que les erreurs génériques (`Exception`, `ValueError`) ne suffisaient pas. Quand quelque chose plante, on veut savoir **pourquoi** et **à quel niveau**.

J'ai donc créé une petite hiérarchie d'exceptions dans `pipeline/exceptions.py` :

```python
class PipelineError(Exception):
    """Exception de base du pipeline."""
    pass

class ConfigurationError(PipelineError):
    """Erreur liée à la configuration (config.yaml)."""
    pass

class DataError(PipelineError):
    """Erreur liée aux données (fichier, format, validation)."""
    pass

class ModelError(PipelineError):
    """Erreur liée aux modèles ML (chargement, prédiction)."""
    pass
```

Comme ça, quand l'API reçoit une exception, elle sait quoi faire :
- `DataError` → HTTP 404 (données introuvables)
- `ModelError` → HTTP 500 (problème serveur)
- `ConfigurationError` → HTTP 500 (mauvaise config)

C'est plus propre que de tout retourner en 500.

### 3.4 Logging systématique

Autre chose qui m'a semblé évidente en cours de route : sans logs, on est aveugle. Impossible de savoir ce que fait le pipeline en production.

J'ai créé un petit module `pipeline/logger.py` qui centralise la configuration :

```python
from pipeline.logger import setup_logging
logger = setup_logging(__name__)

logger.info(f"Pipeline initialisé pour {systeme}")
logger.warning(f"Fichier introuvable : {chemin}")
logger.error(f"Erreur de prédiction : {e}")
```

Résultat : quand on lance le pipeline, on voit tout ce qui se passe :

```
2026-08-13 - pipeline.main - INFO - Pipeline initialisé pour train_ticket
2026-08-13 - pipeline.ingestion - INFO - Métriques chargées : 42274 lignes
2026-08-13 - pipeline.detection - INFO - Détections : 2/3 modalités
2026-08-13 - pipeline.classification_type - INFO - Type prédit : return (confiance 90%)
2026-08-13 - pipeline.alertes - INFO - Alerte WARNING enregistrée
```

C'est particulièrement utile dans Docker, où on peut suivre les logs en temps réel avec `docker-compose logs -f api`.

---

## 4. L'API REST

### 4.1 Pourquoi FastAPI

J'ai choisi FastAPI pour plusieurs raisons :

- **La documentation Swagger se génère automatiquement**. C'est un énorme avantage pour un projet académique : je n'ai pas eu à écrire de documentation manuelle pour l'API, elle apparaît toute seule à l'URL `/docs`.
- **La validation Pydantic est native**. Je définis mes schémas d'entrée/sortie une fois, et FastAPI valide tout automatiquement.
- **C'est moderne**. Les concepts (async, type hints, lifespan) reflètent les bonnes pratiques Python actuelles.
- **C'est rapide à développer**. Beaucoup moins de code répétitif qu'avec Flask.

### 4.2 Les endpoints

L'API expose 7 endpoints organisés en catégories (grâce aux tags OpenAPI) :

**Général** :
- `GET /` — Page d'accueil avec la liste des endpoints
- `GET /api/health` — Vérification de santé (utilisé par Docker)

**Systèmes** :
- `GET /api/systemes` — Liste des systèmes supportés

**Détection** :
- `POST /api/detecter` — Analyse d'une fenêtre temporelle

**Alertes** :
- `GET /api/alertes` — Consultation avec filtres (limite, sévérité, système)
- `GET /api/statistiques` — Agrégats globaux

Et la documentation interactive :
- `GET /docs` — Swagger UI (généré automatiquement)

### 4.3 Chargement des pipelines au démarrage

Un des trucs importants que j'ai appris avec FastAPI, c'est le **lifespan**. Au lieu de charger les modèles à chaque requête (ce qui serait catastrophique — 10-15 secondes par requête), on les charge une seule fois au démarrage :

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Démarrage de l'API — chargement des pipelines")
    pipelines['train_ticket'] = PipelineComplet(systeme='train_ticket')
    pipelines['online_boutique'] = PipelineComplet(systeme='online_boutique')
    logger.info(f"Pipelines chargés : {list(pipelines.keys())}")
    yield
    logger.info("Arrêt de l'API")
```

Résultat : le démarrage prend environ 10 secondes (chargement des 6 modèles pré-entraînés), puis chaque requête `/api/detecter` prend seulement 200-800 ms. Sans cette optimisation, c'était injouable.

### 4.4 Middleware de logging

J'ai ajouté un middleware qui trace automatiquement toutes les requêtes HTTP :

```python
@app.middleware("http")
async def log_requests(request: Request, call_next):
    debut = time.time()
    reponse = await call_next(request)
    duree_ms = (time.time() - debut) * 1000
    logger.info(f"{request.method} {request.url.path} → {reponse.status_code} ({duree_ms:.0f}ms)")
    return reponse
```

Ce qui donne en pratique :

```
GET /api/health → 200 (4ms)
POST /api/detecter → 200 (844ms)
```

Très utile pour comprendre les temps de réponse et déboguer.

### 4.5 Gestion des erreurs HTTP

Au début, mon API retournait tout en HTTP 500 quand quelque chose plantait. C'était laid et pas informatif. Avec les exceptions personnalisées du pipeline, j'ai pu faire une gestion propre :

```python
try:
    return pipeline.traiter_fenetre(requete.date, requete.window)
except DataError as e:
    raise HTTPException(status_code=404, detail=f"Données introuvables : {e}")
except (ModelError, PipelineError) as e:
    logger.error(f"Erreur pipeline : {e}")
    raise HTTPException(status_code=500, detail=f"Erreur pipeline : {e}")
```

Maintenant :
- 400 si le système est inconnu ou les paramètres sont invalides
- 404 si les données ne sont pas trouvées
- 422 si la validation Pydantic échoue (format de date incorrect, etc.)
- 500 pour les erreurs internes

C'est beaucoup plus RESTful et professionnel.

### 4.6 Un exemple concret

Un appel typique à l'API :

```bash
curl -X POST http://localhost:8000/api/detecter \
  -H "Content-Type: application/json" \
  -d '{
    "systeme": "train_ticket",
    "date": "2023-01-29",
    "window": "08_43"
  }'
```

Retourne :

```json
{
  "systeme": "train_ticket",
  "fenetre": "2023-01-29 08_43",
  "anomalie": true,
  "severite": "WARNING",
  "confiance": 0.67,
  "modalites": {
    "metriques": true,
    "logs": false,
    "traces": true
  },
  "type_panne": {
    "type_predit": "return",
    "confiance": 0.90,
    "probabilites": {
      "cpu_problem": 0.00,
      "exception": 0.10,
      "network_delay": 0.00,
      "return": 0.90
    },
    "action_specifique": "Vérifier valeurs retournées par le service"
  },
  "action": "Alerte modérée — investigation à planifier"
}
```

L'opérateur SRE a tout ce qu'il faut : niveau de sévérité, quelles modalités ont détecté, quel type de panne, et quoi faire.

---

## 5. Le dashboard Streamlit

### 5.1 Pourquoi Streamlit

Streamlit a été un choix pragmatique. J'aurais pu faire un dashboard en React ou en Vue, mais ça aurait pris des semaines. Avec Streamlit, on peut avoir un dashboard fonctionnel en quelques heures :

- Pas besoin de connaître le frontend
- Intégration native avec pandas et matplotlib
- Rechargement automatique en développement
- Composants prêts à l'emploi (tableaux, graphiques, métriques)

L'inconvénient c'est que ce n'est pas fait pour la production à grande échelle, mais pour un projet académique et une démonstration, c'est largement suffisant.

### 5.2 Structure en 3 onglets

Le dashboard s'organise en 3 onglets :

**Onglet 1 — Détection** :
- Sélection du système (Train Ticket / Online Boutique)
- Saisie de la date et de la fenêtre
- Bouton "Lancer l'analyse"
- Affichage détaillé du résultat avec émojis pour la sévérité
- Section "Type de panne prédit" avec graphique de probabilités

**Onglet 2 — Alertes** :
- Historique complet avec filtres (sévérité, système)
- Compteurs par sévérité
- Tableau interactif

**Onglet 3 — Statistiques** :
- Métriques globales (total, répartition)
- Distribution par sévérité (graphique Plotly)
- Distribution par système

### 5.3 Communication avec l'API

Le dashboard ne fait aucun calcul — il appelle simplement l'API et affiche les résultats. La séparation est totale :

```python
API_URL = os.getenv("API_URL", "http://localhost:8000")

response = requests.post(f"{API_URL}/api/detecter", json={
    "systeme": systeme,
    "date": date,
    "window": window,
})
resultat = response.json()
```

Le fait que l'URL de l'API soit une variable d'environnement permet au dashboard de fonctionner :
- En local : il tape sur `http://localhost:8000`
- Dans Docker : il tape sur `http://api:8000` (nom du container)

---

## 6. La conteneurisation Docker

### 6.1 Pourquoi Docker

Sans Docker, installer le projet nécessiterait :
- Python 3.12
- 40+ dépendances avec des versions précises
- La configuration des chemins
- Le chargement des modèles

Avec Docker, c'est une seule commande : `docker-compose up`. Point.

C'est un vrai game changer pour la reproductibilité et pour permettre à n'importe qui de lancer le projet.

### 6.2 Le Dockerfile

L'image est basée sur `python:3.12-slim` (léger, environ 150 MB de base) :

```dockerfile
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY pipeline/ ./pipeline/
COPY api/ ./api/
COPY dashboard/ ./dashboard/
COPY models/ ./models/
COPY config.yaml .

EXPOSE 8000 8501
```

L'ordre est important : on copie `requirements.txt` en premier pour bénéficier du cache Docker (si le code change mais pas les dépendances, on ne refait pas l'installation).

### 6.3 docker-compose pour deux services

Un seul Dockerfile mais deux services qui utilisent la même image :

```yaml
services:
  api:
    build: .
    container_name: anomalie-api
    ports:
      - "8000:8000"
    volumes:
      - ./data:/app/data:ro
      - ./config.yaml:/app/config.yaml:ro
      - alertes-data:/app/alertes
    command: uvicorn api.main:app --host 0.0.0.0 --port 8000
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')"]
      interval: 30s

  dashboard:
    image: anomalie-detection:1.0.0
    container_name: anomalie-dashboard
    ports:
      - "8501:8501"
    environment:
      - API_URL=http://api:8000
    command: streamlit run dashboard/app.py --server.address=0.0.0.0
    depends_on:
      - api
```

Les deux services communiquent via un réseau bridge interne (`anomalie-network`). Le dashboard trouve l'API via le DNS interne de Docker (`api:8000`).

### 6.4 Les bugs Docker que j'ai galéré à résoudre

La mise en place de Docker ne s'est pas faite sans mal. J'ai passé un temps considérable à résoudre 6 bugs différents, ce qui m'a beaucoup appris sur les subtilités de la conteneurisation.

**Bug 1 — Incompatibilité scikit-learn**

Les modèles avaient été sauvegardés avec `scikit-learn 1.8.0`, mais Docker installait `1.9.0` par défaut. Les modèles se chargeaient sans erreur mais donnaient des résultats bizarres. Solution : figer la version dans `requirements.txt` avec `scikit-learn==1.8.0`. Ça m'a appris qu'en ML, la reproductibilité passe par le figage des versions.

**Bug 2 — Liens symboliques**

Mon dossier `data/` contenait des liens symboliques vers un autre chemin sur ma machine. Docker ne peut pas suivre ces liens. Solution : copier les vraies données (2.8 GB) dans le projet et ajouter `data/` au `.gitignore`.

**Bug 3 — Chemin absolu dans config.yaml**

Le config.yaml contenait un chemin `/home/eunice/...` qui n'existait évidemment pas dans le container. Solution : passer à un chemin relatif (`data`) et monter le config.yaml comme volume pour pouvoir le modifier sans reconstruire l'image.

**Bug 4 — Schéma Pydantic incomplet**

J'avais ajouté le champ `type_panne` dans le résultat du pipeline mais oublié de le déclarer dans le schéma `ResultatDetection` de l'API. Résultat : le dashboard ne recevait jamais le type de panne. Solution : ajouter `type_panne: Optional[Dict] = None` au schéma.

**Bug 5 — Dashboard qui ne voit pas les modifs**

En développement, je modifiais `dashboard/app.py` mais je ne voyais pas les changements. Il fallait rebuild l'image à chaque fois. Solution : monter le fichier comme volume : `./dashboard/app.py:/app/dashboard/app.py:ro`.

**Bug 6 — Containers créés mais pas démarrés**

Au début, j'utilisais `docker start` sur les containers, mais ça ne suffisait pas. Il fallait `docker-compose up -d` pour bien démarrer avec toute la configuration.

Ces galères sont formatrices — on comprend mieux comment Docker fonctionne en interne.

---

## 7. Les tests automatisés

### 7.1 Pourquoi pytest

Pytest est le standard Python de facto :
- Syntaxe simple (moins de code répétitif que unittest)
- Fixtures puissantes pour la gestion des données de test
- Excellente intégration avec les pipelines CI/CD
- Rapports clairs quand un test échoue

### 7.2 Deux catégories de tests

**23 tests unitaires** (dans `tests/test_pipeline.py`) qui vérifient les fonctions pures du pipeline. Ils ne dépendent d'aucune donnée externe et s'exécutent en moins d'une seconde :

```python
class TestFusion:               # 8 tests
class TestClassification:       # 4 tests
class TestScoreConfiance:       # 4 tests
class TestActions:              # 4 tests
class TestAlertes:              # 3 tests
```

Exemple d'un test unitaire :

```python
def test_critical(self):
    """3 modalités qui détectent → CRITICAL."""
    detections = {'metriques': True, 'logs': True, 'traces': True}
    assert classifier(detections) == 'CRITICAL'
```

**4 tests d'intégration** (dans `tests/test_integration.py`) qui testent le pipeline complet avec de vraies données. Pour ça, j'ai créé un mini-dataset de 2,7 Mo dans `tests/mini_data/` (une seule fenêtre : celle de la panne `return` du 29 janvier 2023). Ce mini-dataset est commité dans le repo pour que le CI puisse l'utiliser :

```python
def test_detection_panne_return(self, config_test):
    """Vérifie que le pipeline détecte l'anomalie connue."""
    pipeline = PipelineComplet(systeme='train_ticket', config_path=config_test)
    resultat = pipeline.traiter_fenetre('2023-01-29', '08_43')
    
    assert resultat['anomalie'] == True
    assert resultat['severite'] in ['CRITICAL', 'WARNING', 'LOW']
```

### 7.3 Résultats

En local, l'exécution de tous les tests prend environ 4 secondes :

```
27 passed in 4s
```

C'est rapide, ce qui incite à lancer les tests souvent — bonne pratique.

---

## 8. Le pipeline CI/CD

### 8.1 Pourquoi GitHub Actions

- Intégré nativement à GitHub (aucune config externe)
- Gratuit pour l'usage que j'en fais
- Standard industriel largement documenté
- Écosystème d'actions réutilisables

### 8.2 Les 5 jobs du pipeline

Le workflow (`.github/workflows/ci.yml`) exécute 5 jobs à chaque push :

**Job 1 — Lint (~10s)**

Vérification de la qualité du code avec flake8. Détecte les erreurs de syntaxe (E9, F63, F7, F82) qui font échouer le pipeline, et signale les warnings de style sans bloquer.

**Job 2 — Tests unitaires (~1 min)**

Exécute les 23 tests unitaires avec pytest et génère un rapport de couverture. Ne se lance que si le lint passe.

**Job 3 — Tests d'intégration (~1 min)**

Exécute les 4 tests d'intégration avec le mini-dataset commité. Valide le comportement end-to-end.

**Job 4 — Build & Push Docker (~3 min)**

Construit l'image Docker avec Buildx, puis la publie sur GitHub Container Registry. L'image est taguée avec le nom de la branche, le SHA court du commit, et `latest` pour la branche par défaut. Un cache Docker est activé pour accélérer les builds successifs.

**Job 5 — Déploiement simulé (<1s)**

Simule un déploiement (affichage d'informations). Ne s'exécute que sur `main` et `develop`. Dans une vraie situation, ce job pousserait l'image sur un cluster Kubernetes ou un serveur.

### 8.3 Bonnes pratiques appliquées

Sans que ce soit forcément conscient au début, j'ai fini par appliquer plusieurs bonnes pratiques :

- **Fail fast** : le lint tourne en premier pour détecter rapidement les erreurs triviales
- **Séparation des tests** : unitaires (rapides) et intégration (avec données) dans des jobs distincts
- **Dépendances explicites** : le build Docker ne se déclenche que si tous les tests passent
- **Cache** : Docker Buildx utilise le cache GHA pour ne pas tout reconstruire à chaque fois

Résultat : le pipeline complet s'exécute en environ **2 min 30s à 4 min 40s** selon si le cache est chaud.

### 8.4 Le bug qui m'a occupé un moment

Une fois, j'ai eu un pipeline qui échouait avec le message :
```
ERROR: failed to build: invalid tag "ghcr.io/eunicepris/intelligent_observability:-fdc68ae"
```

Le problème venait du fait que ma branche s'appelait `feature/pipeline-complet` (avec un slash), ce qui cassait la génération automatique des tags. Solution : utiliser `type=sha,format=short` au lieu de `type=sha,prefix={{branch}}-`.

Petite leçon : les slashs dans les noms de branches peuvent poser problème avec certains outils, il faut y penser.

---

## 9. Ce qui reste à améliorer

Je documente honnêtement les limites actuelles :

**Sécurité** :
- Pas d'authentification sur l'API (elle est ouverte)
- Pas de rate limiting
- CORS ouvert (`allow_origins=["*"]`)

**Observabilité** :
- Pas de métriques Prometheus
- Pas de traces distribuées
- Les alertes vont juste dans un fichier JSON (pas de base de données)

**Scalabilité** :
- Docker Compose au lieu de Kubernetes
- Un seul instance de chaque service
- Pas de file d'attente pour requêtes lourdes

**MLOps** :
- Pas de MLflow
- Pas de détection de drift
- Pas de réentraînement automatique

Ces manques sont documentés dans la proposition initiale comme des ambitions qui n'ont pas pu être livrées dans le temps imparti. Ils constituent des perspectives d'évolution naturelles pour un développement futur du projet.

---

## 10. Ce que j'ai appris

Cette phase "génie logiciel" du projet m'a beaucoup appris. Voici les principales choses :

**Sur l'architecture** :
- L'importance de séparer les préoccupations (UI ≠ API ≠ logique métier)
- Le pattern Facade pour cacher la complexité
- L'injection de dépendances pour la testabilité

**Sur Docker** :
- La différence entre `Docker Engine` et `Docker Desktop`
- L'importance de figer les versions en ML
- Comment gérer les volumes, les réseaux, les healthchecks
- Pourquoi les liens symboliques posent problème dans le build context

**Sur les APIs** :
- FastAPI et son écosystème (Pydantic, lifespan, middleware)
- L'importance des codes HTTP appropriés
- Comment structurer un projet pour qu'il soit maintenable

**Sur le CI/CD** :
- Comment GitHub Actions fonctionne
- L'importance des jobs séparés (fail fast)
- Comment gérer le cache pour accélérer les builds
- Le versionnement automatique des images Docker

**Sur le refactoring** :
- Il vaut mieux commencer simple et refactorer quand on comprend mieux le problème
- Les tests permettent de refactorer en confiance
- Ajouter du logging systématique change complètement l'expérience de développement

Ce projet m'aura fait toucher à énormément de choses différentes en peu de temps. C'est une charge d'apprentissage importante mais c'est ce genre d'expérience qui fait grandir techniquement.

---

## Annexe A — Structure des fichiers

```
Intelligent_observability/
├── api/
│   └── main.py                    # API FastAPI (255 lignes)
├── dashboard/
│   └── app.py                     # Dashboard Streamlit (~400 lignes)
├── pipeline/
│   ├── __init__.py
│   ├── ingestion.py               # Chargement des données Nezha
│   ├── detection.py               # LOF + TF-IDF + IF + fusion
│   ├── classification_type.py     # Random Forest supervisé
│   ├── alertes.py                 # Persistance JSON
│   ├── main.py                    # Facade (PipelineComplet)
│   ├── exceptions.py              # Hiérarchie d'exceptions
│   └── logger.py                  # Configuration du logging
├── models/
│   ├── lof_tt.pkl / lof_ob.pkl
│   ├── tfidf_tt.pkl / tfidf_ob.pkl
│   ├── if_traces_tt.pkl / if_traces_ob.pkl
│   └── classifier_type_panne.pkl
├── tests/
│   ├── __init__.py
│   ├── test_pipeline.py           # 23 tests unitaires
│   ├── test_integration.py        # 4 tests d'intégration
│   └── mini_data/                 # Mini-dataset pour CI (2,7 Mo)
├── .github/
│   └── workflows/
│       └── ci.yml                 # Pipeline à 5 jobs
├── Dockerfile
├── docker-compose.yml
├── .dockerignore
├── requirements.txt
├── config.yaml
└── README.md
```

## Annexe B — Commandes utiles

**Développement local** :
```bash
# API seule
uvicorn api.main:app --reload

# Dashboard seul
streamlit run dashboard/app.py

# Tests
pytest tests/ -v

# Test end-to-end du pipeline
python -m pipeline.main
```

**Docker** :
```bash
# Lancer tout
docker-compose up -d

# Voir les logs en temps réel
docker-compose logs -f api
docker-compose logs -f dashboard

# Arrêter
docker-compose down

# Reconstruire (utile après modifications importantes)
docker-compose build --no-cache
docker-compose up -d
```

**Git** :
```bash
# Créer une branche feature
git checkout -b feature/nouvelle-fonctionnalite

# Commiter avec message descriptif
git add .
git commit -m "feat: description claire"

# Pusher
git push origin feature/nouvelle-fonctionnalite
```

---

*Rapport de la plateforme de déploiement*
*Composante génie logiciel du projet d'observabilité intelligente*
*Projet de maîtrise en génie logiciel*
