# Rapport — Plateforme de déploiement
## API REST, Dashboard interactif, Docker et CI/CD

---

## 1. Vue d'ensemble

### 1.1 Contexte

Après avoir construit le pipeline de détection d'anomalies (F1 = 100%) et ajouté la classification supervisée du type de panne (F1 = 63%), il fallait rendre le système **utilisable par des opérateurs**. Un script Python en ligne de commande ne suffit pas — il faut une interface, une API pour l'intégration, un déploiement portable et un système de tests automatisés.

Ce rapport documente la construction de la plateforme complète de déploiement : API REST, dashboard interactif, conteneurisation Docker, tests unitaires et pipeline CI/CD.

### 1.2 Objectifs

- Exposer le pipeline via une API REST documentée
- Créer un dashboard visuel pour les opérateurs
- Conteneuriser l'application pour un déploiement portable
- Automatiser les tests à chaque changement
- Préparer un déploiement continu

### 1.3 Résultat principal

Une plateforme complète, opérationnelle et déployable :

| Composante | Technologie | Statut |
|------------|-------------|--------|
| API REST | FastAPI + Uvicorn | ✓ Fonctionnelle |
| Dashboard | Streamlit + Plotly | ✓ Fonctionnel |
| Conteneurisation | Docker + docker-compose | ✓ Opérationnel |
| Tests | pytest (23 tests) | ✓ 100% passent |
| CI | GitHub Actions | ✓ Configuré |

**En une seule commande** (`docker-compose up`), un utilisateur peut lancer toute la plateforme.

---

## 2. Architecture globale

### 2.1 Vue d'ensemble

```
┌─────────────┐         ┌──────────────┐         ┌──────────────┐
│             │         │              │         │              │
│  UTILISATEUR│───HTTP─▶│  DASHBOARD   │───HTTP─▶│     API      │
│             │         │  (Streamlit) │         │   (FastAPI)  │
│  Navigateur │◀────────│              │◀────────│              │
│             │         │              │         │              │
└─────────────┘         └──────────────┘         └──────┬───────┘
                                                        │
                                                        │
                                                        ▼
                                                ┌──────────────┐
                                                │              │
                                                │   PIPELINE   │
                                                │  (Python)    │
                                                │              │
                                                └──────┬───────┘
                                                        │
                                                ┌───────┴───────┐
                                                │               │
                                                ▼               ▼
                                        ┌──────────┐  ┌──────────┐
                                        │  MODÈLES │  │ DONNÉES  │
                                        │   .pkl   │  │  Nezha   │
                                        └──────────┘  └──────────┘
```

### 2.2 Séparation des responsabilités

- **Dashboard** : interface utilisateur uniquement, ne fait pas de calcul
- **API** : logique métier exposée via HTTP
- **Pipeline** : orchestration des modules de détection et classification
- **Modèles** : artefacts pré-entraînés chargés une seule fois

### 2.3 Communication

Toutes les communications utilisent HTTP/JSON :
- Dashboard → API : appels REST
- API → Pipeline : appels Python directs
- Pipeline → Modèles : lecture pickle

---

## 3. API REST — FastAPI

### 3.1 Choix de FastAPI

**Justification** :
- Documentation Swagger automatique (essentielle pour un projet académique)
- Validation Pydantic native (schémas typés)
- Performance élevée (basé sur Starlette/Uvicorn)
- Développement rapide (moins de boilerplate que Flask)
- Support async natif

### 3.2 Endpoints exposés

| Méthode | Endpoint | Description |
|---------|----------|-------------|
| GET | `/` | Page d'accueil avec liste des endpoints |
| GET | `/docs` | Documentation Swagger interactive |
| GET | `/api/health` | Vérification de santé (pour monitoring) |
| GET | `/api/systemes` | Liste des systèmes supportés |
| POST | `/api/detecter` | Analyse d'une fenêtre |
| GET | `/api/alertes` | Historique des alertes (avec filtres) |
| GET | `/api/statistiques` | Statistiques globales |

### 3.3 Schémas de données

Validation stricte via Pydantic v2 :

**Requête de détection** :
```python
class RequeteDetection(BaseModel):
    systeme: str = Field(..., description="'train_ticket' ou 'online_boutique'")
    date   : str = Field(..., description="Format YYYY-MM-DD")
    window : str = Field(..., description="Format HH_MM")
```

**Réponse de détection** :
```python
class ResultatDetection(BaseModel):
    systeme   : str
    fenetre   : str
    anomalie  : bool
    severite  : str
    confiance : float
    modalites : Modalites
    type_panne: Optional[Dict] = None
    action    : str
```

