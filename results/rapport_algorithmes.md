# Rapport de détection d'anomalies — Train Ticket
## Comparaison de trois algorithmes sur les métriques système

---

## 1. Contexte et objectif

Ce rapport présente les résultats de l'application de trois algorithmes de détection d'anomalies sur les métriques du système microservices **Train Ticket** (41 services Java Spring Boot), en utilisant le dataset **Nezha** (Yu et al., FSE 2023).

**Objectif** : détecter automatiquement les 45 pannes injectées (135 fenêtres d'anomalie de 3 minutes chacune) à partir des métriques système, sans connaissance préalable des pannes.

**Approche** : apprentissage non supervisé — les modèles apprennent le comportement normal et détectent les écarts.

**Métriques surveillées** :
- `CpuUsageRate(%)` — taux d'utilisation CPU
- `MemoryUsageRate(%)` — taux d'utilisation mémoire
- `PodServerLatencyP99(s)` — latence P99 côté serveur
- `NetworkReceiveBytes` — octets réseau reçus
- `NetworkTransmitBytes` — octets réseau transmis

**Évaluation** : précision, rappel et F1-score contre le `ground_truth.csv` (135 fenêtres anormales).

---

## 2. Algorithme 1 — Z-score

### Principe

Le Z-score mesure l'écart d'une valeur par rapport à la moyenne normale :

```
Z = (valeur - moyenne_normale) / écart_type_normal
```

Un Z-score > 3.0 déclenche une alerte.

### Configuration

- **Seuil** : 3.0 (règle des 3 sigma)
- **Granularité** : un modèle par service (46 modèles)
- **Données d'entraînement** : 76 360 points normaux

### Baseline apprise (exemple — ts-auth-service)

| Métrique | Moyenne | Écart-type | Seuil d'alerte |
|----------|---------|------------|----------------|
| CPU (%) | 1.82 | 1.04 | > 4.94% |
| Mémoire (%) | 23.29 | 0.42 | > 24.55% |
| Latence P99 (s) | 0.29 | 0.36 | > 1.37s |

### Résultats

| Métrique | Valeur |
|----------|--------|
| Vrais positifs (VP) | 129 |
| Faux positifs (FP) | 0 |
| Faux négatifs (FN) | 6 |
| **Précision** | **100.0%** |
| **Rappel** | **95.6%** |
| **F1-score** | **97.7%** |

### Fenêtres manquées (6)

| Type de panne | Nombre | Raison |
|---------------|--------|--------|
| `exception` | 4 | Gérées silencieusement — pas de trace dans les métriques |
| `return` | 1 | Panne logicielle invisible dans les métriques |
| `network_delay` | 1 | Délai trop faible pour dépasser le seuil |

### Analyse

Le Z-score obtient d'excellents résultats grâce à sa simplicité et sa granularité par service. La précision parfaite (100%) confirme qu'aucune fausse alarme n'est générée. Les 6 fenêtres manquées correspondent aux pannes de type applicatif (`exception`, `return`) qui ne laissent pas de trace dans les métriques système.

---

## 3. Algorithme 2 — Isolation Forest

### Principe

L'Isolation Forest construit des arbres de décision aléatoires et mesure la facilité d'isolation de chaque point. Un point facile à isoler est considéré comme une anomalie.

- Point normal → difficile à isoler → beaucoup d'étapes → score élevé
- Point anormal → facile à isoler → peu d'étapes → score bas → **anomalie**

### Configuration

- **Contamination** : 0.05 (5% de données supposées anormales)
- **Nombre d'arbres** : 100
- **Granularité** : un modèle par service (46 modèles)
- **Normalisation** : StandardScaler par service

### Résultats

| Métrique | Valeur |
|----------|--------|
| Vrais positifs (VP) | 123 |
| Faux positifs (FP) | 0 |
| Faux négatifs (FN) | 12 |
| **Précision** | **100.0%** |
| **Rappel** | **91.1%** |
| **F1-score** | **95.3%** |

### Fenêtres manquées (12)

| Type de panne | Nombre | Raison |
|---------------|--------|--------|
| `exception` | 6 | Patterns subtils en dessous du seuil de contamination |
| `network_delay` | 3 | Anomalies progressives confondues avec des pics normaux |
| `cpu_contention` | 2 | Pics courts capturés sur un seul point de mesure |
| `return` | 1 | Invisible dans les métriques |

### Analyse

L'Isolation Forest maintient une précision parfaite mais un rappel inférieur au Z-score (91.1% vs 95.6%). Le paramètre `contamination=0.05` rend le modèle conservateur — il ne détecte que les anomalies les plus marquées. L'avantage théorique (pas d'hypothèse gaussienne, détection multi-dimensionnelle) ne se concrétise pas sur ce dataset où les anomalies génèrent des signaux très nets dans les métriques.

---

## 4. Algorithme 3 — Autoencoder

### Principe

Un Autoencoder est un réseau de neurones qui apprend à compresser puis reconstruire les données normales. Une erreur de reconstruction élevée indique une anomalie.

```
Entrée (5) → Dense(3) → Dense(2) → Dense(3) → Sortie (5)
              ReLU       ReLU       ReLU       Linéaire
             Encodeur   Goulot    Décodeur
```

### Configuration

- **Architecture** : 4 couches, 55 paramètres
- **Epochs** : 50
- **Batch size** : 256
- **Seuil** : percentile 95 de l'erreur de reconstruction normale
- **Optimizer** : Adam, loss MSE

### Limitation structurelle du dataset

Les fichiers métriques de Nezha couvrent l'intégralité de la journée et sont **identiques** entre `construct_data` et `rca_data` (MD5 identique vérifié). L'Autoencoder ne peut donc pas apprendre sur un dataset "normal pur" — il est entraîné sur des données qui contiennent déjà des pannes, ce qui dégrade ses performances.

### Résultats

| Métrique | Valeur |
|----------|--------|
| Vrais positifs (VP) | 19 |
| Faux positifs (FP) | 0 |
| Faux négatifs (FN) | 116 |
| **Précision** | **100.0%** |
| **Rappel** | **14.1%** |
| **F1-score** | **24.7%** |

### Ratio erreur reconstruction

| Phase | Erreur moyenne |
|-------|---------------|
| Normale | 0.447 |
| Anormale | 24.756 |
| **Ratio** | **55.33x** |

Malgré le faible F1, l'erreur de reconstruction est 55x plus élevée pendant les pannes — preuve que le modèle détecte bien l'anomalie en termes de signal brut, mais le seuil est mal calibré à cause de la contamination des données d'entraînement.

---

## 5. Comparaison synthétique

| Algorithme | Précision | Rappel | F1-score | VP | FP | FN |
|------------|-----------|--------|----------|----|----|----|
| **Z-score** | 100% | **95.6%** | **97.7%** | **129** | 0 | 6 |
| **Isolation Forest** | 100% | 91.1% | 95.3% | 123 | 0 | 12 |
| **Autoencoder** | 100% | 14.1% | 24.7% | 19 | 0 | 116 |

### Observations clés

1. **Précision identique (100%)** — aucun algorithme ne génère de fausse alarme sur ce dataset. Les 3 algorithmes sont très précis quand ils déclenchent une alerte.

2. **Le Z-score domine** — F1 de 97.7%, meilleur résultat malgré sa simplicité. Les métriques de Train Ticket produisent des signaux très nets (pics CPU à 100%) facilement capturables par un seuil statistique.

3. **L'Isolation Forest est compétitif** — F1 de 95.3%, légèrement inférieur. Le paramètre `contamination` mériterait une optimisation par validation croisée.

4. **L'Autoencoder est limité par le dataset** — F1 de 24.7%. La structure de Nezha (fichiers métriques identiques entre construct_data et rca_data) ne permet pas d'entraîner l'Autoencoder sur un dataset vraiment normal. Il serait plus efficace sur un dataset avec séparation franche entre phases normales et anormales.

---

## 6. Types de pannes détectables par les métriques

| Type de panne | Z-score | Isolation Forest | Autoencoder | Signal dans les métriques |
|---------------|---------|------------------|-------------|--------------------------|
| `cpu_contention` | ✓ | ✓ | Partiel | CPU x10, mémoire +50% |
| `network_delay` | Partiel | Partiel | Partiel | Latence P99 x10 |
| `exception` | Partiel | ✗ | ✗ | Faible — surtout visible dans les logs |
| `return` | ✗ | ✗ | ✗ | Invisible — détectable uniquement via les logs |

---

## 7. Conclusion et perspectives

### Conclusion

Le Z-score est l'algorithme le plus performant sur les métriques de Train Ticket avec un F1 de 97.7%. Sa simplicité, son interprétabilité et sa granularité par service en font l'approche de référence pour ce type de données.

Les pannes de type `exception` et `return` restent non détectables par les métriques — elles requièrent une analyse des logs applicatifs. Cela justifie l'approche multi-modale (logs + métriques + traces) pour une couverture complète des 4 types de pannes.

### Perspectives

1. **Détection sur les logs** — algorithmes DeepLog, LogBERT pour les pannes `exception` et `return`
2. **Détection sur les traces** — analyse des durées de spans pour les pannes `network_delay`
3. **Fusion multi-modale** — combiner les scores des 3 modalités pour améliorer le rappel global
4. **Optimisation des hyperparamètres** — ajuster `contamination` pour l'Isolation Forest et le seuil pour l'Autoencoder via validation croisée

---

*Rapport fait dans le cadre du projet de maîtrise en génie logiciel — Détection d'anomalies dans les systèmes microservices*  
*Dataset : Nezha (Yu et al., FSE 2023) — github.com/IntelligentDDS/Nezha*
