# Rapport de détection d'anomalies sur les traces — Train Ticket
## Comparaison de huit algorithmes classiques et de trois approches améliorées

---

## 1. Contexte et objectif

Ce rapport présente les résultats de l'application de plusieurs algorithmes de détection d'anomalies sur les **traces distribuées** du système microservices Train Ticket (41 services Java Spring Boot), en utilisant le dataset Nezha (Yu et al., FSE 2023).

**Rappel des résultats précédents** :
- Métriques (notebook 3) : Z-score F1 = 97.7%, détecte cpu_contention et network_delay
- Logs (notebook 4) : TF-IDF F1 = 98.9%, détecte exception et return

**Objectif** : évaluer la capacité des traces distribuées à détecter les 4 types de pannes, en complément des métriques et des logs.

**Limitation du dataset** : seulement 2 fenêtres de traces normales disponibles dans `construct_data` pour Train Ticket. Toutes les 135 fenêtres de `rca_data` sont anormales. Cette limitation motive l'exploration d'approches améliorées après la première batterie de tests.

---

## 2. Prétraitement des traces

### 2.1 Structure des données

Chaque ligne est un **span** — une action dans un service donné. Plusieurs spans avec le même TraceID forment l'arbre complet d'une requête.

### 2.2 Features extraites par fenêtre

| Feature | Ce qu'elle capture |
|---------|-------------------|
| nb_spans | Volume d'activité |
| nb_traces | Nombre de requêtes utilisateurs |
| nb_services | Services impliqués |
| duree_moy | Latence moyenne des spans |
| duree_max | Pic de latence |
| duree_p99 | Latence du 99ème percentile |
| duree_std | Variabilité des durées |
| spans_par_trace | Complexité moyenne des requêtes |

### 2.3 Baseline normale

| Feature | Moyenne | Écart-type |
|---------|---------|------------|
| nb_spans | 4742.5 | 208.6 |
| nb_traces | 66.5 | 6.4 |
| nb_services | 26.5 | 2.1 |
| duree_moy | 0.0244 ms | 0.0008 |
| duree_max | 0.8248 ms | 0.0212 |
| duree_p99 | 0.3615 ms | 0.0299 |

---

## 3. Algorithmes classiques testés

### 3.1 Seuil de latence

**Principe** : si la durée maximale d'une fenêtre dépasse la moyenne normale + 3 écarts-types, anomalie détectée.

**Résultats** : VP = 104, FP = 0, FN = 31 -> **F1 = 87.0%**

**Par type** : network_delay 95%, cpu_contention 86%, exception 72%, return 55%

### 3.2 Z-score multi-features

**Principe** : Z-score sur les 8 features. Si au moins une dépasse 3.0, anomalie.

**Résultats** : VP = 133, FP = 0, FN = 2 -> **F1 = 99.3%**

**Par type** : cpu_contention 100%, return 100%, network_delay 98%, exception 97%

**Analyse** : meilleur algorithme non supervisé classique. `duree_max` est le déclencheur principal (123 alertes).

### 3.3 Isolation Forest (agrégé par fenêtre)

**Résultats** : VP = 40, FP = 1, FN = 95 -> **F1 = 45.5%**

**Analyse** : inadapté — seulement 2 fenêtres normales, insuffisant pour construire des arbres significatifs.

### 3.4 SVM

**Configuration** : kernel RBF, class_weight='balanced'

**Résultats** : VP = 115, FP = 0, FN = 20 -> **F1 = 92.0%**

**Par type** : network_delay 98%, cpu_contention 81%, exception 79%, return 79%

### 3.5 Autoencoder

**Architecture** : 8 -> 4 -> 2 -> 4 -> 8

**Résultats** : VP = 135, FP = 1, FN = 0 -> **F1 = 99.6%**

**Analyse** : fonctionne bien contrairement aux métriques (F1 = 26.9% sur les métriques). Le faible nombre de fenêtres est paradoxalement un avantage — chaque fenêtre anormale est suffisamment différente des 2 normales.

### 3.6 DBSCAN

**Configuration** : eps=0.5, min_samples=5

**Résultats** : VP = 104, FP = 1, FN = 31 -> **F1 = 86.7%**

**Par type** : network_delay 95%, cpu_contention 76%, return 76%, exception 59%

### 3.7 Random Forest

**Résultats** : VP = 135, FP = 0, FN = 0 -> **F1 = 100%** \*

**Feature Importance** :

