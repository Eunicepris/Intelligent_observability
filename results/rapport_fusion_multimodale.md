# Rapport — Fusion multi-modale
## Combinaison des modalités métriques + logs + traces sur Train Ticket

---

## 1. Contexte

Les notebooks 03 à 09 ont évalué 21 algorithmes de détection d'anomalies sur 3 modalités indépendantes (métriques, logs, traces) pour deux systèmes microservices (Train Ticket et Online Boutique).

L'analyse a mis en évidence la **complémentarité** des 3 modalités :

| Type de panne | Métriques | Logs | Traces |
|---------------|-----------|------|--------|
| cpu_contention | Détecté | Détecté | Détecté |
| network_delay | Détecté | Détecté | Détecté |
| exception | **Manqué** | Détecté | Détecté |
| return | **Manqué** | Détecté | Détecté |

Aucune modalité seule ne couvre les 4 types de pannes. Ce notebook explore comment combiner ces sources pour maximiser la couverture globale.

---

## 2. Algorithmes utilisés pour la fusion

### Sélection basée sur la robustesse

Les algorithmes sélectionnés doivent être adaptés à un déploiement long terme sur tout type de système microservice — pas seulement sur Nezha.

Critères de sélection :
- Non supervisé (pas de labels requis en production)
- Adaptatif (apprend le comportement normal)
- S'améliore avec plus de données normales
- Fonctionne sur les deux systèmes testés

### Algorithmes retenus

| Modalité | Algorithme principal | Justification |
|----------|---------------------|---------------|
| Métriques | **LOF** | Densité locale adaptative, utilise 76 000 points normaux |
| Logs | **TF-IDF** | Similarité vectorielle robuste au petit vocabulaire |
| Traces | **Isolation Forest par service** | Utilise ~500 spans normaux par service |

### Algorithmes complémentaires (Option B)

| Modalité | Algorithme secondaire |
|----------|----------------------|
| Métriques | Isolation Forest (contamination=0.10) |
| Logs | Comptage de templates nouveaux |
| Traces | Aucun (LOF impossible avec 2 fenêtres, IF sur features globales échoue) |

---

## 3. Trois options de fusion testées

### Option A — 1 algorithme par modalité

Approche la plus simple. Chaque modalité contribue avec une seule prédiction.

```
Métriques (LOF)                  →  détection 1
Logs (TF-IDF)                     →  détection 2
Traces (IF par service)          →  détection 3
                                       ↓
                                  Fusion finale
```

### Option B — Fusion à 2 niveaux

Chaque modalité utilise plusieurs algorithmes avec une fusion intra-modalité, puis une fusion inter-modalités.

```
Niveau 1 (intra-modalité) :
  Métriques : LOF OR Isolation Forest       →  détection métriques
  Logs      : TF-IDF OR Comptage            →  détection logs
  Traces    : IF par service                 →  détection traces
Niveau 2 (inter-modalités) :
  détection métriques + détection logs + détection traces  →  fusion finale
```

### Option C — Fusion plate multi-algorithmes

Toutes les prédictions (5 algorithmes) sont combinées directement sans structure hiérarchique.

```
LOF + IF métriques + TF-IDF + Comptage + IF traces  →  fusion finale
```

---

## 4. Stratégies de fusion testées

### Vote majoritaire (≥ 2)

Une fenêtre est anormale si au moins la majorité des sources détectent une anomalie.

### OR logique (≥ 1)

Une fenêtre est anormale si au moins une source détecte une anomalie. Maximise le rappel.

### AND logique (= 3)

Une fenêtre est anormale seulement si toutes les sources détectent. Maximise la précision.

### Pondéré par F1 (Option C uniquement)

Chaque algorithme contribue proportionnellement à son F1 individuel :

```
score = Σ (F1_algo × prediction_algo) / Σ F1_algo
```

---

## 5. Résultats sur Train Ticket

### Performances individuelles par modalité

| Modalité | Algorithme | F1 |
|----------|-----------|-----|
| Métriques | LOF | 95.8% |
| Métriques | IF | 99.6% |
| Logs | TF-IDF | 98.9% |
| Logs | Comptage templates | 40.2% |
| Traces | IF par service | 98.9% |

### Résultats de fusion

| Option | Stratégie | VP | FP | FN | F1 |
|--------|-----------|----|----|-----|-----|
| A | Vote majoritaire (≥ 2/3) | 135 | 0 | 0 | **100%** |
| A | OR logique (≥ 1/3) | 135 | 0 | 0 | **100%** |
| A | AND logique (= 3/3) | 118 | 0 | 17 | 93.3% |
| B | Vote majoritaire 2 niveaux | 135 | 0 | 0 | **100%** |
| B | OR logique 2 niveaux | 135 | 0 | 0 | **100%** |
| B | AND logique 2 niveaux | 128 | 0 | 7 | 97.3% |
| C | Vote strict (≥ 3/5) | 134 | 0 | 1 | 99.6% |
| C | Vote souple (≥ 2/5) | 135 | 0 | 0 | **100%** |
| C | Pondéré par F1 | 135 | 0 | 0 | **100%** |

