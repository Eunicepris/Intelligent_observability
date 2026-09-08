# Intelligent Observability Platform

## Détection intelligente d’anomalies dans les systèmes microservices

> Projet technique de fin de maîtrise en génie logiciel — MGL8707  
> 2026

---

## Présentation

Les architectures microservices génèrent plusieurs types de données d’observabilité, notamment les métriques, les logs et les traces distribuées. Lorsqu’un incident survient, ces informations peuvent être dispersées entre plusieurs services, ce qui rend le diagnostic difficile.

Ce projet propose une plateforme d’observabilité intelligente permettant d’analyser à la demande une fenêtre de données microservices afin de :

- détecter automatiquement des anomalies ;
- combiner les résultats provenant des métriques, logs et traces ;
- calculer un niveau de sévérité et de confiance ;
- prédire le type de panne lorsqu’une anomalie est détectée ;
- proposer une action de diagnostic ;
- enregistrer et consulter les alertes ;
- visualiser les résultats dans un dashboard ;
- exposer les fonctionnalités par une API REST.

La plateforme a été évaluée sur deux systèmes du dataset public **Nezha** : **Train Ticket** et **Online Boutique**.

---

## Fonctionnalités principales

La version finale comprend :

- détection multimodale sur les métriques, logs et traces ;
- fusion des résultats des trois modalités ;
- niveaux de sévérité `NORMAL`, `LOW`, `WARNING` et `CRITICAL` ;
- classification supervisée du type de panne ;
- estimation d’un niveau de confiance ;
- recommandation d’une action générale et d’une action spécifique ;
- persistance et filtrage des alertes ;
- statistiques agrégées sur les alertes ;
- API REST avec FastAPI ;
- documentation Swagger interactive ;
- dashboard Streamlit ;
- utilisation directe du pipeline depuis Python ;
- conteneurisation avec Docker et Docker Compose ;
- tests automatisés ;
- pipeline CI/CD avec GitHub Actions ;
- publication de l’image Docker dans GitHub Container Registry.

---

## Résultats principaux

Les principaux résultats obtenus pendant le projet sont :

- plus de **20 approches de détection** étudiées ;
- **LOF** retenu pour les métriques ;
- **TF-IDF** retenu pour les logs ;
- **Isolation Forest** retenu pour les traces ;
- fusion multimodale atteignant un **F1 jusqu’à 100 % sur les données évaluées** ;
- classification supervisée du type de panne avec un **F1 pondéré de 63 %** ;
- **64 tests automatisés** ;
- **71 % de couverture globale** mesurée sur la version finale ;
- contrôles Flake8 automatisés ;
- API REST avec six routes applicatives ;
- dashboard Streamlit à trois onglets ;
- pipeline CI/CD à cinq jobs.

Les performances indiquées correspondent aux données et scénarios évalués dans le cadre du projet académique. Elles ne constituent pas une garantie de performance sur un environnement de production différent.

---

## Systèmes étudiés

| Système | Nombre de microservices | Technologies principales |
|---|---:|---|
| Train Ticket | 41 | Java / Spring Boot |
| Online Boutique | 10 | Go, Python, Node.js et autres |

---

## Dataset Nezha

Le projet utilise le dataset public **Nezha**, présenté par Yu et al. à ESEC/FSE 2023.

Il fournit trois principales modalités d’observabilité :

- métriques ;
- logs ;
- traces distribuées.

Les données contiennent plusieurs catégories de pannes, notamment :

- `return` ;
- `exception` ;
- `network_delay` ;
- `cpu_contention` ;
- `cpu_consumed`.

Pour le classificateur final développé dans ce projet, les problèmes CPU sont regroupés dans la classe `cpu_problem`.

Les quatre classes finales sont donc :

```text
cpu_problem
network_delay
exception
return
```

Le dataset Nezha complet n’est pas inclus dans ce dépôt en raison de sa taille.

---

# Démarrage rapide

Le dépôt contient un petit jeu de données dans :

```text
tests/mini_data
```

Il permet de lancer rapidement la plateforme sans télécharger le dataset Nezha complet.

## Prérequis

Pour la méthode Docker recommandée :

- Git ;
- Docker ;
- Docker Compose.

Pour une exécution Python locale :

- Python 3.10 ou supérieur ;
- Python 3.12 recommandé.

---

## 1. Cloner le projet

```bash
git clone <URL_DU_DEPOT>
cd Intelligent_observability
```

