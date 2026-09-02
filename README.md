# Intelligent Observability Platform
## Détection d'anomalies dans les systèmes microservices

> Projet technique de fin de Maîtrise — Génie Logiciel  
> Université du Québec — 2026

---

## Contexte

Les architectures microservices modernes génèrent un volume important
de données d'observabilité : logs applicatifs, métriques système et
traces distribuées. Ce projet conçoit et implémente une plateforme
intelligente capable de détecter automatiquement des anomalies dans
ces systèmes sans intervention humaine.

---

## Objectifs

- Collecter et analyser des logs, métriques et traces
- Détecter automatiquement des anomalies via des algorithmes de ML
- Comparer les performances de détection sur deux systèmes différents
- Évaluer les modèles avec précision, rappel et F1-score
- **Construire un pipeline automatique déployable en production**

---

## Résultats principaux

- **Fusion multi-modale** : F1 = 100%
- **Classification supervisée** : F1 = 63%
- 64 tests automatisés avec 71% de couverture
- 0 avertissement flake8 (code 100% conforme PEP 8)
- **API REST sémantique** (200/400/404)
- **21+ algorithmes** évalués et comparés
- **Pipeline fonctionnel** avec API REST, dashboard interactif, Docker et CI/CD

---

## Systèmes analysés

| Système | Services | Langages | Pannes |
|---------|----------|----------|--------|
| **Train Ticket** | 41 microservices | Java Spring Boot | 45 cas |
| **Online Boutique** | 10 microservices | Go, Python, Node.js | 56 cas |

---

## Dataset

**Nezha** — Yu et al., FSE 2023  
- 3 modalités : Logs · Métriques (21 colonnes) · Traces distribuées  
- 4 types de pannes : `return` · `exception` · `network_delay` · `cpu_contention`  
- Fenêtre d'anomalie : 3 minutes par panne  
- Lien : https://github.com/IntelligentDDS/Nezha

---

## Architecture du projet

Intelligent_observability/
├── notebooks/ Études comparatives (13 notebooks)
│ ├── 01_TrainTicket.ipynb
│ ├── 02_OnlineBoutique.ipynb
│ ├── 03-10 : détection par modalité et fusion
│ ├── 12_sauvegarde_modeles.ipynb
│ ├── 13_analyse_localisation.ipynb
│ └── 14_classification_type_panne.ipynb
├── pipeline/ Modules Python du pipeline
│ ├── ingestion.py Chargement des données
│ ├── detection.py Détection + fusion + sévérité
│ ├── classification_type.py Classification supervisée
│ ├── alertes.py Gestion des alertes
│ ├── main.py Orchestration (Facade)
│ ├── exceptions.py Hiérarchie d'exceptions
│ └── logger.py Configuration du logging
├── models/ 7 modèles pré-entraînés (~44 MB)
├── api/ API FastAPI
├── dashboard/ Interface Streamlit
├── tests/ Tests automatisés (27 tests)
├── .github/workflows/ CI/CD GitHub Actions
├── figures/ Graphiques générés
├── results/ Rapports et résultats (11 rapports)
├── data/ Dataset Nezha
├── Dockerfile
├── docker-compose.yml
├── config.yaml Configuration centralisée
├── requirements.txt Dépendances Python
└── README.md

---

## Installation

```bash
# Cloner le repo
git clone https://github.com/Eunicepris/Intelligent_observability.git
cd Intelligent_observability

# Créer l'environnement virtuel
python3 -m venv venv
source venv/bin/activate

# Installer les dépendances
pip install -r requirements.txt

# Télécharger le dataset Nezha
git clone https://github.com/IntelligentDDS/Nezha.git /tmp/nezha

# Copier les données au bon endroit (structure attendue par le code)
mkdir -p data/normal data/anomalies
cp -r /tmp/nezha/construct_data/* data/normal/
cp -r /tmp/nezha/rca_data/* data/anomalies/
```

---

## Utilisation du pipeline

### 1. Utilisation programmatique

