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


## 5. Algorithme 4 — Random Forest (supervisé)

### Principe

Le Random Forest est un algorithme de classification supervisé
qui construit 100 arbres de décision différents et combine leurs votes
pour classer chaque point comme normal ou anormal.

Contrairement aux trois algorithmes précédents qui apprennent
uniquement sur les données normales, le Random Forest utilise
les labels du ground truth — il voit des exemples de normal
ET d'anormal pendant l'entraînement.

### Configuration

- **Nombre d'arbres** : 100
- **Profondeur maximale** : 10
- **Pondération des classes** : `balanced` (compense le déséquilibre)
- **Split train/test** : 70% / 30% avec stratification

### Gestion du déséquilibre

Le dataset contient 76 225 points normaux contre 135 anormaux (0.18%).
Sans correction, le modèle prédirait systématiquement "normal".
Le paramètre `class_weight='balanced'` attribue un poids de 565x
aux anomalies, garantissant qu'elles pèsent autant que les normaux
dans le vote des arbres.

### Résultats

| Métrique | Valeur |
|----------|--------|
| Vrais positifs (VP) | 134 |
| Faux positifs (FP) | 0 |
| Faux négatifs (FN) | 1 |
| **Précision** | **100.0%** |
| **Rappel** | **99.3%** |
| **F1-score** | **99.6%** |

### Feature Importance

Le Random Forest fournit un classement des métriques
les plus discriminantes pour la détection :

| Métrique | Importance | Interprétation |
|----------|-----------|---------------|
| NetworkReceiveBytes | 30.7% | Le trafic réseau est le signal le plus fort |
| PodServerLatencyP99 | 30.5% | La latence est presque aussi importante |
| NetworkTransmitBytes | 16.2% | Signal secondaire réseau |
| MemoryUsageRate | 13.2% | Signal modéré |
| CpuUsageRate | 9.5% | Le CPU est le moins discriminant |

Observation : contrairement à l'intuition, le CPU n'est pas
la métrique la plus importante. Le réseau et la latence sont
les signaux les plus discriminants, suggérant que les pannes
impactent d'abord la communication entre services
avant les ressources locales.

### Analyse

Le Random Forest obtient le meilleur F1 (99.6%) grâce à son accès
aux labels. Cependant, ce résultat doit être nuancé :
le modèle est entraîné et évalué sur les mêmes données
(prédiction sur tout le dataset après entraînement sur 70%).
En production réelle, les labels ne sont pas disponibles —
ce qui rend les algorithmes non supervisés (Z-score, Isolation Forest)
plus réalistes pour un déploiement.


## 6. Comparaison synthétique

| Algorithme | Type | Précision | Rappel | F1-score | VP | FP | FN |
|------------|------|-----------|--------|----------|----|----|----|
| **Random Forest** | Supervisé | 100% | **99.3%** | **99.6%** | **134** | 0 | 1 |
| **Z-score** | Non supervisé | 100% | 95.6% | 97.7% | 129 | 0 | 6 |
| **Isolation Forest** | Non supervisé | 100% | 91.1% | 95.3% | 123 | 0 | 12 |
| **Autoencoder** | Non supervisé | 100% | 14.1% | 24.7% | 19 | 0 | 116 |

### Observations clés

1. **Précision identique (100%)** — aucun algorithme ne génère
   de fausse alarme sur ce dataset.

2. **Random Forest domine** — F1 de 99.6% grâce à l'accès aux labels.
   Cependant, en production les labels ne sont pas disponibles.

3. **Z-score — meilleur non supervisé** — F1 de 97.7% malgré
   sa simplicité. Les signaux d'anomalie dans les métriques
   de Train Ticket sont suffisamment nets pour un seuil statistique.

4. **Le réseau et la latence sont plus discriminants que le CPU** —
   le feature importance du Random Forest révèle que
   NetworkReceiveBytes (30.7%) et PodServerLatencyP99 (30.5%)
   sont les variables les plus importantes.

5. **L'Autoencoder est limité par le dataset** — F1 de 24.7%.
   Les fichiers métriques identiques entre construct_data et rca_data
   empêchent l'Autoencoder d'apprendre un normal pur.

6. **Supervisé vs non supervisé** — en contexte académique,
   Random Forest donne les meilleurs résultats.
   En contexte de production, Z-score est recommandé
   car il ne nécessite pas de labels.


## 7. Conclusion et perspectives

### Conclusion

Le Random Forest obtient le meilleur F1 (99.6%) grâce à son accès
aux labels du ground truth. Cependant, en contexte de production réelle
où les labels ne sont pas disponibles, le Z-score (F1 = 97.7%)
est l'algorithme non supervisé le plus performant.
Sa simplicité, son interprétabilité et sa granularité par service
en font l'approche de référence pour un déploiement en production.

L'Isolation Forest (F1 = 95.3%) confirme que les approches
non supervisées multi-dimensionnelles sont compétitives,
tandis que l'Autoencoder (F1 = 24.7%) est limité par la structure
du dataset Nezha (fichiers métriques identiques entre construct_data
et rca_data).

Le feature importance du Random Forest révèle que le trafic réseau
(30.7%) et la latence P99 (30.5%) sont plus discriminants
que le CPU (9.5%) — une observation contre-intuitive mais importante
pour le choix des métriques à surveiller en production.

Les pannes de type `exception` et `return` restent non détectables
par les métriques seules — elles requièrent une analyse
des logs applicatifs. Cela justifie l'approche multi-modale
(logs + métriques + traces) pour une couverture complète
des 4 types de pannes.

### Perspectives

1. **Détection sur les logs** — algorithmes TF-IDF, DeepLog
   pour les pannes `exception` et `return`
2. **Détection sur les traces** — analyse des durées de spans
   pour les pannes `network_delay`
3. **Fusion multi-modale** — combiner les scores des 3 modalités
   pour améliorer le rappel global
4. **Optimisation des hyperparamètres** — ajuster `contamination`
   pour l'Isolation Forest et le seuil pour l'Autoencoder
   via validation croisée
5. **Validation sur Online Boutique** — appliquer les mêmes
   algorithmes sur le deuxième système pour vérifier
   la généralisation des résultats

---

*Rapport dans le cadre du projet de maîtrise en génie logiciel*
*Détection d'anomalies dans les systèmes microservices*
*Dataset : Nezha (Yu et al., FSE 2023) — github.com/IntelligentDDS/Nezha*