---

## 2. Lancer la plateforme avec Docker

```bash
docker compose up -d --build
```

Si aucune variable `DATA_DIR` n’est définie, Docker Compose utilise automatiquement :

```text
tests/mini_data
```

Vérifier l’état de l’API :

```bash
curl http://localhost:8000/api/health
```

Réponse attendue :

```json
{
  "status": "healthy",
  "pipelines_charges": [
    "train_ticket",
    "online_boutique"
  ]
}
```

Une fois les conteneurs démarrés :

- Dashboard Streamlit : port `8501`
- API FastAPI : port `8000`
- Swagger : port `8000`, chemin `/docs`

Arrêter l’application :

```bash
docker compose down
```

---

## Important : mini-dataset et dataset complet

Le mini-dataset fourni dans `tests/mini_data` sert principalement à :

- vérifier rapidement le fonctionnement du projet ;
- exécuter les tests automatisés ;
- utiliser le projet dans le CI ;
- développer sans télécharger plusieurs gigaoctets de données.

Il ne reproduit pas nécessairement les résultats exacts du scénario présenté dans le rapport MGL8707.

Pour reproduire les résultats du rapport, utiliser le dataset Nezha complet comme expliqué dans la section :

**Reproduire le scénario du rapport**

---

# Architecture

La plateforme utilise une architecture en couches.

```text
Clients
│
├── Dashboard Streamlit
├── Swagger / API REST
└── Scripts Python
        │
        ▼
FastAPI
        │
        ▼
PipelineComplet
        │
        ├── IngestionEngine
        ├── DetecteurAnomalies
        ├── ClassificateurTypePanne
        └── SystemeAlertes
                │
                ▼
Données Nezha / modèles / configuration / alertes
```

`PipelineComplet` joue le rôle de façade et orchestre les différentes étapes du traitement.

---

## Pipeline de traitement

Pour une fenêtre donnée, le traitement suit principalement les étapes suivantes :

```text
Entrée
  │
  ▼
Validation
  │
  ▼
Ingestion
  │
  ├── Métriques
  ├── Logs
  └── Traces
  │
  ▼
Détection multimodale
  │
  ▼
Fusion
  │
  ▼
Sévérité + confiance
  │
  ├── NORMAL
  ├── LOW
  ├── WARNING
  └── CRITICAL
  │
  ▼
Classification du type de panne
(si anomalie)
  │
  ▼
Action recommandée
  │
  ▼
Enregistrement éventuel de l’alerte
```

---

# Algorithmes utilisés

## Détection multimodale

| Modalité | Algorithme final | Rôle |
|---|---|---|
| Métriques | LOF | Détection d’anomalies selon la densité locale |
| Logs | TF-IDF + similarité cosinus | Comparaison des contenus textuels |
| Traces | Isolation Forest par service | Détection de comportements atypiques dans les traces |

Ces choix résultent d’une phase expérimentale comparant plus de vingt approches.

---

## Fusion multimodale

La plateforme combine les décisions produites par les trois modalités.

Trois stratégies ont notamment été étudiées :

- `or` ;
- `vote_majoritaire` ;
- `and`.

La stratégie peut être configurée dans `config.yaml`.

---

## Sévérité

La sévérité dépend du nombre de modalités signalant une anomalie.

| Modalités anormales | Sévérité | Confiance |
|---:|---|---:|
| 0 / 3 | NORMAL | 0 % |
| 1 / 3 | LOW | 33 % |
| 2 / 3 | WARNING | 67 % |
| 3 / 3 | CRITICAL | 100 % |

Une détection `NORMAL` n’est pas enregistrée comme alerte.

Les niveaux `LOW`, `WARNING` et `CRITICAL` peuvent produire une alerte persistante.

---

## Classification du type de panne

Lorsqu’une anomalie est détectée, un modèle Random Forest prédit une classe parmi :

```text
cpu_problem
network_delay
exception
return
```

Le résultat contient notamment :

- le type prédit ;
- la confiance ;
- les probabilités de chaque classe ;
- une action spécifique recommandée.

Le F1 pondéré obtenu par ce classificateur sur les données évaluées est de **63 %**.

---

# Structure du projet