```python
from pipeline.main import PipelineComplet

# Initialiser le pipeline
pipeline = PipelineComplet(systeme='train_ticket')

# Analyser une fenêtre
resultat = pipeline.traiter_fenetre('2023-01-29', '08_43')

print(f"Sévérité : {resultat['severite']}")     # WARNING
print(f"Confiance : {resultat['confiance']*100:.0f}%")
print(f"Action : {resultat['action']}")
```

### 2. API REST

Lancer l'API :

```bash
uvicorn api.main:app --reload
```

Endpoints :

| Méthode | Endpoint | Description |
|---------|----------|-------------|
| POST | `/api/detecter` | Analyser une fenêtre |
| GET | `/api/alertes` | Consulter les alertes |
| GET | `/api/statistiques` | Statistiques globales |
| GET | `/api/systemes` | Systèmes supportés |
| GET | `/api/health` | Vérification de santé |
| GET | `/docs` | Documentation Swagger |


note:
POST /api/detecter retourne :
200 OK : détection réussie
400 Bad Request : entrée invalide (ex: 24_89)
404 Not Found : fenêtre absente du dataset

Exemple :

```bash
curl -X POST http://localhost:8000/api/detecter \
  -H "Content-Type: application/json" \
  -d '{"systeme": "train_ticket", "date": "2023-01-29", "window": "08_43"}'
```

### 3. Dashboard Streamlit

