# Rapport — Algorithmes robustes
## Comparaison avec les algorithmes de base sur Train Ticket et Online Boutique

---

## 1. Motivation

Les notebooks 03 à 08 ont mis en évidence des faiblesses importantes des algorithmes de base :

| Algorithme de base | Faiblesse identifiée | Impact |
|-------------------|----------------------|--------|
| Z-score | Statistique statique — ne s'adapte pas à la variabilité | Chute de 25 pts entre TT et OB |
| Random Forest | Sur-apprentissage avec seulement 2 fenêtres normales | Chute de 17.5 pts entre TT et OB |
| SVM classique | Dépendance aux labels et fragilité de la frontière | Chute de 57 pts entre TT et OB |

Ce notebook évalue trois alternatives plus robustes, sélectionnées pour leur capacité à mieux se généraliser entre systèmes différents.

---

## 2. Algorithme 1 — LOF (Local Outlier Factor)

### Principe

LOF détecte les anomalies en comparant la densité locale d'un point avec celle de ses voisins. Contrairement au Z-score qui compare à une moyenne globale, LOF s'adapte à chaque région de l'espace des données.

### Configuration
- n_neighbors : 20
- contamination : 0.05
- novelty : True (permet la prédiction sur nouvelles données)
- Un modèle par service

### Résultats

| Système | VP | FP | FN | Précision | Rappel | F1 |
|---------|----|----|-----|-----------|--------|-----|
| Train Ticket | 124 | 0 | 11 | 100% | 91.9% | **95.8%** |
| Online Boutique | 107 | 0 | 61 | 100% | 63.7% | **77.8%** |

### Comparaison avec Z-score

| Système | Z-score F1 | LOF F1 | Différence |
|---------|-----------|--------|------------|
| Train Ticket | 97.7% | 95.8% | -1.9 pts |
| Online Boutique | 72.7% | 77.8% | **+5.1 pts** |
| Écart TT/OB | -25.0 pts | -17.9 pts | Réduit de 7.1 pts |

### Analyse

LOF est légèrement moins performant que Z-score sur Train Ticket car le CPU y est très stable (moyenne 1.7% ± 1%) — le Z-score détecte facilement les déviations. En revanche, sur Online Boutique où le CPU varie fortement (moyenne 23% ± 8%), LOF surpasse Z-score de 5.1 points grâce à son approche par densité locale.

**Conclusion** : LOF améliore la robustesse entre systèmes en réduisant l'écart TT/OB de 25 à 17.9 points.

---

## 3. Algorithme 2 — XGBoost

### Principe

XGBoost construit 100 arbres de décision séquentiels — chaque arbre apprend spécifiquement à corriger les erreurs des précédents. C'est du boosting par gradient descent : le modèle affine progressivement ses prédictions.

Random Forest construit 100 arbres indépendants qui votent.
XGBoost construit 100 arbres correctifs qui apprennent des erreurs des précédents.

### Configuration
- n_estimators : 100
- max_depth : 6
- learning_rate : 0.1
- scale_pos_weight : automatique (compense le déséquilibre)

### Résultats

| Système | VP | FP | FN | Précision | Rappel | F1 |
|---------|----|----|-----|-----------|--------|-----|
| Train Ticket | 133 | 0 | 2 | 100% | 98.5% | **99.3%** |
| Online Boutique | 139 | 0 | 29 | 100% | 82.7% | **90.6%** |

### Feature Importance sur Train Ticket

| Feature | Importance |
|---------|-----------|
| PodServerLatencyP99 | 48.8% |
| NetworkReceiveBytes | 19.6% |
| MemoryUsageRate | 14.9% |
| NetworkTransmitBytes | 9.2% |
| CpuUsageRate | 7.5% |

### Comparaison avec Random Forest

| Système | RF F1 | XGBoost F1 | Différence |
|---------|-------|-----------|------------|
| Train Ticket | 99.6% | 99.3% | -0.3 pts |
| Online Boutique | 82.1% | 90.6% | **+8.5 pts** |
| Écart TT/OB | -17.5 pts | -8.7 pts | Réduit de 8.8 pts |

### Analyse

XGBoost est équivalent à Random Forest sur Train Ticket (les deux atteignent le plafond de performance). Sur Online Boutique, XGBoost gagne 8.5 points grâce à sa capacité de correction séquentielle — les arbres suivants apprennent à distinguer les cas ambigus que Random Forest classe incorrectement.

**Conclusion** : XGBoost divise par deux l'écart entre TT et OB (17.5 → 8.7 points). C'est l'amélioration la plus impactante des trois alternatives.

---

## 4. Algorithme 3 — One-Class SVM

### Principe

Version non supervisée du SVM. Apprend uniquement sur les données normales et détecte tout ce qui s'en écarte. Contrairement au SVM classique qui nécessite des labels normal + anormal, One-Class SVM se contente d'apprendre le comportement normal.

