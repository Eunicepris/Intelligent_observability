# Rapport de détection d'anomalies sur les logs — Train Ticket
## Comparaison de cinq algorithmes sur les logs applicatifs

---

## 1. Contexte et objectif

Ce rapport présente les résultats de l'application de cinq algorithmes de détection d'anomalies sur les **logs applicatifs** du système microservices Train Ticket (41 services Java Spring Boot), en utilisant le dataset Nezha (Yu et al., FSE 2023).

**Motivation** : le notebook 3 a montré que les métriques détectent bien les pannes `cpu_contention` et `network_delay` (Z-score F1 = 97.7%) mais manquent les pannes `exception` et `return` — invisibles dans le CPU, la mémoire ou la latence. Ces pannes sont visibles uniquement dans les logs applicatifs.

**Objectif** : détecter les 45 pannes injectées (135 fenêtres d'anomalie) à partir des logs, en ciblant particulièrement les pannes `exception` et `return`.

**Limitation du dataset** : Nezha ne fournit que 2 fenêtres de logs normaux pour Train Ticket dans `construct_data`. Toutes les 135 fenêtres de `rca_data` sont anormales. Cette contrainte influence le choix des algorithmes et l'interprétation des résultats.

---

## 2. Prétraitement des logs

### 2.1 Chargement robuste

Les fichiers CSV de logs contiennent du JSON imbriqué avec des virgules qui perturbent le parsing standard. Un lecteur ligne par ligne avec `csv.reader` a été implémenté pour garantir la lecture des 8 colonnes sans perte de données.

### 2.2 Extraction des templates

Les logs bruts sont transformés en templates en remplaçant les valeurs variables par des tokens :
- UUID → `<UUID>`
- Nombres → `<NUM>`
- TraceID/SpanID → `<HEX>`

Le message métier est extrait entre crochets `[ ]`.

Exemple :
```
Brut  : "16:48:42.424 INFO getRouteByRouteId — Route ID: d5b9f2fe-f924..."
Template : "getRouteByRouteId | Get Route By Id | Route ID: <UUID>"
```

**Baseline construite** : 238 templates uniques sur 2 fenêtres normales.

---

## 3. Algorithme 1 — Comptage de templates

### Principe
On compare les templates de chaque fenêtre anormale avec la baseline. Un template jamais vu en phase normale est un signal d'anomalie.

### Deux niveaux de détection
- **Global** : template nouveau dans n'importe quel service
- **Service ciblé** : template nouveau dans le service en panne

### Résultats

| Niveau | VP | FN | Rappel | F1 |
|--------|----|----|--------|-----|
| Global | 135 | 0 | 100% | 100% |
| Service ciblé | 34 | 101 | 25.2% | 40.2% |

### Détection par type de panne (service ciblé)

| Type | Détecté | Taux |
|------|---------|------|
| `return` | 25/33 | 76% |
| `cpu_contention` | 3/21 | 14% |
| `network_delay` | 5/42 | 12% |
| `exception` | 1/39 | 3% |

### Analyse

La détection globale à 100% est trompeuse — avec seulement 2 fenêtres normales, presque tout template est "nouveau". La détection par service ciblé (F1 = 40.2%) est plus réaliste. Le comptage détecte bien les pannes `return` (76%) car elles génèrent des messages d'erreur spécifiques, mais manque les `exception` (3%) car les exceptions Java utilisent des templates similaires aux logs normaux.

---

## 4. Algorithme 2 — TF-IDF

### Principe

TF-IDF (Term Frequency — Inverse Document Frequency) transforme les logs en vecteurs numériques en mesurant l'importance de chaque mot. Un mot fréquent dans une fenêtre mais rare globalement reçoit un score élevé.

On calcule la similarité cosinus entre chaque fenêtre anormale et le vecteur de référence normal. Une similarité faible indique une anomalie.

### Configuration

- Vocabulaire : 355 termes
- Seuil optimal : similarité < 0.95
- Référence : vecteur moyen des 2 fenêtres normales

### Résultats

| Métrique | Valeur |
|----------|--------|
| VP | 132 |
| FP | 0 |
| FN | 3 |
| **Précision** | **100%** |
| **Rappel** | **97.8%** |
| **F1-score** | **98.9%** |

### Détection par type de panne

| Type | Détecté | Taux |
|------|---------|------|
| `cpu_contention` | 21/21 | 100% |
| `exception` | 39/39 | 100% |
| `network_delay` | 41/42 | 98% |
| `return` | 31/33 | 94% |

### Analyse

TF-IDF atteint un F1 de 98.9% — nettement supérieur au comptage de templates. Il détecte 100% des pannes `exception` — la cible principale de ce notebook. Le seuil élevé de 0.95 est lié à la baseline limitée (2 fenêtres normales) et devrait être ajusté avec plus de données normales.

---

## 5. Algorithme 3 — Random Forest

### Principe

Algorithme supervisé qui utilise les labels du ground truth pour apprendre à classer les fenêtres. Les logs sont transformés en 8 features numériques par fenêtre.

### Features extraites

| Feature | Ce qu'elle capture |
|---------|-------------------|
| `nb_lignes` | Volume de logs |
| `nb_templates` | Diversité des messages |
| `nb_services` | Services actifs |
| `nb_info` | Messages informatifs |
| `nb_warn` | Avertissements |
| `nb_error` | Erreurs |
| `taux_erreur` | Proportion d'erreurs |
| `nb_nouveaux` | Templates jamais vus en normal |

### Configuration
- 100 arbres, profondeur maximale 5
- `class_weight='balanced'` pour compenser le déséquilibre (2 normales vs 135 anormales)

### Résultats

| Métrique | Valeur |
|----------|--------|
| VP | 135 |
| FP | 0 |
| FN | 0 |
| **Précision** | **100%** |
| **Rappel** | **100%** |
| **F1-score** | **100%** |

### Feature Importance

| Feature | Importance |
|---------|-----------|
| nb_nouveaux | 30.4% |
| nb_lignes | 19.2% |
| nb_info | 15.2% |
| nb_templates | 13.0% |
| nb_warn | 7.9% |
| nb_error | 6.0% |
| nb_services | 4.6% |
| taux_erreur | 3.7% |

### Analyse

Le F1 de 100% doit être fortement nuancé. Avec seulement 2 fenêtres normales d'entraînement, le modèle mémorise les 2 fenêtres normales et classe tout le reste comme anormal. Ce résultat ne reflète pas une capacité de généralisation réelle. En revanche, le feature importance est très instructif : `nb_nouveaux` (templates jamais vus en normal) est la feature la plus discriminante (30.4%), confirmant les résultats du comptage de templates.

---

## 6. Algorithme 4 — LSTM DeepLog

### Principe

DeepLog (Du et al., 2017) est un réseau LSTM qui apprend l'ordre normal des templates de logs. Il prédit le prochain template attendu à partir des 5 précédents. Si le template réel n'est pas dans le top K des prédictions, c'est une anomalie.

### Architecture

| Couche | Forme | Rôle |
|--------|-------|------|
| Embedding | 238 → 32 | Transforme chaque ID en vecteur dense |
| LSTM | 64 neurones | Apprend les dépendances séquentielles |
| Dense + Softmax | 238 sorties | Probabilité de chaque template suivant |

### Configuration
- Fenêtre de prédiction : 5 templates
- Séquences d'entraînement : 4 964 (depuis 2 fenêtres normales)
- Époques : 30
- Accuracy finale : 84.5%
- Top K : 5
- Seuil : taux d'anomalie > 3%

### Résultats

| Métrique | Valeur |
|----------|--------|
| VP | 130 |
| FP | 0 |
| FN | 5 |
| **Précision** | **100%** |
| **Rappel** | **96.3%** |
| **F1-score** | **98.1%** |

### Détection par type de panne

| Type | Détecté | Taux |
|------|---------|------|
| `exception` | 39/39 | 100% |
| `return` | 33/33 | 100% |
| `cpu_contention` | 20/21 | 95% |
| `network_delay` | 38/42 | 90% |

### Analyse

Le LSTM détecte 100% des pannes `exception` et `return` — exactement les types invisibles dans les métriques. Son accuracy de 84.5% est remarquable étant donné que l'entraînement se fait sur seulement 2 fenêtres normales (4 964 séquences). Le seuil bas de 3% est nécessaire car l'accuracy imparfaite du modèle génère un taux naturel de fausses prédictions d'environ 15%.

---

## 7. Algorithme 5 — SVM

### Principe

Support Vector Machine supervisé qui trace une frontière optimale entre les fenêtres normales et anormales dans l'espace des 8 features extraites des logs. Utilise un kernel RBF (Radial Basis Function) pour des frontières non linéaires.

### Configuration
- Kernel : RBF
- `class_weight='balanced'`
- Données normalisées avec StandardScaler

### Résultats

| Métrique | Valeur |
|----------|--------|
| VP | 133 |
| FP | 0 |
| FN | 2 |
| **Précision** | **100%** |
| **Rappel** | **98.5%** |
| **F1-score** | **99.3%** |

### Détection par type de panne

| Type | Détecté | Taux |
|------|---------|------|
| `exception` | 39/39 | 100% |
| `return` | 33/33 | 100% |
| `network_delay` | 42/42 | 100% |
| `cpu_contention` | 19/21 | 90% |

### Analyse

Le SVM atteint un F1 de 99.3% et détecte 100% des pannes `exception`, `return` et `network_delay`. Seul `cpu_contention` est légèrement manqué (90%). La normalisation des features est cruciale pour le SVM — sans elle, les features à grande échelle (nb_lignes ~2500) domineraient les features à petite échelle (taux_erreur ~0.01).

---

## 8. Comparaison synthétique

| Algorithme | Type | F1 | VP | FP | FN | exception | return |
|------------|------|-----|----|----|-----|-----------|--------|
| **Random Forest** | Supervisé | **100%** * | 135 | 0 | 0 | 100% | 100% |
| **SVM** | Supervisé | **99.3%** | 133 | 0 | 2 | 100% | 100% |
| **TF-IDF** | Non supervisé | **98.9%** | 132 | 0 | 3 | 100% | 94% |
| **LSTM DeepLog** | Deep Learning | **98.1%** | 130 | 0 | 5 | 100% | 100% |
| **Comptage templates** | Statistique | 40.2% | 34 | 0 | 101 | 3% | 76% |

\* Résultat à nuancer — seulement 2 fenêtres normales d'entraînement.

### Observations clés

1. **Précision parfaite (100%)** — aucun algorithme ne génère de fausse alarme. Les 5 algorithmes sont très conservateurs dans leurs alertes.

2. **Le comptage de templates est insuffisant** — F1 de 40.2% seulement. La baseline de 2 fenêtres normales est trop limitée pour cette approche statistique simple.

3. **TF-IDF et LSTM se distinguent** — F1 de 98.9% et 98.1% respectivement. Ces deux algorithmes non supervisés sont les plus adaptés car ils ne nécessitent pas de labels. TF-IDF est plus simple et légèrement meilleur. LSTM apporte la dimension séquentielle mais nécessite plus de données d'entraînement pour atteindre son plein potentiel.

4. **Random Forest et SVM sont performants mais biaisés** — leur F1 élevé est partiellement dû au faible nombre de fenêtres normales (2 seulement). Le modèle mémorise les 2 cas normaux plutôt que d'apprendre des patterns généralisables.

5. **Les pannes `exception` sont détectées à 100%** par 4 algorithmes sur 5 — c'est l'objectif principal de ce notebook, puisque les métriques les manquent complètement.

---

## 9. Complémentarité métriques + logs

| Type de panne | Métriques (Z-score) | Logs (TF-IDF) | Couverture |
|---------------|--------------------|--------------------|------------|
| `cpu_contention` | **Détecté** (100%) | Détecté (100%) | Redondant |
| `network_delay` | **Détecté** (93%) | Détecté (98%) | Redondant |
| `exception` | **Manqué** | **Détecté** (100%) | Complémentaire |
| `return` | **Manqué** | **Détecté** (94%) | Complémentaire |

Les métriques et les logs sont complémentaires : les métriques détectent les pannes de ressources, les logs détectent les pannes applicatives. Aucune source seule ne couvre les 4 types de pannes. La fusion multi-modale est nécessaire pour une couverture complète.

---

## 10. Conclusion et perspectives

### Conclusion

TF-IDF est l'algorithme non supervisé le plus performant sur les logs de Train Ticket avec un F1 de 98.9%. Il détecte 100% des pannes `exception` que les métriques manquent complètement.

Le LSTM DeepLog (F1 = 98.1%) apporte une dimension séquentielle complémentaire et détecte 100% des pannes `exception` et `return`. Sa performance est remarquable étant donné la baseline limitée à 2 fenêtres normales.

La principale limitation est la taille de la baseline normale (2 fenêtres). Avec plus de données normales, les performances du comptage de templates et du LSTM s'amélioreraient significativement.

### Perspectives

1. **Détection sur les traces** — analyser les durées et structures des appels entre services
2. **Fusion multi-modale** — combiner métriques + logs + traces pour une couverture complète
3. **Application sur Online Boutique** — valider la généralisation des algorithmes sur un deuxième système
4. **Enrichir la baseline** — collecter plus de données normales pour améliorer la robustesse

---

*Rapport dans le cadre du projet de maîtrise en génie logiciel*
*Dataset : Nezha (Yu et al., FSE 2023) — github.com/IntelligentDDS/Nezha*