Lancer le dashboard (l'API doit être active) :

```bash
streamlit run dashboard/app.py
```

Accès : http://localhost:8501

### 4. Déploiement avec Docker

Lancer l'API et le dashboard ensemble :

```bash
docker-compose up -d
```

Accès :
- Dashboard : http://localhost:8501
- API : http://localhost:8000

---

## Algorithmes utilisés

Le pipeline utilise des algorithmes **non supervisés adaptatifs** :

| Modalité | Algorithme | Rationale |
|----------|-----------|-----------|
| Métriques | LOF | Densité locale, adaptatif |
| Logs | TF-IDF | Robuste, sans labels |
| Traces | Isolation Forest par service | S'adapte à chaque service |

Ces choix résultent d'une étude comparative de 21 algorithmes documentée dans les notebooks 03-10.

Un **Random Forest** supervisé complète le pipeline pour classifier le type de panne parmi 4 catégories (voir notebook 14).

---

## Classification en 4 niveaux

| Niveau | Modalités confirmant | Action |
|--------|---------------------|--------|
| CRITICAL | 3/3 | Investigation immédiate |
| WARNING | 2/3 | Investigation à planifier |
| LOW | 1/3 | Vérifier la modalité |
| NORMAL | 0/3 | Surveillance passive |

---

## Résultats par type de panne

| Type de panne | Signal principal | Modalité |
|---------------|-----------------|---------|
| `return` | Comportement applicatif anormal | Traces |
| `exception` | Stack traces | Logs |
| `cpu_contention` | CPU > 2x normale | Métriques |
| `network_delay` | Latence P99 | Métriques + Traces |

---

## Tests

Le projet contient 64 tests automatisés répartis dans 4 fichiers :
- test_pipeline.py : 23 tests unitaires (fonctions pures)
- test_integration.py : 4 tests d'intégration (pipeline complet)
- test_api.py : 10 tests d'API (endpoints HTTP)
- test_pipeline_main.py : 10 tests d'orchestration
- test_errors.py : 17 tests d'erreurs et cas limites

Couverture : 71% global (89% pour l'API)

```bash
pytest tests/ -v
```

---

## Rapports détaillés

Le dossier `results/` contient les rapports scientifiques du projet :

- `rapport_complet_trainticket.md` — Étude Train Ticket
- `rapport_complet_onlineboutique.md` — Étude Online Boutique
- `rapport_algorithmes_robustes.md` — Analyse de robustesse (LOF, XGBoost)
- `rapport_fusion_multimodale.md` — Fusion multi-modale
- `rapport_classification_type_panne.md` — Classification supervisée du type de panne
- `rapport_plateforme_deploiement.md` — API, dashboard, Docker, CI/CD
- `rapport_pipeline_core.md` — Documentation du pipeline

---

## Branches Git

| Branche | Contenu | Statut |
|---------|---------|--------|
| `main` | Version stable finale | ✓ |
| `develop` | Intégration des features | En cours |
| `feature/exploration-data` | Notebooks d'exploration | ✓ Mergé |
| `feature/detection-algorithmes` | 21 algorithmes évalués | ✓ Complet |
| `feature/pipeline-complet` | Pipeline + API + Dashboard + Docker + CI/CD | En cours |

---

## Technologies utilisées

| Catégorie | Outils |
|-----------|--------|
| Langage | Python 3.12 |
| Analyse | Pandas, NumPy |
| Visualisation | Matplotlib, Seaborn, Plotly |
| ML | Scikit-learn, XGBoost |
| API | FastAPI, Uvicorn |
| Dashboard | Streamlit |
| Config | PyYAML |
| Tests | pytest, pytest-cov |
| Conteneurisation | Docker, docker-compose |
| CI/CD | GitHub Actions |
| Versionnement | Git, GitHub |
| Environnement | Jupyter, venv |

---

## Limitations connues

1. **Localisation** — L'identification précise du service défaillant reste un problème ouvert (Top-1 = 11.9% avec les traces seules). Une extension avec analyse de graphe des dépendances est identifiée comme perspective future.

2. **Baseline limitée** — Le dataset Nezha ne contient que 2 fenêtres normales pour logs et traces, limitant la calibration.

3. **Apprentissage figé** — Les modèles ne s'adaptent pas automatiquement aux nouvelles données. Un re-entraînement périodique est recommandé.

---

## Reproduire les résultats du rapport

Cette section explique comment obtenir **exactement les mêmes résultats** que ceux présentés dans le rapport de projet MGL8707.

### Contexte

Le scénario principal du rapport (Section 3.3.5) présente l'analyse de la fenêtre `08_43` du 29 janvier 2023 sur Train Ticket, qui produit :

| Élément | Valeur attendue |
|---|---|
| Sévérité | **WARNING** |
| Confiance globale | **67%** (2/3 modalités) |
| Métriques anormales | ✓ |
| Logs anormaux | ✗ |
| Traces anormales | ✓ |
| Type de panne prédit | **return** |
| Confiance du type | **90%** |
| Action spécifique | Vérifier valeurs retournées par le service |

Pour obtenir ces valeurs, il faut le **dataset Nezha complet** (~3 GB, non inclus dans le dépôt pour des raisons de taille et de licence).

### Étape 1 — Télécharger le dataset Nezha

```bash
# Cloner le dépôt officiel Nezha (Yu et al., FSE 2023)
git clone https://github.com/IntelligentDDS/Nezha.git /tmp/nezha
```

### Étape 2 — Organiser les données

Le pipeline attend une structure spécifique :

```bash
# Créer la structure attendue
mkdir -p ~/nezha_data/normal
mkdir -p ~/nezha_data/anomalies

# Copier les données normales (comportement de référence)
cp -r /tmp/nezha/construct_data/* ~/nezha_data/normal/

# Copier les données avec anomalies injectées
cp -r /tmp/nezha/rca_data/* ~/nezha_data/anomalies/
```

Structure attendue :

```
~/nezha_data/
├── normal/
│   ├── 2023-01-29/
│   │   ├── log/
│   │   ├── metric/
│   │   └── trace/
│   └── 2023-01-30/
└── anomalies/
    ├── 2023-01-29/
    │   ├── log/
    │   ├── metric/
    │   └── trace/
    └── ...
```

### Étape 3 — Configurer le chemin avec .env

```bash
# Depuis la racine du projet
cd Intelligent_observability

# Copier le fichier d'exemple
cp .env.example .env

# Éditer .env avec l'éditeur de votre choix
nano .env
```

Modifier la ligne dans `.env` avec le chemin **absolu** vers vos données :

```
DATA_DIR=/home/votre_utilisateur/nezha_data
```

### Étape 4 — Lancer la plateforme

```bash
# Redémarrer les conteneurs pour prendre en compte le .env
docker-compose down
docker-compose up -d

# Attendre 30 secondes que les services démarrent
sleep 30

# Vérifier que tout est prêt
curl http://localhost:8000/api/health
```

Réponse attendue :

```json
{"status": "healthy", "pipelines_charges": ["train_ticket", "online_boutique"]}
```

### Étape 5 — Reproduire le scénario du rapport

```bash
curl -X POST http://localhost:8000/api/detecter \
  -H "Content-Type: application/json" \
  -d '{"systeme": "train_ticket", "date": "2023-01-29", "window": "08_43"}' \
  | python3 -m json.tool
```

**Réponse attendue** (identique au rapport) :

```json
{
  "systeme": "train_ticket",
  "fenetre": "2023-01-29 08_43",
  "anomalie": true,
  "severite": "WARNING",
  "confiance": 0.6667,
  "modalites": {
    "metriques": true,
    "logs": false,
    "traces": true
  },
  "type_panne": {
    "type_predit": "return",
    "confiance": 0.9,
    "probabilites": {
      "cpu_problem": 0.0,
      "exception": 0.1,
      "network_delay": 0.0,
      "return": 0.9
    },
    "action_specifique": "Vérifier valeurs retournées par le service"
  },
  "action": "Alerte modérée — investigation à planifier"
}
```

### Étape 6 — Utiliser le dashboard

**Accès** : http://localhost:8501

**Reproduction du scénario dans le dashboard** :

1. Ouvrir l'onglet **Détection**
2. Sélectionner :
   - Système : `train_ticket`
   - Date : `2023-01-29`
   - Fenêtre : `08_43`
3. Cliquer sur **Lancer l'analyse**
4. Le résultat WARNING/return à 67% s'affiche

### Autres scénarios validés

| Fenêtre (Train Ticket, 2023-01-29) | Sévérité attendue | Type de panne |
|---|---|---|
| `08_43` | WARNING | return |
| `24_89` | HTTP 400 (format invalide) | - |
| `11_51` | HTTP 404 (fenêtre absente) | - |

### Sans le dataset complet

Si vous ne pouvez pas télécharger Nezha, le projet fonctionne quand même avec le **mini-dataset intégré** (`tests/mini_data/`), mais les résultats seront différents :

- La fenêtre `08_43` retournera **LOW** au lieu de WARNING
- La confiance sera plus faible (33% au lieu de 67%)
- Le type de panne prédit peut varier
- **La plateforme fonctionne normalement**, c'est juste que le dataset restreint donne moins de signal

Ce mode est parfait pour :
- Découvrir la plateforme rapidement
- Développer de nouvelles fonctionnalités
- Exécuter le CI/CD automatique
- Faire des démos

### Dépannage

**Problème** : Après `docker-compose up`, l'API répond mais la détection retourne "fenêtre non trouvée".
**Solution** : Vérifier que le chemin dans `.env` est correct :
```bash
docker-compose config | grep -A 2 volumes
# Doit afficher le vrai chemin de vos données
```

**Problème** : Résultats différents de ceux du rapport.
**Solution** : Vérifier que `.env` existe et pointe vers Nezha complet. Redémarrer :
```bash
docker-compose down && docker-compose up -d
```

**Problème** : `.env` n'est pas pris en compte.
**Solution** : Vérifier que `.env` est bien à la racine du projet (même dossier que `docker-compose.yml`) et redémarrer.

## Perspectives futures

- Analyse de graphe pour améliorer la localisation
- Streaming temps réel (Kafka)
- Base de données pour les alertes (PostgreSQL)
- Notifications (email, Slack, PagerDuty)
- Pipeline MLOps (MLflow, drift detection)
- Authentification et rate limiting sur l'API

---

## Références

- Yu et al. (2023). *Nezha: Interpretable Fine-Grained Root Causes Analysis for Microservices on Multi-Modal Observability Data*. FSE 2023.
- FudanSELab. *Train Ticket: A Benchmark Microservice System*. https://github.com/FudanSELab/train-ticket
- GoogleCloudPlatform. *Online Boutique*. https://github.com/GoogleCloudPlatform/microservices-demo

---

## Auteur

**Eunice** — Master 2 Génie Logiciel  
GitHub : [@Eunicepris](https://github.com/Eunicepris)

---

## Description courte

Projet de fin de maîtrise : conception et déploiement d'une plateforme cloud-native d'observabilité intelligente intégrant Machine Learning, DevOps et MLOps.
