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

- Collecter et analyser des logs, métriques et traces en temps réel
- Détecter automatiquement des anomalies via des algorithmes de ML
- Comparer les performances de détection sur deux systèmes différents
- Évaluer les modèles avec précision, rappel et F1-score

---

## Systèmes analysés

| Système | Services | Langages | Pannes |
|---------|----------|----------|--------|
| **Train Ticket** | 41 microservices | Java Spring Boot | 45 cas |
| **Online Boutique** | 12 microservices | Go, Python, Node.js | 56 cas |

---

## Dataset

**Nezha** — Yu et al., FSE 2023  
- 3 modalités : Logs · Métriques (21 colonnes) · Traces distribuées  
- 4 types de pannes : `return` · `exception` · `network_delay` · `cpu_contention`  
- Fenêtre d'anomalie : 3 minutes par panne  
- Lien : https://github.com/IntelligentDDS/Nezha

---

## Architecture du projet
intelligent-observability/
├── notebooks/                    # Analyse exploratoire
│   ├── 01_TrainTicket.ipynb      # Exploration Train Ticket
│   └── 02_OnlineBoutique.ipynb   # Exploration Online Boutique
├── figures/                      # Graphiques générés
│   ├── TrainTicket/              # 9 figures TT
│   └── OnlineBoutique/           # 9 figures OB
├── models/                       # Algorithmes de détection
├── results/                      # Résultats d'évaluation
├── requirements.txt              # Dépendances Python
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

# Télécharger les données
git clone https://github.com/IntelligentDDS/Nezha.git
```

---

## Branches

| Branche | Contenu | Statut |
|---------|---------|--------|
| `main` | Version stable finale | ✓ |
| `develop` | Intégration des features | En cours |
| `feature/exploration-data` | Notebooks d'exploration | ✓ Mergé |
| `feature/detection-metrics` | Z-score, Isolation Forest | À venir |
| `feature/detection-logs` | Analyse des logs | À venir |
| `feature/detection-traces` | Analyse des traces | À venir |
| `feature/evaluation` | Précision, rappel, F1 | À venir |

---

## Résultats préliminaires

| Type de panne | Signal principal | Modalité |
|---------------|-----------------|---------|
| `return` | Taux d'erreur par service | Logs |
| `exception` | Stack traces | Logs |
| `cpu_contention` | CPU > 2x normale | Métriques |
| `network_delay` | Latence P99 | Métriques + Traces |

---

## Technologies utilisées

| Catégorie | Outils |
|-----------|--------|
| Langage | Python 3.12 |
| Analyse | Pandas, NumPy |
| Visualisation | Matplotlib, Seaborn |
| ML | Scikit-learn |
| Versionnement | Git, GitHub |
| Environnement | Jupyter, venv |

---

## Références

- Yu et al. (2023). *Nezha: Interpretable Fine-Grained Root Causes
  Analysis for Microservices on Multi-Modal Observability Data*.
  FSE 2023.
- FudanSELab. *Train Ticket: A Benchmark Microservice System*.
  https://github.com/FudanSELab/train-ticket

---

## Auteur

**Eunice** — Master 2 Génie Logiciel  
GitHub : [@Eunicepris](https://github.com/Eunicepris)
# Intelligent_observability
Projet de fin de maitrise: Conception et déploiement d’une plateforme cloud-native d’observabilité intelligente intégrant Machine Learning, DevOps et MLOps