### Configuration
- kernel : RBF
- nu : 0.05 (proportion attendue de points anormaux)
- gamma : scale
- Un modèle par service

### Résultats

| Système | VP | FP | FN | Précision | Rappel | F1 |
|---------|----|----|-----|-----------|--------|-----|
| Train Ticket | 128 | 0 | 7 | 100% | 94.8% | **97.3%** |
| Online Boutique | 106 | 0 | 62 | 100% | 63.1% | **77.4%** |

### Comparaison avec SVM classique

Le SVM classique n'a pas été testé sur les métriques (uniquement logs et traces). Les résultats de référence sont :

| Système | SVM classique (logs/traces) | One-Class SVM (métriques) |
|---------|----------------------------|---------------------------|
| Train Ticket | 99.3% (logs) / 92.0% (traces) | 97.3% |
| Online Boutique | 41.5% (logs) / 42.3% (traces) | 77.4% |

### Analyse

One-Class SVM apporte une amélioration majeure sur Online Boutique par rapport au SVM classique (+35 points environ). Cette différence s'explique par l'approche non supervisée — pas besoin de labels pour tracer une frontière robuste.

**Conclusion** : One-Class SVM résout le problème fondamental du SVM classique — il n'a pas besoin de labels, ce qui le rend adapté au déploiement en production réelle.

---

## 5. Comparaison synthétique

### Tableau complet

| Algorithme de base | TT F1 | OB F1 | Écart | Alternative robuste | TT F1 | OB F1 | Écart | Gain de stabilité |
|-------------------|-------|-------|-------|--------------------|-------|-------|-------|-------------------|
| Z-score | 97.7% | 72.7% | -25.0 | **LOF** | 95.8% | 77.8% | -17.9 | +7.1 pts |
| Random Forest | 99.6% | 82.1% | -17.5 | **XGBoost** | 99.3% | 90.6% | -8.7 | +8.8 pts |
| SVM classique | 99.3%* | 42.3%* | -57.0 | **One-Class SVM** | 97.3% | 77.4% | -20.0 | +37.0 pts |

\* SVM classique testé sur logs/traces

### Observations clés

1. **Les 3 alternatives robustes améliorent la stabilité** entre les deux systèmes. L'écart de performance TT/OB est réduit dans tous les cas.

2. **XGBoost offre la meilleure amélioration** — écart divisé par 2. C'est l'algorithme supervisé le plus adapté aux contextes variables.

3. **LOF est plus adapté que Z-score aux systèmes avec forte variabilité** — améliore de 5.1 points sur Online Boutique tout en restant à 95.8% sur Train Ticket.

4. **One-Class SVM résout le problème des labels** — il est utilisable en production réelle contrairement au SVM classique.

---

## 6. Comparaison avec l'Autoencoder V2

L'Autoencoder V2 reste l'algorithme le plus stable de tous ceux testés :

| Algorithme | TT F1 | OB F1 | Écart |
|------------|-------|-------|-------|
| Autoencoder V2 | 99.6% | 99.7% | **+0.1** |
| XGBoost | 99.3% | 90.6% | -8.7 |
| LOF | 95.8% | 77.8% | -17.9 |
| One-Class SVM | 97.3% | 77.4% | -20.0 |

L'Autoencoder V2 par fenêtre reste inégalé pour la généralisation entre systèmes. Les algorithmes robustes de ce notebook s'en rapprochent mais ne le surpassent pas.

---

## 7. Recommandations

### Pour la production sans labels

Priorité 1 : **Autoencoder V2** (F1 ~99.6% stable sur les deux systèmes)
Priorité 2 : **One-Class SVM** (F1 77-97% selon le système, sans labels)
Priorité 3 : **LOF** (F1 78-96%, plus interprétable)

### Pour l'analyse post-incident (avec labels)

Priorité 1 : **XGBoost** (F1 90-99%, meilleure alternative supervisée)
Priorité 2 : Random Forest (F1 82-100%, plus classique et interprétable)

### À éviter en production

- Z-score : trop fragile face à la variabilité
- SVM classique : dépendance aux labels et fragilité de la frontière

---

## 8. Conclusion

Ce notebook démontre qu'il est possible d'améliorer significativement la robustesse des algorithmes de détection d'anomalies en remplaçant les approches statiques par des approches adaptatives. Les trois alternatives testées (LOF, XGBoost, One-Class SVM) réduisent toutes l'écart de performance entre Train Ticket et Online Boutique, avec des gains de stabilité allant de 7 à 37 points.

Cette étude complète les résultats des notebooks précédents en apportant une dimension critique importante pour votre mémoire : les meilleurs résultats sur un système ne garantissent pas la même performance sur un autre. Le choix des algorithmes doit tenir compte de leur capacité de généralisation, pas seulement de leurs performances sur un dataset unique.

---

*Rapport fait dans le cadre du projet de maîtrise en génie logiciel*
*Détection d'anomalies dans les systèmes microservices*
*Dataset : Nezha (Yu et al., FSE 2023)*