```text
Intelligent_observability/
│
├── api/
│   └── main.py
│
├── dashboard/
│   └── app.py
│
├── pipeline/
│   ├── alertes.py
│   ├── classification_type.py
│   ├── detection.py
│   ├── exceptions.py
│   ├── ingestion.py
│   ├── logger.py
│   └── main.py
│
├── models/
│   └── modèles pré-entraînés
│
├── notebooks/
│   └── 13 notebooks expérimentaux
│
├── results/
│   └── rapports et résultats expérimentaux
│
├── tests/
│   ├── mini_data/
│   ├── test_api.py
│   ├── test_errors.py
│   ├── test_integration.py
│   ├── test_pipeline.py
│   └── test_pipeline_main.py
│
├── .github/
│   └── workflows/
│       └── ci.yml
│
├── Dockerfile
├── docker-compose.yml
├── config.yaml
├── pyproject.toml
├── requirements.txt
├── demo.py
└── README.md
```

---

# Utilisation locale avec Python

## Installation

Créer un environnement virtuel :

```bash
python3 -m venv venv
```

Linux/macOS :

```bash
source venv/bin/activate
```

Windows :

```text
venv\Scripts\activate
```

Installer les dépendances :

```bash
pip install -r requirements.txt
```

Python 3.12 est recommandé afin de rester cohérent avec l’environnement utilisé par le projet et le pipeline CI.

---

# Utilisation directe du pipeline

Exemple :

```python
from pipeline.main import PipelineComplet

pipeline = PipelineComplet(systeme="train_ticket")

resultat = pipeline.traiter_fenetre(
    "2023-01-29",
    "08_43"
)

print(f"Sévérité : {resultat['severite']}")
print(f"Confiance : {resultat['confiance'] * 100:.0f}%")
print(f"Action : {resultat['action']}")
```

Le pipeline peut également être utilisé depuis les notebooks et les tests d’intégration.

---

# API REST

Lancer l’API localement :

```bash
uvicorn api.main:app --reload
```

## Routes applicatives

| Méthode | Route | Description |
|---|---|---|
| GET | `/` | Informations générales |
| GET | `/api/health` | Vérification de l’état de l’API |
| GET | `/api/systemes` | Liste des systèmes supportés |
| POST | `/api/detecter` | Analyse d’une fenêtre |
| GET | `/api/alertes` | Consultation et filtrage des alertes |
| GET | `/api/statistiques` | Statistiques sur les alertes |

La documentation Swagger interactive est générée automatiquement à :

```text
/docs
```

---

## Exemple de détection

```bash
curl -X POST http://localhost:8000/api/detecter \
  -H "Content-Type: application/json" \
  -d '{
    "systeme": "train_ticket",
    "date": "2023-01-29",
    "window": "08_43"
  }'
```

L’API distingue notamment :

```text
200 → requête traitée correctement
400 → entrée sémantiquement invalide
404 → fenêtre ou données demandées absentes
422 → validation structurelle FastAPI/Pydantic
500 → erreur interne
```

---

# Dashboard Streamlit

Lancer le dashboard :

```bash
streamlit run dashboard/app.py
```

L’API doit être accessible pour que le dashboard puisse fonctionner.

Le dashboard comprend trois onglets :

### Détection

Permet de :

- sélectionner un système ;
- sélectionner une date ;
- sélectionner une fenêtre ;
- lancer une analyse ;
- afficher la sévérité ;
- visualiser le résultat des trois modalités ;
- consulter le type de panne prédit ;
- afficher les actions recommandées.

### Alertes

Permet de :

- consulter l’historique des alertes ;
- filtrer par système ;
- filtrer par sévérité ;
- limiter le nombre de résultats affichés.

### Statistiques

Affiche :

- le nombre total d’alertes ;
- leur répartition par système ;
- leur répartition par niveau de sévérité.

---

# Alertes

Les alertes sont persistées au format JSON.

Une alerte contient notamment :

- système ;
- fenêtre analysée ;
- horodatage ;
- sévérité ;
- confiance ;
- modalités ;
- services suspects éventuels ;
- type de panne éventuel ;
- action recommandée.

Avec Docker Compose, un volume persistant permet de conserver les alertes entre les redémarrages des conteneurs.

---

# Tests automatisés

La version finale comprend **64 tests répartis dans cinq fichiers**.

| Fichier | Tests | Objectif principal |
|---|---:|---|
| `test_pipeline.py` | 23 | Fusion, sévérité, confiance, actions et alertes |
| `test_integration.py` | 4 | Scénarios d’intégration |
| `test_api.py` | 10 | API REST et codes HTTP |
| `test_pipeline_main.py` | 10 | Orchestration et traitement batch |
| `test_errors.py` | 17 | Entrées invalides, configuration et cas limites |
| **Total** | **64** | |