| Feature | Importance |
|---------|-----------|
| nb_traces | 28.1% |
| duree_p99 | 19.0% |
| duree_moy | 18.6% |
| duree_std | 13.9% |
| nb_spans | 9.3% |

\* Résultat à nuancer — seulement 2 fenêtres normales d'entraînement.

### 3.8 LSTM sur les séquences de spans

**Architecture** : Embedding(28, 16) -> LSTM(32) -> Dense(28, softmax)
**Accuracy** : 89.3%

**Résultats** : VP = 55, FP = 0, FN = 80 -> **F1 = 57.9%**

**Par type** : cpu_contention 62%, network_delay 55%, exception 28%, return 24%

**Analyse** : le LSTM est inadapté aux traces dans cette configuration car les pannes modifient les **durées** des appels, pas l'**ordre** des services appelés. Le LSTM capture l'ordre mais pas la latence.

---

## 4. Bilan des algorithmes classiques

| Algorithme | Type | F1 | VP | FP | FN |
|------------|------|-----|----|----|-----|
| **Random Forest** | Supervisé | **100%** \* | 135 | 0 | 0 |
| **Autoencoder** | Deep Learning | **99.6%** | 135 | 1 | 0 |
| **Z-score** | Non supervisé | **99.3%** | 133 | 0 | 2 |
| **SVM** | Supervisé | 92.0% | 115 | 0 | 20 |
| **Seuil latence** | Statistique | 87.0% | 104 | 0 | 31 |
| **DBSCAN** | Non supervisé | 86.7% | 104 | 1 | 31 |
| **LSTM (ordre)** | Deep Learning | 57.9% | 55 | 0 | 80 |
| **Isolation Forest** | Non supervisé | 45.5% | 40 | 1 | 95 |

\* Résultat à nuancer — seulement 2 fenêtres normales d'entraînement.

**Observation** : deux algorithmes obtiennent des performances décevantes malgré leur potentiel théorique — le LSTM et l'Isolation Forest. Ces deux résultats ont motivé le développement d'approches améliorées, présentées dans la section suivante.

---

## 5. Approches améliorées

Trois approches complémentaires ont été développées pour améliorer les résultats des algorithmes classiques limités.

### 5.1 LSTM sur les durées (au lieu de l'ordre des services)

**Motivation** : le LSTM classique prédit le prochain **service** appelé. Mais dans le dataset, l'ordre des services est similaire entre fenêtres normales et anormales — seules les **durées** changent pendant une panne.

**Approche** : entraîner le LSTM à prédire la **prochaine durée** d'un span, à partir des 10 durées précédentes. Une erreur de prédiction élevée indique une anomalie.

**Configuration** :
- Fenêtre de prédiction : 10 durées
- Données d'entraînement : 9 485 durées normales, 9 475 séquences
- Seuil optimal : erreur > 0.05

**Résultats** :

| Métrique | Valeur |
|---|---|
| VP | 116 |
| FN | 19 |
| **F1-score** | **92.4%** |

**Gain** : F1 passe de 57.9% (LSTM ordre) à **92.4%** (LSTM durées), soit **+34.5 points**.

### 5.2 Isolation Forest par service sur spans bruts

**Motivation** : l'Isolation Forest classique travaillait sur 2 fenêtres agrégées (2 points seulement), insuffisant pour construire des arbres significatifs.

**Approche** : entraîner **un Isolation Forest par service** directement sur les **durées de spans bruts** (des milliers de points par service).

**Configuration** :
- Feature : `duration_ms`
- 28 modèles (un par service actif)
- Contamination : 0.05
- Détection : au moins un service avec un taux d'anomalies supérieur à un seuil

**Résultats** :

| Seuil | VP | FN | F1 |
|---|---|---|---|
| 0.05 | 135 | 0 | **100.0%** |
| 0.08 | 135 | 0 | 100.0% |
| 0.10 | 135 | 0 | 100.0% |
| **0.12** | **132** | **3** | **98.9%** |
| 0.15 | 121 | 14 | 94.5% |
| 0.20 | 63 | 72 | 63.6% |

**Choix retenu** : seuil = 0.12 -> F1 = 98.9%. Ce seuil est le plus **conservateur** parmi ceux qui restent au-dessus de 95%. Les seuils plus bas (0.05, 0.08, 0.10) atteignent F1 = 100% mais risqueraient de générer des faux positifs sur d'autres jeux de données. C'est cet algorithme et ce seuil qui sont utilisés dans le pipeline final.

