# Rapport de détection d'anomalies sur les traces — Train Ticket
## Comparaison de huit algorithmes sur les traces distribuées

---

## 1. Contexte et objectif

Ce rapport présente les résultats de l'application de huit algorithmes de détection d'anomalies sur les **traces distribuées** du système microservices Train Ticket (41 services Java Spring Boot), en utilisant le dataset Nezha (Yu et al., FSE 2023).

**Rappel des résultats précédents :**
- Métriques (notebook 3) : Z-score F1 = 97.7%, détecte cpu_contention et network_delay
- Logs (notebook 4) : TF-IDF F1 = 98.9%, détecte exception et return

**Objectif :** évaluer la capacité des traces distribuées à détecter les 4 types de pannes, en complément des métriques et des logs.

**Limitation du dataset :** seulement 2 fenêtres de traces normales disponibles dans construct_data pour Train Ticket. Toutes les 135 fenêtres de rca_data sont anormales.

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

## 3. Algorithme 1 — Seuil de latence

### Principe
Si la durée maximale d'une fenêtre dépasse la moyenne normale + 3 écarts-types, anomalie détectée.

### Résultats
| Métrique | Valeur |
|----------|--------|
| VP : 104 | FP : 0 | FN : 31 |
| **Précision** | **100%** |
| **Rappel** | **77.0%** |
| **F1-score** | **87.0%** |

### Par type : network_delay 95%, cpu_contention 86%, exception 72%, return 55%

---

## 4. Algorithme 2 — Z-score multi-features

### Principe
Z-score sur les 8 features. Si au moins une dépasse 3.0, anomalie.

### Résultats
| Métrique | Valeur |
|----------|--------|
| VP : 133 | FP : 0 | FN : 2 |
| **Précision** | **100%** |
| **Rappel** | **98.5%** |
| **F1-score** | **99.3%** |

### Par type : cpu_contention 100%, return 100%, network_delay 98%, exception 97%

### Analyse
Meilleur algorithme non supervisé. duree_max est le déclencheur principal (123 alertes).

---

## 5. Algorithme 3 — Isolation Forest

### Résultats
| Métrique | Valeur |
|----------|--------|
| VP : 40 | FP : 1 | FN : 95 |
| **F1-score** | **45.5%** |

### Analyse
Inadapté — seulement 2 fenêtres normales, insuffisant pour construire des arbres significatifs.

---

## 6. Algorithme 4 — SVM

### Résultats
| Métrique | Valeur |
|----------|--------|
| VP : 115 | FP : 0 | FN : 20 |
| **F1-score** | **92.0%** |

### Par type : network_delay 98%, cpu_contention 81%, exception 79%, return 79%

---

## 7. Algorithme 5 — Autoencoder

### Architecture : 8 → 4 → 2 → 4 → 8

### Résultats
| Métrique | Valeur |
|----------|--------|
| VP : 135 | FP : 1 | FN : 0 |
| **Précision** | **99.3%** |
| **Rappel** | **100%** |
| **F1-score** | **99.6%** |

### Analyse
Fonctionne bien contrairement aux métriques (24.7%). Le faible nombre de fenêtres (137) est paradoxalement un avantage — chaque fenêtre anormale est suffisamment différente des 2 normales.

---

## 8. Algorithme 6 — DBSCAN

### Configuration : eps=0.5, min_samples=5

### Résultats
| Métrique | Valeur |
|----------|--------|
| VP : 104 | FP : 1 | FN : 31 |
| **F1-score** | **86.7%** |

### Par type : network_delay 95%, cpu_contention 76%, return 76%, exception 59%

---

## 9. Algorithme 7 — Random Forest

### Résultats
| Métrique | Valeur |
|----------|--------|
| VP : 135 | FP : 0 | FN : 0 |
| **F1-score** | **100%** * |

### Feature Importance
| Feature | Importance |
|---------|-----------|
| nb_traces | 28.1% |
| duree_p99 | 19.0% |
| duree_moy | 18.6% |
| duree_std | 13.9% |
| nb_spans | 9.3% |

\* Résultat à nuancer — seulement 2 fenêtres normales.

---

## 10. Algorithme 8 — LSTM sur les séquences de spans

### Architecture : Embedding(28, 16) → LSTM(32) → Dense(28, softmax)
### Accuracy : 89.3%

### Résultats
| Métrique | Valeur |
|----------|--------|
| VP : 55 | FP : 0 | FN : 80 |
| **F1-score** | **57.9%** |

### Par type : cpu_contention 62%, network_delay 55%, exception 28%, return 24%

### Analyse
Le LSTM est inadapté aux traces car les pannes modifient les **durées** des appels, pas l'**ordre** des services appelés. Le LSTM capture l'ordre mais pas la latence.

---

## 11. Comparaison synthétique

| Algorithme | Type | F1 | VP | FP | FN |
|------------|------|-----|----|----|-----|
| **Random Forest** | Supervisé | **100%** * | 135 | 0 | 0 |
| **Autoencoder** | Deep Learning | **99.6%** | 135 | 1 | 0 |
| **Z-score** | Non supervisé | **99.3%** | 133 | 0 | 2 |
| **SVM** | Supervisé | 92.0% | 115 | 0 | 20 |
| **Seuil latence** | Statistique | 87.0% | 104 | 0 | 31 |
| **DBSCAN** | Non supervisé | 86.7% | 104 | 1 | 31 |
| **LSTM** | Deep Learning | 57.9% | 55 | 0 | 80 |
| **Isolation Forest** | Non supervisé | 45.5% | 40 | 1 | 95 |

---

## 12. Complémentarité métriques + logs + traces

| Type de panne | Métriques (Z-score) | Logs (TF-IDF) | Traces (Z-score) |
|---------------|--------------------|--------------------|-------------------|
| cpu_contention | **Détecté** | Détecté | **Détecté** |
| network_delay | **Détecté** | Détecté | **Détecté** |
| exception | **Manqué** | **Détecté** | Détecté |
| return | **Manqué** | **Détecté** | **Détecté** |

---

## 13. Conclusion

Le Z-score multi-features est l'algorithme non supervisé le plus performant sur les traces (F1 = 99.3%). Le LSTM est inadapté car les pannes changent les durées, pas l'ordre des services. La combinaison métriques + logs + traces couvre les 4 types de pannes.

---

*Rapport dans le cadre du projet de maîtrise en génie logiciel*
*Dataset : Nezha (Yu et al., FSE 2023)*
