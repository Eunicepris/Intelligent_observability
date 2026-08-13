# Intelligent Observability Platform
## Détection d'anomalies dans les systèmes microservices

> Mémoire de fin de Maîtrise — Génie Logiciel  
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

- **Fusion multi-modale** : F1 = 100% (sur Train Ticket et Online Boutique)
- **21+ algorithmes** évalués et comparés
- **Pipeline fonctionnel** avec API REST et dashboard interactif

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
├── notebooks/ Études comparatives (11 notebooks)
│ ├── 01_TrainTicket.ipynb
│ ├── 02_OnlineBoutique.ipynb
│ ├── 03-10 : détection par modalité et fusion
│ └── 12_sauvegarde_modeles.ipynb
├── pipeline/ Modules Python du pipeline
│ ├── ingestion.py Chargement des données
│ ├── detection.py Détection + fusion + classification
│ ├── alertes.py Gestion des alertes
│ └── main.py Orchestration
├── models/ 6 modèles pré-entraînés (43 MB)
├── api/ API FastAPI
├── dashboard/ Interface Streamlit
├── figures/ Graphiques générés
├── results/ Rapports et résultats
├── data/ Dataset Nezha
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

# Télécharger les données (si pas déjà présent)
git clone https://github.com/IntelligentDDS/Nezha.git data/nezha
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
| GET | `/docs` | Documentation Swagger |

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

### 4. Démonstration rapide

```bash
python demo.py
```

---

## Algorithmes utilisés

Le pipeline utilise des algorithmes **non supervisés adaptatifs** :

| Modalité | Algorithme | Rationale |
|----------|-----------|-----------|
| Métriques | LOF | Densité locale, adaptatif |
| Logs | TF-IDF | Robuste, sans labels |
| Traces | Isolation Forest par service | S'adapte à chaque service |

Ces choix résultent d'une étude comparative de 21 algorithmes documentée dans les notebooks 03-10.

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

## Rapports détaillés

Le dossier `results/` contient les rapports scientifiques du projet :

- `rapport_complet_trainticket.md` — Étude Train Ticket
- `rapport_complet_onlineboutique.md` — Étude Online Boutique
- `rapport_algorithmes_robustes.md` — Analyse de robustesse (LOF, XGBoost)
- `rapport_fusion_multimodale.md` — Fusion multi-modale
- `rapport_pipeline_core.md` — Documentation du pipeline

---

## Branches Git

| Branche | Contenu | Statut |
|---------|---------|--------|
| `main` | Version stable finale | ✓ |
| `develop` | Intégration des features | En cours |
| `feature/exploration-data` | Notebooks d'exploration | ✓ Mergé |
| `feature/detection-algorithmes` | 21 algorithmes évalués | ✓ Complet |
| `feature/pipeline-complet` | Pipeline + API + Dashboard | En cours |

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
| Versionnement | Git, GitHub |
| Environnement | Jupyter, venv |

---

## Limitations connues

1. **Localisation** — L'identification précise du service défaillant reste un problème ouvert (Top-1 = 11.9% avec les traces seules). Une extension avec analyse de graphe des dépendances est identifiée comme perspective future.

2. **Baseline limitée** — Le dataset Nezha ne contient que 2 fenêtres normales pour logs et traces, limitant la calibration.

3. **Apprentissage figé** — Les modèles ne s'adaptent pas automatiquement aux nouvelles données. Un re-entraînement périodique est recommandé.

---

## Perspectives futures

- Analyse de graphe pour améliorer la localisation
- Streaming temps réel (Kafka)
- Dockerisation pour déploiement
- Base de données pour les alertes (PostgreSQL)
- Notifications (email, Slack, PagerDuty)
- Pipeline MLOps (MLflow, drift detection)

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