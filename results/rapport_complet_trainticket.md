# Rapport complet — Détection d'anomalies dans Train Ticket
## 18 algorithmes sur 3 modalités de données

---

## 1. Contexte

**Système** : Train Ticket — 41 microservices Java Spring Boot
**Dataset** : Nezha (Yu et al., FSE 2023)
**Dates** : 29 et 30 janvier 2023
**Pannes** : 45 injections → 135 fenêtres d'anomalie de 3 minutes
**Types** : return (11), exception (13), network_delay (14), cpu_contention (7)

**Approche** : détection non supervisée — les modèles apprennent le comportement normal et détectent les écarts.

**Limitation du dataset** : les fichiers métriques sont identiques entre construct_data et rca_data (MD5 vérifié). Les logs et traces ne disposent que de 2 fenêtres normales.

---

## 2. Résultats par modalité

### 2.1 Métriques — 5 algorithmes

Métriques surveillées : CpuUsageRate(%), MemoryUsageRate(%), PodServerLatencyP99(s), NetworkReceiveBytes, NetworkTransmitBytes

| Algorithme | Type | F1 | VP | FP | FN | Observation |
|------------|------|-----|----|----|-----|-------------|
| Autoencoder V2 | Deep Learning | 99.6% | 135 | 1 | 0 | Entraîné par fenêtre (2 fenêtres pures) |
| Random Forest | Supervisé | 99.6% | 134 | 0 | 1 | Feature importance : réseau 30.7%, latence 30.5% |
| Z-score | Non supervisé | 97.7% | 129 | 0 | 6 | Meilleur non supervisé classique |
| Isolation Forest | Non supervisé | 95.3% | 123 | 0 | 12 | contamination=0.05 |
| Autoencoder V1 | Deep Learning | 49.2% | 44 | 0 | 91 | Données contaminées — fichiers identiques |

**Observation clé** : l'Autoencoder V1 (points bruts, F1=49.2%) vs V2 (par fenêtre, F1=99.6%) démontre que la pureté des données d'entraînement est plus importante que leur quantité.

**Feature importance (Random Forest)** :
- NetworkReceiveBytes : 30.7%
- PodServerLatencyP99 : 30.5%
- NetworkTransmitBytes : 16.2%
- MemoryUsageRate : 13.2%
- CpuUsageRate : 9.5%

Le CPU n'est pas la métrique la plus discriminante — le réseau et la latence sont les signaux les plus forts.

### 2.2 Logs — 5 algorithmes

Prétraitement : extraction de templates (remplacement UUID, nombres, timestamps par des tokens). Baseline : 238 templates uniques sur 2 fenêtres normales.

| Algorithme | Type | F1 | VP | FP | FN | Observation |
|------------|------|-----|----|----|-----|-------------|
| Random Forest | Supervisé | 100% * | 135 | 0 | 0 | Feature importance : nb_nouveaux 30.4% |
| SVM | Supervisé | 99.3% | 133 | 0 | 2 | kernel=rbf, class_weight=balanced |
| TF-IDF | Non supervisé | 98.9% | 132 | 0 | 3 | Meilleur non supervisé — seuil similarité<0.95 |
| LSTM DeepLog | Deep Learning | 98.1% | 130 | 0 | 5 | Accuracy 84.5%, top K=5, seuil 3% |
| Comptage templates | Statistique | 40.2% | 34 | 0 | 101 | Baseline trop limitée (2 fenêtres) |

\* Résultat à nuancer — seulement 2 fenêtres normales d'entraînement.

**Feature importance (Random Forest)** :
- nb_nouveaux (templates jamais vus) : 30.4%
- nb_lignes : 19.2%
- nb_info : 15.2%
- nb_templates : 13.0%

**Détection par type de panne (LSTM DeepLog)** :
- exception : 100%
- return : 100%
- cpu_contention : 95%
- network_delay : 90%

### 2.3 Traces — 8 algorithmes

Features extraites : nb_spans, nb_traces, nb_services, duree_moy, duree_max, duree_p99, duree_std, spans_par_trace.