### 3.4 Chargement des pipelines au démarrage

Optimisation critique : les pipelines des deux systèmes sont **chargés une seule fois** au démarrage de l'API, pas à chaque requête.

```python
pipelines: Dict[str, PipelineComplet] = {
    'train_ticket'   : PipelineComplet(systeme='train_ticket'),
    'online_boutique': PipelineComplet(systeme='online_boutique'),
}
```

**Impact** :
- Temps de démarrage : ~10 secondes (chargement des modèles)
- Temps de réponse par requête : ~200 ms (détection + classification)
- Sans cette optimisation : chaque requête aurait pris 5-10 secondes

### 3.5 CORS et sécurité

Configuration CORS ouverte pour permettre au dashboard d'appeler l'API :

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**Note** : cette configuration est acceptable pour un environnement académique. En production, les origines seraient restreintes.

### 3.6 Exemple d'utilisation

```bash
curl -X POST http://localhost:8000/api/detecter \
  -H "Content-Type: application/json" \
  -d '{
    "systeme": "train_ticket",
    "date": "2023-01-29",
    "window": "08_43"
  }'
```

**Réponse** :
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

---

## 4. Dashboard — Streamlit

### 4.1 Choix de Streamlit

**Justification** :
- Développement extrêmement rapide (moins de code que React/Vue)
- Intégration native avec pandas et matplotlib
- Rechargement automatique en développement
- Composants prêts à l'emploi (tables, graphiques, métriques)
- Adapté aux data scientists

### 4.2 Structure en 3 onglets

**Onglet 1 — Détection** :
- Sélection du système et de la fenêtre
- Bouton "Lancer l'analyse"
- Affichage détaillé du résultat
- Section "Type de panne prédit" avec graphique de probabilités

**Onglet 2 — Alertes** :
- Historique complet avec filtres
- Compteurs par sévérité
- Tableau interactif

**Onglet 3 — Statistiques** :
- Métriques globales
- Distribution par sévérité (graphique)
- Distribution par système

### 4.3 Composants visuels

**Métriques mises en avant** :
```python
col1, col2, col3 = st.columns(3)
with col1:
    st.error(f"🚨 {severite}")
with col2:
    st.metric("Confiance", f"{conf_pct:.0f}%")
```

**Graphiques Plotly** :
```python
fig = px.bar(df_mod, x="Modalité", y="Détecte",
             color="Détecte",
             color_continuous_scale=["#4CAF50", "#F44336"])
```

**Badge de santé de l'API** dans la sidebar :
```python
try:
    r_health = requests.get(f"{API_URL}/api/health", timeout=2)
    if r_health.ok:
        st.sidebar.success("✓ API opérationnelle")
    else:
        st.sidebar.error("✗ API en erreur")
except requests.RequestException:
    st.sidebar.error("✗ API inaccessible")
```

### 4.4 Configuration adaptable

Le dashboard lit l'URL de l'API depuis les variables d'environnement :

```python
API_URL = os.getenv("API_URL", "http://localhost:8000")
```

**Impact** :
- En local : utilise `http://localhost:8000`
- Dans Docker : utilise `http://api:8000` (nom du container)

Cette abstraction permet le déploiement dans différents contextes sans modification du code.

---

## 5. Conteneurisation — Docker

### 5.1 Motivation

Sans Docker, l'installation du projet nécessite :
- Python 3.12
- 40+ dépendances Python (avec versions spécifiques)
- Configuration des chemins
- Chargement des modèles

Avec Docker : **une seule commande** — `docker-compose up`.

### 5.2 Dockerfile

Image basée sur Python 3.12-slim (léger, environ 150 MB) :

```dockerfile
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Installer les dépendances système minimales
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ \
    && rm -rf /var/lib/apt/lists/*

# Copier requirements.txt d'abord (pour cache Docker)
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copier le code
COPY pipeline/ ./pipeline/
COPY api/ ./api/
COPY dashboard/ ./dashboard/
COPY models/ ./models/
COPY config.yaml .

EXPOSE 8000 8501
```

### 5.3 docker-compose.yml

Orchestration de deux services :