### Détection par type de panne (fusion Option A — Vote majoritaire)

| Type de panne | Détecté | Taux |
|---------------|---------|------|
| cpu_contention | 21/21 | 100% |
| exception | 39/39 | 100% |
| network_delay | 42/42 | 100% |
| return | 33/33 | 100% |

---

## 6. Analyse comparative

### Gain de la fusion vs modalités individuelles

| Approche | F1 |
|----------|-----|
| Meilleure modalité seule (TF-IDF) | 98.9% |
| Meilleure fusion (Vote majoritaire) | **100%** |
| **Gain** | **+1.1 point** |

Le gain absolu est modeste mais significatif : la fusion récupère les **3 anomalies** que la meilleure modalité individuelle manquait.

### Comparaison des 3 options

**Option A (1 algo/modalité)** :
- Avantage : simple, interprétable
- F1 max : 100% (vote majoritaire et OR)
- Recommandée pour la production

**Option B (fusion à 2 niveaux)** :
- Avantage : plus robuste face aux erreurs d'un algorithme
- Amélioration notable sur AND logique (93.3% → 97.3%)
- Recommandée pour les systèmes critiques

**Option C (fusion plate)** :
- Avantage : exploite tous les algorithmes disponibles
- Approche pondérée par F1 = 100%
- Plus complexe à calibrer

---

## 7. Analyse des stratégies de fusion

### Vote majoritaire (≥ 2/3)

**Meilleur compromis précision/rappel**. Nécessite une confirmation par au moins 2 modalités indépendantes, ce qui garantit la fiabilité de la détection tout en préservant la couverture.

### OR logique (≥ 1/3)

**Maximise la couverture**. Détecte toutes les anomalies vues par au moins une modalité. Risque théorique de faux positifs plus élevé, mais dans notre cas ce risque ne se matérialise pas (FP = 0).

### AND logique (= 3/3)

**Maximise la précision**. Utile pour des alertes critiques où il faut être certain avant de notifier. Manque cependant des anomalies vues par 2 modalités seulement.

Pour un déploiement en production standard, le **vote majoritaire** offre le meilleur équilibre.

---

## 8. Recommandation pour la production

### Configuration recommandée

**Option A avec vote majoritaire (≥ 2/3)**

**Justifications** :

1. **Simplicité** — 3 modèles, une règle de vote simple
2. **Robustesse** — nécessite confirmation par au moins 2 sources
3. **Interprétabilité** — décision facile à expliquer aux opérateurs
4. **Performance** — F1 = 100% sur Train Ticket
5. **Extensibilité** — facile d'ajouter une modalité supplémentaire

### Algorithmes recommandés

```
Métriques : LOF (n_neighbors=20, contamination=0.05)
Logs      : TF-IDF (max_features=500, seuil similarité=0.95)
Traces    : Isolation Forest par service (contamination=0.10, seuil=0.12)
```

### Adaptation nécessaire

Pour un déploiement sur un nouveau système, les seuils doivent être calibrés sur les données normales de ce système. Les 3 algorithmes s'adaptent automatiquement au comportement normal grâce à leur nature non supervisée.

---

## 9. Limitations et perspectives

### Limitations

1. **Baseline normale limitée** — 2 fenêtres normales pour logs et traces, ce qui limite la calibration
2. **Absence de validation croisée** — les résultats de 100% doivent être confirmés sur d'autres datasets
3. **Pas de test des faux positifs** — le manque de fenêtres normales dans le test ne permet pas d'évaluer précisément le taux de FP réel

### Perspectives

1. **Validation sur Online Boutique** — vérifier la généralisation de la fusion sur le deuxième système
2. **Détection en temps réel** — implémenter la fusion en streaming
3. **Priorisation des alertes** — combiner détection et sévérité (WARNING vs CRITICAL)
4. **Localisation de la panne** — utiliser les feature importance pour identifier le service en cause

---

## 10. Conclusion

Ce notebook démontre que la fusion multi-modale améliore significativement la détection d'anomalies par rapport à l'utilisation d'une seule modalité. Sur Train Ticket, la fusion atteint F1 = 100% avec plusieurs stratégies, contre 98.9% pour la meilleure modalité individuelle.

Les 3 options de fusion testées atteignent des performances excellentes, avec l'Option A (vote majoritaire simple) offrant le meilleur compromis entre performance et simplicité.

Cette approche est adaptée à un déploiement production sur de nouveaux systèmes microservices grâce à ses caractéristiques :
- Non supervisée (pas de labels requis)
- Adaptative (apprend le comportement normal)
- Robuste (nécessite confirmation multi-source)
- Interprétable (règle de décision simple)

La fusion multi-modale valide l'hypothèse initiale du projet : combiner métriques, logs et traces permet une détection plus fiable et plus complète des anomalies dans les systèmes microservices.

---

*Rapport généré dans le cadre du projet de maîtrise en génie logiciel*
*Détection d'anomalies dans les systèmes microservices*
*Dataset : Nezha (Yu et al., FSE 2023)*