| Algorithme | Type | F1 | VP | FP | FN | Observation |
|------------|------|-----|----|----|-----|-------------|
| Random Forest | Supervisé | 100% * | 135 | 0 | 0 | Feature importance : nb_traces 28.1% |
| Autoencoder | Deep Learning | 99.6% | 135 | 1 | 0 | Entraîné sur 2 fenêtres pures |
| Z-score | Non supervisé | 99.3% | 133 | 0 | 2 | Meilleur non supervisé — seuil 3.0 |
| SVM | Supervisé | 92.0% | 115 | 0 | 20 | kernel=rbf, class_weight=balanced |
| Seuil latence | Statistique | 87.0% | 104 | 0 | 31 | duree_max > moyenne + 3σ |
| DBSCAN | Non supervisé | 86.7% | 104 | 1 | 31 | eps=0.5, min_samples=5 |
| LSTM | Deep Learning | 57.9% | 55 | 0 | 80 | Inadapté — pannes changent durées, pas l'ordre |
| Isolation Forest | Non supervisé | 45.5% | 40 | 1 | 95 | Inadapté — 2 fenêtres normales insuffisantes |

\* Résultat à nuancer — seulement 2 fenêtres normales d'entraînement.

**Feature importance (Random Forest)** :
- nb_traces : 28.1%
- duree_p99 : 19.0%
- duree_moy : 18.6%
- duree_std : 13.9%
- nb_spans : 9.3%

---

## 3. Comparaison transversale

### 3.1 Meilleur algorithme par modalité

| Modalité | Meilleur non supervisé | F1 | Meilleur supervisé | F1 |
|----------|----------------------|-----|-------------------|-----|
| Métriques | Z-score | 97.7% | Random Forest | 99.6% |
| Logs | TF-IDF | 98.9% | SVM | 99.3% |
| Traces | Z-score | 99.3% | Random Forest | 100% |

### 3.2 Détection par type de panne — meilleur algorithme par modalité

| Type de panne | Métriques (Z-score) | Logs (TF-IDF) | Traces (Z-score) |
|---------------|--------------------|--------------------|-------------------|
| cpu_contention | **Détecté** (100%) | Détecté (100%) | **Détecté** (100%) |
| network_delay | **Détecté** (93%) | Détecté (98%) | **Détecté** (98%) |
| exception | **Manqué** (69%) | **Détecté** (100%) | Détecté (97%) |
| return | **Manqué** (76%) | **Détecté** (94%) | **Détecté** (100%) |

### 3.3 Complémentarité des modalités

Les métriques manquent les pannes applicatives (exception, return) car elles ne génèrent pas de changement dans le CPU, la mémoire ou la latence. Les logs détectent ces pannes grâce aux messages d'erreur et aux templates nouveaux. Les traces détectent les anomalies de volume et de durée des requêtes.

Aucune modalité seule ne couvre les 4 types de pannes. La combinaison des 3 est nécessaire pour une couverture complète.

---

## 4. Analyse des algorithmes transversaux

### 4.1 Z-score — performant partout

| Modalité | F1 |
|----------|-----|
| Métriques | 97.7% |
| Traces | 99.3% |

Simple, rapide, interprétable. Fonctionne bien quand les signaux d'anomalie sont nets. Ne nécessite pas de labels. Recommandé pour le déploiement en production.

### 4.2 Random Forest — le plus performant mais supervisé

| Modalité | F1 |
|----------|-----|
| Métriques | 99.6% |
| Logs | 100% |
| Traces | 100% |

Les meilleurs résultats mais nécessite des labels (ground truth). En production réelle, les labels ne sont pas disponibles — ce qui rend cette approche inadaptée pour un déploiement automatique. Utile pour l'analyse post-incident.

### 4.3 Autoencoder — sensible à la préparation des données

| Version | Modalité | F1 | Entraînement |
|---------|----------|-----|-------------|
| V1 | Métriques | 49.2% | 76 360 points contaminés |
| V2 | Métriques | 99.6% | 2 fenêtres pures |
| — | Traces | 99.6% | 2 fenêtres pures |