```yaml
services:
  api:
    build: .
    image: anomalie-detection:1.0.0
    container_name: anomalie-api
    ports:
      - "8000:8000"
    volumes:
      - ./data:/app/data:ro
      - ./config.yaml:/app/config.yaml:ro
      - alertes-data:/app/alertes
    command: uvicorn api.main:app --host 0.0.0.0 --port 8000
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; ..."]
      interval: 30s
    restart: unless-stopped
    networks:
      - anomalie-network

  dashboard:
    image: anomalie-detection:1.0.0
    container_name: anomalie-dashboard
    ports:
      - "8501:8501"
    volumes:
      - ./data:/app/data:ro
      - ./config.yaml:/app/config.yaml:ro
      - alertes-data:/app/alertes
    environment:
      - API_URL=http://api:8000
    command: streamlit run dashboard/app.py --server.address=0.0.0.0
    depends_on:
      - api

volumes:
  alertes-data:

networks:
  anomalie-network:
    driver: bridge
```

### 5.4 Défis rencontrés et résolus

**Défi 1 — Version scikit-learn** :
- Les modèles étaient sauvegardés avec sklearn 1.8.0
- Docker installait sklearn 1.9.0
- Les modèles se chargeaient mais produisaient des résultats invalides
- **Solution** : fixer `scikit-learn==1.8.0` dans `requirements.txt`

**Défi 2 — Liens symboliques** :
- Le dossier `data/` contenait des liens symboliques vers un chemin externe
- Docker ne peut pas suivre ces liens
- **Solution** : copier les vraies données dans le projet (2.8 GB)
- **Ajout** : `data/` dans `.gitignore` pour éviter de commit les données

**Défi 3 — Chemin absolu dans config.yaml** :
- Le chemin `/home/eunice/...` n'existait pas dans le container
- **Solution 1** : chemin relatif `data` au lieu du chemin absolu
- **Solution 2** : monter config.yaml comme volume pour hot-reload

**Défi 4 — Schéma Pydantic incomplet** :
- Le champ `type_panne` n'était pas dans le schéma de réponse
- L'API le filtrait avant renvoi
- **Solution** : ajouter `type_panne: Optional[Dict]` au schéma

### 5.5 Volumes et persistance

**Volumes montés** :
- `./data:/app/data:ro` — données Nezha en lecture seule
- `./config.yaml:/app/config.yaml:ro` — configuration en lecture seule
- `alertes-data:/app/alertes` — volume Docker pour les alertes (persistance)

**Volume dashboard** (dev uniquement) :
- `./dashboard/app.py:/app/dashboard/app.py:ro` — hot-reload du code dashboard

### 5.6 Réseau interne

Les deux containers communiquent via un réseau bridge nommé `anomalie-network`. Le dashboard résout `api:8000` grâce au DNS interne de Docker.

### 5.7 Healthcheck

L'API expose un endpoint `/api/health` utilisé par Docker pour vérifier la santé :

```yaml
healthcheck:
  test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')"]
  interval: 30s
  timeout: 10s
  retries: 3
```

En cas de défaillance, Docker peut redémarrer automatiquement le container.

---

## 6. Tests automatisés

### 6.1 Choix de pytest

**Justification** :
- Standard de facto en Python
- Syntaxe simple (pas de boilerplate)
- Fixtures puissantes
- Excellente intégration avec CI

### 6.2 Structure des tests

**Fichier `tests/test_pipeline.py`** — 23 tests organisés en 5 classes :

```python
class TestFusion:               # 8 tests
    """Fusion multi-modale"""
    
class TestClassification:       # 4 tests
    """Classification par sévérité"""
    
class TestScoreConfiance:       # 4 tests
    """Calcul de confiance"""
    
class TestActions:              # 4 tests
    """Actions recommandées"""
    
class TestAlertes:              # 3 tests
    """Système d'alertes"""
```

### 6.3 Exemple de test

```python
def test_critical(self):
    """Test que 3 modalités détectent → CRITICAL."""
    detections = {'metriques': True, 'logs': True, 'traces': True}
    assert classifier(detections) == 'CRITICAL'

def test_or_avec_une_detection(self):
    """Test que OR détecte avec 1 seule modalité."""
    detections = {'metriques': True, 'logs': False, 'traces': False}
    assert fusionner(detections, 'or') == True

def test_enregistrer_alerte(self, tmp_path):
    """Test enregistrement d'une alerte."""
    from pipeline.alertes import SystemeAlertes
    fichier = tmp_path / "test_alertes.json"
    alertes = SystemeAlertes(fichier_alertes=str(fichier))
    
    alertes.enregistrer({
        'systeme'  : 'train_ticket',
        'severite' : 'WARNING',
        # ...
    })
    
    assert len(alertes.obtenir()) == 1
```