Exécuter toute la suite :

```bash
pytest tests/ -v
```

Mesurer la couverture :

```bash
pytest tests/ \
  --cov=pipeline \
  --cov=api \
  --cov=dashboard \
  --cov-report=term-missing
```

La version finale du projet a obtenu une couverture globale de **71 %**.

Le dossier `tests/mini_data` permet d’exécuter les tests sans nécessiter le dataset Nezha complet.

---

# Qualité du code

Le projet utilise notamment :

- Flake8 ;
- pytest ;
- pytest-cov ;
- configuration Black ;
- configuration isort.

Le pipeline CI effectue une première vérification bloquante des erreurs Python critiques.

Une deuxième vérification Flake8 analyse également les aspects de style et de complexité en mode non bloquant.

Les configurations de formatage sont centralisées dans `pyproject.toml`.

---

# CI/CD

GitHub Actions automatise les principales validations du projet.

Le workflow comprend cinq jobs :

```text
1. Lint code Python
       │
       ▼
2. Tests unitaires ─────┐
                        │
3. Tests intégration ───┤
                        ▼
4. Build & Push Docker Image
                        │
                        ▼
5. Déploiement simulé
```

Les tests unitaires et les tests d’intégration peuvent s’exécuter en parallèle après le lint.

Lorsque les validations réussissent :

1. Docker Buildx construit l’image ;
2. l’image est publiée dans GitHub Container Registry ;
3. des tags permettent de relier l’image au code correspondant ;
4. le workflow termine par une simulation de déploiement.

La dernière étape est volontairement une **simulation** : aucun déploiement automatique vers un environnement Kubernetes ou de production n’est effectué dans la version actuelle.

---

# Configuration

Les principaux paramètres sont regroupés dans :

```text
config.yaml
```

La configuration comprend notamment :

- chemin vers les données ;
- fichier d’alertes ;
- stratégie de fusion ;
- paramètres associés aux systèmes et à la détection.

La configuration est partiellement externalisée. L’ajout d’un nouveau système nécessite encore des modèles adaptés et certaines modifications du code.

---

# Reproduire le scénario du rapport MGL8707

Le scénario principal du rapport utilise :

```text
Système : Train Ticket
Date : 2023-01-29
Fenêtre : 08_43
```

Avec le dataset Nezha complet utilisé pendant le projet, le résultat attendu est :

| Élément | Résultat |
|---|---|
| Anomalie | Oui |
| Sévérité | WARNING |
| Confiance globale | environ 67 % |
| Métriques | Anormales |
| Logs | Normaux |
| Traces | Anormales |
| Type prédit | `return` |
| Confiance classification | 90 % |

Ces valeurs ne sont pas nécessairement reproduites avec `tests/mini_data`.

---

## 1. Télécharger Nezha

Cloner le dépôt officiel **IntelligentDDS/Nezha** dans un emplacement local.

Exemple :

```bash
git clone <URL_DU_DEPOT_OFFICIEL_NEZHA> /tmp/nezha
```

---

## 2. Préparer les données

Créer une structure de ce type :

```text
nezha_data/
├── normal/
│   ├── 2023-01-29/
│   └── 2023-01-30/
│
└── anomalies/
    ├── 2023-01-29/
    └── ...
```

Copier :

```text
construct_data → normal/
rca_data       → anomalies/
```

Par exemple :

```bash
mkdir -p ~/nezha_data/normal
mkdir -p ~/nezha_data/anomalies

cp -r /tmp/nezha/construct_data/* ~/nezha_data/normal/
cp -r /tmp/nezha/rca_data/* ~/nezha_data/anomalies/
```

---

## 3. Configurer Docker

Copier le fichier d’exemple :

```bash
cp .env.example .env
```

Modifier ensuite `.env` :

```text
DATA_DIR=/chemin/absolu/vers/nezha_data
```

Le fichier `.env` est local et ne doit pas être versionné.

---

## 4. Redémarrer la plateforme

```bash
docker compose down
docker compose up -d --build
```

Vérifier :

```bash
curl http://localhost:8000/api/health
```

Puis lancer le scénario :