Le même algorithme passe de 49.2% à 99.6% en changeant uniquement la granularité des données d'entraînement. La pureté des données est plus importante que leur quantité.

### 4.4 LSTM — adapté aux logs, inadapté aux traces

| Modalité | F1 | Raison |
|----------|-----|--------|
| Logs | 98.1% | Les pannes changent les templates → séquences anormales |
| Traces | 57.9% | Les pannes changent les durées, pas l'ordre des services |

Le LSTM détecte les anomalies d'ordre séquentiel. Sur les logs, les pannes génèrent des templates nouveaux qui rompent la séquence normale. Sur les traces, les mêmes services sont appelés dans le même ordre — seule la latence change, ce que le LSTM ne capture pas.

### 4.5 Isolation Forest — inadapté avec peu de données normales

| Modalité | F1 |
|----------|-----|
| Métriques | 95.3% |
| Traces | 45.5% |

Sur les métriques (76 360 points), IF fonctionne correctement. Sur les traces (2 fenêtres = 2 points), il est incapable de construire des arbres significatifs.

---

## 5. Limitations du dataset

### 5.1 Fichiers métriques identiques

Les fichiers métriques de construct_data et rca_data sont identiques (MD5 vérifié). Ils couvrent toute la journée — normal et anormal dans le même fichier. Impact : l'Autoencoder V1 échoue car il apprend aussi les anomalies.

### 5.2 Baseline normale limitée

Seulement 2 fenêtres de logs et traces normaux pour Train Ticket. Toutes les 135 fenêtres de rca_data sont anormales — impossible d'enrichir la baseline. Impact : les résultats des algorithmes supervisés (Random Forest 100%, SVM 99.3%) sont à nuancer car le modèle mémorise les 2 fenêtres normales.

### 5.3 Fenêtres partiellement anormales

Les 135 fenêtres labellisées anormales ne le sont pas uniformément. Seul le service ciblé est en panne (1/41). La première minute n'est que partiellement affectée. Certaines pannes (return) ne produisent pas de signal dans toutes les modalités.

---

## 6. Conclusion

### Résultats principaux

1. **Le Z-score est l'algorithme non supervisé le plus fiable** — F1 de 97.7% sur les métriques et 99.3% sur les traces. Simple, rapide et interprétable.

2. **TF-IDF est le meilleur pour les logs** — F1 de 98.9%. Il détecte 100% des pannes exception que les métriques manquent.

3. **L'Autoencoder V2 démontre l'importance de la préparation des données** — le passage de points bruts (F1=49.2%) à une agrégation par fenêtre (F1=99.6%) sans changer l'architecture.

4. **Le LSTM est adapté aux logs mais pas aux traces** — les pannes modifient l'ordre des templates de logs mais pas l'ordre des services dans les traces.

5. **Les 3 modalités sont complémentaires** — les métriques détectent les pannes de ressources, les logs détectent les pannes applicatives, les traces confirment les deux.

6. **Le réseau et la latence sont plus discriminants que le CPU** — observation contre-intuitive révélée par le feature importance du Random Forest.

### Recommandation pour la production

Pour un déploiement en production sans labels disponibles :
- **Métriques** : Z-score par service (F1 = 97.7%)
- **Logs** : TF-IDF avec similarité cosinus (F1 = 98.9%)
- **Traces** : Z-score multi-features (F1 = 99.3%)
- **Fusion** : vote majoritaire des 3 modalités

### Perspectives

1. Validation sur Online Boutique — vérifier la généralisation
2. Fusion multi-modale — combiner les scores des 3 modalités
3. Enrichir la baseline — collecter plus de données normales
4. Graph Neural Network — exploiter la structure de graphe des traces
5. Validation avec AnoMod — dataset alternatif avec 5 modalités

---

*Rapport écrit dans le cadre du projet de maîtrise en génie logiciel*
*Détection d'anomalies dans les systèmes microservices*
*Dataset : Nezha (Yu et al., FSE 2023) — github.com/IntelligentDDS/Nezha*