### 6.4 Résultats

```
============= 23 passed in 1.23s =============
```

**Toutes les fonctions critiques du pipeline sont testées** :
- 3 stratégies de fusion (or, vote_majoritaire, and)
- 4 niveaux de classification
- 4 niveaux de score de confiance
- 4 actions recommandées
- Création, enregistrement, statistiques d'alertes

### 6.5 Couverture

Les tests couvrent les fonctions **pures** (sans dépendance aux données ou modèles). Les tests d'intégration (avec vraies données Nezha) sont exclus car ils prendraient trop de temps en CI.

---

## 7. CI/CD — GitHub Actions

### 7.1 Motivation

Chaque push doit :
1. Lancer les tests unitaires
2. Vérifier la syntaxe Python
3. Construire l'image Docker
4. (Éventuellement) publier l'image

**Automatisation** = pas d'erreur humaine, feedback immédiat.

### 7.2 Workflow `.github/workflows/ci.yml`

```yaml
name: CI/CD Pipeline

on:
  push:
    branches: [main, develop, 'feature/**']
  pull_request:
    branches: [main, develop]

jobs:
  test:
    name: Tests unitaires
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
          cache: 'pip'
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest pytest-cov
      - name: Run tests
        run: pytest tests/ -v --cov=pipeline
      - name: Check syntax
        run: python -m py_compile pipeline/*.py api/*.py dashboard/*.py

  build:
    name: Build Docker Image
    runs-on: ubuntu-latest
    needs: test
    steps:
      - uses: actions/checkout@v4
      - uses: docker/setup-buildx-action@v3
      - name: Build image
        uses: docker/build-push-action@v5
        with:
          context: .
          push: false
          tags: anomalie-detection:${{ github.sha }}
```

### 7.3 Déclencheurs

Le workflow se lance sur :
- Push sur `main`, `develop`, ou branches `feature/*`
- Pull request vers `main` ou `develop`

### 7.4 Pipeline en 2 étapes

**Étape 1 — Tests** :
- Setup Python 3.12
- Installation des dépendances
- Exécution de pytest
- Vérification de la syntaxe
- **Bloque le pipeline si un test échoue**

**Étape 2 — Build** :
- Setup Docker Buildx
- Construction de l'image
- Cache Docker pour accélérer les builds futurs
- **Ne se lance que si les tests passent** (`needs: test`)

### 7.5 Push d'image (extension future)

Le workflow peut être étendu pour publier automatiquement l'image sur GitHub Container Registry :

```yaml
- name: Login to GHCR
  uses: docker/login-action@v3
  with:
    registry: ghcr.io
    username: ${{ github.actor }}
    password: ${{ secrets.GITHUB_TOKEN }}

- name: Build and Push
  uses: docker/build-push-action@v5
  with:
    context: .
    push: true
    tags: ghcr.io/${{ github.repository }}:latest
```

---

## 8. Reproductibilité et déploiement

### 8.1 Reproduire l'environnement complet

```bash
# 1. Cloner le projet
git clone https://github.com/Eunicepris/Intelligent_observability.git
cd Intelligent_observability

# 2. Placer les données Nezha
cp -r /path/to/nezha/rca_data data/anomalies
cp -r /path/to/nezha/construct_data data/normal

# 3. Lancer la plateforme
docker-compose up -d

# 4. Accéder aux interfaces
# API      : http://localhost:8000/docs
# Dashboard: http://localhost:8501
```

### 8.2 Reproduction des résultats

Tous les résultats sont reproductibles à l'identique grâce à :
- **Random state fixé** dans tous les algorithmes ML
- **Version scikit-learn figée** dans requirements.txt
- **Modèles pré-entraînés** versionnés dans le repo
- **Données Nezha** publiques et documentées

### 8.3 Portabilité

La plateforme fonctionne sur :
- Linux (testé sur Ubuntu 24)
- macOS (via Docker Desktop)
- Windows (via Docker Desktop)
- Cloud (AWS, GCP, Azure) via images Docker

### 8.4 Ressources requises

**Minimum** :
- 4 GB RAM
- 5 GB espace disque (dont ~3 GB de données Nezha)
- Docker 20.10+

**Recommandé** :
- 8 GB RAM
- 10 GB espace disque
- Docker 24.0+

---

## 9. Limitations et perspectives

### 9.1 Limitations actuelles