**Gain** : F1 passe de 45.5% (IF agrégé) à **98.9%** (IF par service), soit **+53.4 points**.

### 5.3 Analyse de la structure d'appels

**Motivation** : détecter les anomalies non pas dans les durées, mais dans la **structure du graphe d'appels** entre services.

**Approche** : construire la matrice d'appels normale (paires de services et leur fréquence), puis détecter les fenêtres qui s'écartent significativement de cette matrice.

**Résultats** :

| Seuil | VP | FN | F1 |
|---|---|---|---|
| 1.0 | 135 | 0 | **100.0%** |
| 2.0 | 135 | 0 | 100.0% |
| 3.0 | 135 | 0 | 100.0% |
| 5.0 | 129 | 6 | 97.7% |
| 8.0 | 113 | 22 | 91.1% |
| 10.0 | 91 | 44 | 80.5% |

**Analyse** : approche complémentaire qui capture une dimension différente des anomalies (structure vs durées). Les faibles seuils (1-3) atteignent F1 = 100%, mais avec le risque habituel de sur-ajustement à la baseline limitée.

---

## 6. Bilan des approches améliorées

| Algorithme | Version | F1 | Amélioration |
|------------|---------|-----|--------------|
| LSTM | Ordre services -> Durées | 57.9% -> 92.4% | +34.5 pts |
| Isolation Forest | Agrégé -> Par service | 45.5% -> 98.9% | +53.4 pts |
| Structure d'appels | Nouvelle approche | 100% | Nouveau |

**Conclusion technique** : deux algorithmes classiques initialement décevants ont été récupérés avec des adaptations ciblées. L'Isolation Forest par service, en particulier, atteint des performances comparables au Z-score tout en restant non supervisé et robuste.

---

## 7. Comparaison finale de tous les algorithmes

| Algorithme | Type | F1 | Utilisé dans pipeline final ? |
|---|---|---|---|
| Random Forest | Supervisé | 100% \* | Non (labels non disponibles en prod) |
| Structure d'appels | Statistique | 100% | Non (approche exploratoire) |
| **Isolation Forest par service** | **Non supervisé** | **98.9%** | **OUI (seuil 0.12)** |
| Autoencoder | Deep Learning | 99.6% | Non (complexité) |
| Z-score multi-features | Non supervisé | 99.3% | Non (choix pipeline) |
| LSTM (durées) | Deep Learning | 92.4% | Non (approche exploratoire) |
| SVM | Supervisé | 92.0% | Non (labels non disponibles) |
| Seuil latence | Statistique | 87.0% | Non |
| DBSCAN | Non supervisé | 86.7% | Non |
| LSTM (ordre) | Deep Learning | 57.9% | Non (inadapté) |
| Isolation Forest (agrégé) | Non supervisé | 45.5% | Non (remplacé par version par service) |

\* Résultat à nuancer — seulement 2 fenêtres normales.

---

## 8. Complémentarité métriques + logs + traces

| Type de panne | Métriques (Z-score) | Logs (TF-IDF) | Traces (IF par service) |
|---------------|--------------------|--------------------|-------------------|
| cpu_contention | **Détecté** | Détecté | **Détecté** |
| network_delay | **Détecté** | Détecté | **Détecté** |
| exception | **Manqué** | **Détecté** | Détecté |
| return | **Manqué** | **Détecté** | **Détecté** |

Les trois modalités sont complémentaires. La fusion des trois couvre l'ensemble des 4 types de pannes, ce qui justifie l'approche multi-modale retenue dans le pipeline final.

---

## 9. Conclusion

Le Z-score multi-features est le meilleur algorithme non supervisé **classique** sur les traces (F1 = 99.3%). Cependant, l'**Isolation Forest par service** développé en tant qu'approche améliorée atteint F1 = 98.9% avec un seuil conservateur, et présente l'avantage de fournir une **granularité par service** utile pour la localisation ultérieure des pannes. C'est cet algorithme qui est intégré au pipeline final.

Le LSTM classique (F1 = 57.9%) est inadapté car les pannes changent les durées, pas l'ordre des services. Le LSTM sur les durées récupère la performance (F1 = 92.4%) mais reste moins compétitif que l'IF par service.

La combinaison métriques + logs + traces couvre les 4 types de pannes.

---

*Rapport écrit dans le cadre du projet de maîtrise en génie logiciel*
*Dataset : Nezha (Yu et al., FSE 2023)*