```bash
curl -X POST http://localhost:8000/api/detecter \
  -H "Content-Type: application/json" \
  -d '{
    "systeme": "train_ticket",
    "date": "2023-01-29",
    "window": "08_43"
  }'
```

---

# Rapports expérimentaux

Le dossier `results/` conserve les principaux rapports produits pendant l’expérimentation.

Il contient notamment des analyses concernant :

- Train Ticket ;
- Online Boutique ;
- comparaison des algorithmes ;
- robustesse et généralisation ;
- fusion multimodale ;
- classification du type de panne ;
- pipeline logiciel ;
- plateforme et déploiement.

Les notebooks associés sont disponibles dans `notebooks/`.

---

# Notebooks

Le projet contient **13 notebooks expérimentaux**.

Ils couvrent notamment :

- exploration de Train Ticket ;
- exploration d’Online Boutique ;
- analyse des métriques ;
- analyse des logs ;
- analyse des traces ;
- comparaison des algorithmes ;
- fusion multimodale ;
- sauvegarde des modèles ;
- localisation ;
- classification du type de panne.

Les notebooks constituent la partie expérimentale du projet. Le code de l’application finale se trouve principalement dans `pipeline/`, `api/` et `dashboard/`.

---

# Technologies

| Catégorie | Technologies |
|---|---|
| Langage | Python 3.12 |
| Données | Pandas, NumPy |
| Machine Learning | Scikit-learn |
| API | FastAPI, Uvicorn, Pydantic |
| Dashboard | Streamlit, Plotly |
| Configuration | PyYAML |
| Tests | pytest, pytest-cov |
| Qualité | Flake8 |
| Conteneurisation | Docker, Docker Compose |
| CI/CD | GitHub Actions |
| Versionnement | Git, GitHub |
| Expérimentation | Jupyter Notebook |

---

# Limites actuelles

La plateforme constitue un prototype fonctionnel et non une solution de monitoring de production complète.

Les principales limites sont :

1. **Analyse à la demande**  
   La plateforme analyse des fenêtres temporelles sélectionnées par l’utilisateur. Elle ne traite pas actuellement un flux continu en temps réel.

2. **Deux systèmes supportés**  
   La version finale prend en charge Train Ticket et Online Boutique. Ajouter un nouveau système nécessite de nouveaux modèles et certaines adaptations.

3. **Pas de cycle MLOps automatisé**  
   Le projet ne comprend pas encore de détection automatique de dérive, de réentraînement automatique ni de registre de modèles.

4. **Pas de déploiement Kubernetes final**  
   Le pipeline CI/CD construit et publie l’image Docker, mais la dernière étape de déploiement est simulée.

5. **Pas d’authentification**  
   L’API et le dashboard ne mettent pas encore en œuvre de mécanisme d’authentification ou d’autorisation.

6. **Dataset de test réduit**  
   `tests/mini_data` permet de vérifier le fonctionnement logiciel mais n’est pas destiné à reproduire toutes les performances expérimentales du dataset complet.

7. **Localisation de la cause**  
   La localisation précise du service responsable d’une anomalie reste moins robuste que la détection globale et constitue une perspective d’amélioration.

---

# Perspectives

Les principales évolutions possibles sont :

- ingestion continue via OpenTelemetry ;
- traitement streaming ;
- Kafka ou technologie équivalente ;
- déploiement Kubernetes ;
- infrastructure as code ;
- observabilité de la plateforme elle-même ;
- suivi des modèles ;
- détection de dérive ;
- réentraînement automatisé ;
- versionnement et registre des modèles ;
- authentification et contrôle d’accès ;
- amélioration de la localisation de la cause racine ;
- déduplication et gestion avancée des alertes.

Ces éléments constituent des perspectives et ne font pas partie du périmètre final implémenté.

---

# Branche de remise

La branche :

```text
main
```

contient la version stable utilisée pour la remise du projet.

---

# Référence principale

Le dataset utilisé est associé à l’article :

> G. Yu, P. Chen, Y. Li, H. Chen, X. Li et Z. Zheng,  
> “Nezha: Interpretable Fine-Grained Root Causes Analysis for Microservices on Multi-modal Observability Data”,  
> ESEC/FSE 2023.

---

# Licence

Ce projet est distribué selon les conditions précisées dans le fichier `LICENSE`.

---

# Auteur

Projet technique de fin de maîtrise en génie logiciel.

**Intelligent Observability Platform — 2026**