1. **Pas de authentification** — l'API est ouverte
2. **Pas de rate limiting** — vulnérable au flood
3. **Alertes en JSON** — pas adapté à une production réelle (utiliser PostgreSQL)
4. **CORS ouvert** — acceptable en académique, à restreindre en prod
5. **Pas de logs structurés** — utiliser Loguru en production

### 9.2 Perspectives d'amélioration

**Sécurité** :
- Authentification JWT
- HTTPS via Traefik/Nginx
- Rate limiting avec Redis

**Observabilité** :
- Métriques Prometheus
- Traces distribuées (Jaeger)
- Logs structurés

**Scalabilité** :
- Kubernetes pour orchestration multi-nœuds
- File d'attente Redis/RabbitMQ pour requêtes lourdes
- Cache Redis pour résultats fréquents

**Data pipeline** :
- Ingestion Kafka en temps réel
- Base de données time-series (InfluxDB, TimescaleDB)
- Rétention et archivage automatiques

**MLOps** :
- Suivi des expériences (MLflow)
- Détection de drift
- Ré-entraînement automatique périodique
- A/B testing des modèles

---

## 10. Conclusion

### 10.1 Bilan technique

La plateforme construite constitue une **base solide** pour un système de détection d'anomalies en production. Elle réunit :

- **Interface web utilisable** par des non-développeurs
- **API programmatique** pour intégration dans d'autres outils
- **Conteneurisation** pour déploiement portable
- **Tests automatisés** pour garantir la qualité
- **CI/CD** pour évoluer en toute confiance

### 10.2 Statistiques du travail

| Composante | Métrique |
|------------|----------|
| Endpoints API | 7 |
| Lignes de code API | ~250 |
| Lignes de code Dashboard | ~400 |
| Onglets dashboard | 3 |
| Tests unitaires | 23 |
| Temps d'exécution des tests | 1.23 s |
| Taille de l'image Docker | ~1.5 GB |
| Services orchestrés | 2 |

### 10.3 Contribution

Transformer un pipeline Python (script) en une **plateforme déployable** représente un travail d'ingénierie logicielle significatif :

- **Ingénierie API** : conception REST, validation, documentation
- **UI/UX** : conception d'un dashboard utilisable
- **DevOps** : conteneurisation, orchestration, CI
- **Qualité** : tests automatisés, revue de code
- **Documentation** : rapports, README, docstrings

Ces compétences transverses sont ce qui distingue **la recherche appliquée** d'un simple prototype.

### 10.4 Valeur pédagogique

Pour un projet de maîtrise en **génie logiciel**, cette plateforme démontre la maîtrise de :
- Frameworks modernes (FastAPI, Streamlit)
- Conteneurisation (Docker, docker-compose)
- Tests automatisés (pytest)
- CI/CD (GitHub Actions)
- Bonnes pratiques (typing, validation, séparation des préoccupations)

**Cette dimension "génie logiciel" complète la dimension "machine learning" pour un projet équilibré et professionnel.**

---

## Annexe A — Structure des fichiers

```
Intelligent_observability/
├── api/
│   └── main.py                 API FastAPI (250 lignes)
├── dashboard/
│   └── app.py                  Dashboard Streamlit (400 lignes)
├── pipeline/
│   ├── __init__.py
│   ├── ingestion.py
│   ├── detection.py
│   ├── alertes.py
│   ├── classification_type.py  Nouveau module ML
│   └── main.py                 Pipeline orchestrateur
├── models/
│   ├── lof_tt.pkl / lof_ob.pkl
│   ├── tfidf_tt.pkl / tfidf_ob.pkl
│   ├── if_traces_tt.pkl / if_traces_ob.pkl
│   └── classifier_type_panne.pkl
├── tests/
│   ├── __init__.py
│   └── test_pipeline.py        23 tests unitaires
├── .github/
│   └── workflows/
│       └── ci.yml              Workflow GitHub Actions
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

# Démo
python demo.py
```

**Docker** :
```bash
# Lancer tout
docker-compose up -d

# Voir les logs
docker-compose logs -f api
docker-compose logs -f dashboard

# Arrêter
docker-compose down

# Reconstruire
docker-compose build --no-cache
docker-compose up -d
```

**Git** :
```bash
# Créer une branche feature
git checkout -b feature/nouvelle-fonctionnalite

# Commiter
git add .
git commit -m "feat: description du changement"

# Pusher
git push origin feature/nouvelle-fonctionnalite
```

---

*Rapport de la plateforme de déploiement*
*Composante génie logiciel du projet d'observabilité intelligente*
*Projet de maîtrise en génie logiciel*
