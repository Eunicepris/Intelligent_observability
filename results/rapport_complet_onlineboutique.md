# Rapport complet — Détection d'anomalies dans Online Boutique
## 14 algorithmes sur 3 modalités de données

---

## 1. Contexte

**Système** : Online Boutique — 10 microservices (Go, Python, Node.js)
**Dataset** : Nezha (Yu et al., FSE 2023)
**Dates** : 22 et 23 août 2022
**Pannes** : 56 injections → 168 fenêtres d'anomalie de 3 minutes
**Types** : cpu_consumed (10), cpu_contention (16), exception (7), network_delay (16), return (7)

**Objectif** : vérifier si les résultats obtenus sur Train Ticket se généralisent sur un second système ayant une architecture différente (Go/Python vs Java Spring Boot).

**Limitations du dataset** :
- Fichiers métriques identiques entre construct_data et rca_data (MD5 vérifié)
- Seulement 2 fenêtres normales de logs et traces disponibles
- Toutes les 168 fenêtres de rca_data sont anormales

---

## 2. Résultats par modalité

### 2.1 Métriques — 4 algorithmes

| Algorithme | Type | F1 | VP | FP | FN | Observation |
|------------|------|-----|----|----|-----|-------------|
| Autoencoder V2 | Deep Learning | **99.7%** | 168 | 1 | 0 | Stable comme sur TT (99.6%) |
| Isolation Forest | Non supervisé | 88.0% | 132 | 0 | 36 | contamination=0.10 |
| Random Forest | Supervisé | 82.1% | 117 | 0 | 51 | CPU dominant (35.7%) |
| Z-score | Non supervisé | 72.7% | 96 | 0 | 72 | Baseline CPU trop variable |

**Feature importance (Random Forest)** :
- CpuUsageRate : 35.7% (contre 9.5% sur TT — grande différence)
- PodServerLatencyP99 : 18.7%
- MemoryUsageRate : 17.3%
- NetworkReceiveBytes : 14.7%
- NetworkTransmitBytes : 13.7%

**Observation clé** : le CPU est de loin la métrique la plus discriminante pour OB, alors que le réseau et la latence dominent sur TT. Les services Go/Python d'OB sont plus gourmands en CPU que les services Java de TT.

### 2.2 Logs — 5 algorithmes

Prétraitement adapté : extraction du champ `severity` du JSON et conversion des status HTTP en niveaux (500+ → ERROR, 400+ → WARN).

Baseline : seulement **15 templates uniques** sur 2 fenêtres normales (contre 238 pour TT).

| Algorithme | Type | F1 | VP | FP | FN | Observation |
|------------|------|-----|----|----|-----|-------------|
| Random Forest | Supervisé | **100%** * | 168 | 0 | 0 | À nuancer — 2 normales |
| TF-IDF | Non supervisé | **93.3%** | 147 | 0 | 21 | Robuste malgré petit vocabulaire |
| SVM | Supervisé | 41.5% | 44 | 0 | 124 | Chute importante vs TT (99.3%) |
| Comptage templates | Statistique | 5.8% | 5 | 0 | 163 | Vocabulaire trop pauvre |
| LSTM DeepLog | Deep Learning | 0% | 0 | 0 | 168 | Inadapté avec 15 templates |

**Feature importance (Random Forest)** :
- nb_info : 46.7%
- nb_lignes : 44.2%
- nb_error : 3.2%
- nb_templates : 2.9%

**Observation clé** : contrairement à TT où `nb_nouveaux` (templates jamais vus) dominait à 30.4%, sur OB c'est le volume de logs (nb_info + nb_lignes = 90.9%) qui est discriminant. Les logs Go/Python génèrent moins de templates distincts mais leur volume varie fortement pendant les pannes.

### 2.3 Traces — 5 algorithmes

Features extraites par fenêtre : nb_spans, nb_traces, nb_services, duree_moy, duree_max, duree_p99, duree_std, spans_par_trace.

| Algorithme | Type | F1 | VP | FP | FN | Observation |
|------------|------|-----|----|----|-----|-------------|
| Random Forest | Supervisé | **100%** * | 168 | 0 | 0 | À nuancer — 2 normales |
| IF par service | Non supervisé | 99.4% | 166 | 0 | 2 | Sur spans bruts (seuil 0.12) |
| Autoencoder V2 | Deep Learning | **99.4%** | 167 | 1 | 1 | Stable comme sur TT |
| Z-score | Non supervisé | 93.0% | 146 | 0 | 22 | Baseline moins nette qu'sur TT |
| SVM | Supervisé | 42.3% | 45 | 0 | 123 | Chute similaire aux logs |

**Feature importance (Random Forest)** :
- nb_traces : 20.1%
- duree_max : 18.9%
- duree_p99 : 14.1%
- spans_par_trace : 13.7%
- nb_spans : 12.6%
- duree_moy : 10.8%
- duree_std : 9.9%

---

## 3. Comparaison Train Ticket vs Online Boutique

### 3.1 Métriques

| Algorithme | TT F1 | OB F1 | Différence |
|------------|-------|-------|------------|
| Autoencoder V2 | 99.6% | **99.7%** | +0.1 pts |
| Isolation Forest | 99.6% | 88.0% | -11.6 pts |
| Random Forest | 99.6% | 82.1% | -17.5 pts |
| Z-score | 97.7% | 72.7% | -25.0 pts |

### 3.2 Logs

| Algorithme | TT F1 | OB F1 | Différence |
|------------|-------|-------|------------|
| Random Forest | 100% | 100% | 0 pts |
| TF-IDF | 98.9% | 93.3% | -5.6 pts |
| Comptage templates | 40.2% | 5.8% | -34.4 pts |
| SVM | 99.3% | 41.5% | -57.8 pts |
| LSTM DeepLog | 98.1% | 0% | -98.1 pts |

### 3.3 Traces

| Algorithme | TT F1 | OB F1 | Différence |
|------------|-------|-------|------------|
| Random Forest | 100% | 100% | 0 pts |
| Autoencoder V2 | 99.6% | 99.4% | -0.2 pts |
| IF par service | 98.9% | 99.4% | +0.5 pts |
| Z-score | 99.3% | 93.0% | -6.3 pts |
| SVM | 92.0% | 42.3% | -49.7 pts |

---

## 4. Analyse transversale

### 4.1 Algorithmes qui se généralisent

**Autoencoder V2** est le seul algorithme qui reste stable entre les deux systèmes sur les 3 modalités :

| Modalité | TT F1 | OB F1 |
|----------|-------|-------|
| Métriques | 99.6% | 99.7% |
| Traces | 99.6% | 99.4% |

Cette stabilité s'explique par sa capacité d'apprentissage adaptatif — il apprend un profil spécifique à chaque système sans hypothèse préalable sur la distribution des données.

**TF-IDF** se généralise correctement sur les logs (98.9% → 93.3%). L'approche par similarité cosinus est robuste face à la variabilité du vocabulaire.

**Random Forest** atteint 100% dans les deux systèmes mais ce résultat est à nuancer — avec seulement 2 fenêtres normales d'entraînement, le modèle mémorise les cas normaux plutôt que d'apprendre des patterns généralisables.

### 4.2 Algorithmes qui échouent sur OB

**SVM** chute massivement sur les logs et traces d'OB (-57.8 et -49.7 pts). Explication : avec seulement 2 exemples normaux, SVM ne peut pas tracer une frontière robuste. La variabilité naturelle plus élevée d'OB rend les features anormales et normales trop proches.

**LSTM DeepLog** échoue complètement sur les logs d'OB (F1 = 0%). Avec seulement 15 templates dans le vocabulaire (contre 238 pour TT), le LSTM prédit correctement 96.5% des séquences même pendant les pannes. Les pannes ne créent pas de séquences inhabituelles.

**Comptage de templates** chute de 40.2% à 5.8%. Sans nouveaux templates apparaissant pendant les pannes, cette approche statistique simple devient inutilisable.

### 4.3 Différences structurelles entre les systèmes

**CPU** — c'est la métrique la plus importante pour OB (35.7% importance) contre 9.5% pour TT. Les services Go/Python d'OB consomment naturellement plus de CPU avec plus de variabilité (moyenne 23.3% ± 8% vs 1.7% ± 1% pour TT).

**Logs** — OB produit seulement 15 templates uniques (Go, Python, Node.js utilisent des formats JSON standardisés) contre 238 pour TT (Java Spring Boot produit des logs textuels très variés). Cette différence impacte fortement les approches basées sur le vocabulaire.

**Volume de logs** — pour OB, le volume (nb_info, nb_lignes) est plus discriminant que la diversité (nb_templates). L'inverse est vrai pour TT.

---

## 5. Limitations et biais

### 5.1 Baseline normale limitée

Comme pour Train Ticket, Online Boutique ne dispose que de 2 fenêtres normales pour les logs et traces. Cette limitation affecte :
- Les algorithmes supervisés (mémorisation possible)
- L'évaluation du taux de faux positifs
- La calibration des seuils

### 5.2 Fichiers métriques identiques

MD5 vérifié : les fichiers métriques de construct_data et rca_data sont identiques. Cette contrainte affecte principalement l'Autoencoder V1 (approche points bruts). L'Autoencoder V2 (approche par fenêtre) contourne le problème.

### 5.3 Fenêtres partiellement anormales

Chaque fenêtre de 3 minutes n'est pas uniformément anormale. La première minute d'injection n'est que partiellement affectée. Seul le service ciblé (1/10) est en panne — les 9 autres services fonctionnent normalement.

---

## 6. Conclusion

### Résultats principaux

1. **L'Autoencoder V2 est le seul algorithme véritablement généralisable** entre Train Ticket et Online Boutique. F1 stable autour de 99.5% sur les métriques et traces des deux systèmes.

2. **Le CPU est déterminant pour Online Boutique** contrairement au réseau/latence pour Train Ticket. Cette différence reflète les caractéristiques des langages (Go/Python vs Java).

3. **Le vocabulaire des logs est critique** pour les algorithmes NLP. Le LSTM DeepLog qui fonctionnait à 98.1% sur TT échoue complètement sur OB (0%) à cause du petit vocabulaire (15 templates vs 238).

4. **TF-IDF reste robuste** sur les logs des deux systèmes (98.9% → 93.3%). C'est l'algorithme recommandé pour les logs en production quand les labels ne sont pas disponibles.

5. **Le SVM est le moins robuste** — il chute de 50 à 60 points entre TT et OB. Sa dépendance à une frontière unique le rend fragile face aux variations entre systèmes.

6. **Les 3 modalités restent complémentaires** sur les deux systèmes. Aucune modalité seule ne couvre tous les types de pannes de manière fiable.

### Recommandation pour la production

Pour un déploiement en production sur un nouveau système sans labels :
- **Métriques** : Autoencoder V2 (approche par fenêtre)
- **Logs** : TF-IDF avec similarité cosinus
- **Traces** : Autoencoder V2 + Z-score multi-features

### Perspectives

1. **Fusion multi-modale** — combiner les scores des 3 modalités pour améliorer la robustesse globale
2. **Autoencoder + apprentissage adaptatif** — enrichir la baseline en production
3. **Enrichir le dataset** — collecter plus de données normales pour améliorer l'évaluation des faux positifs
4. **Validation sur un 3ème système** — vérifier si les conclusions se généralisent au-delà de deux exemples

---

*Rapport écrit dans le cadre du projet de maîtrise en génie logiciel*
*Détection d'anomalies dans les systèmes microservices*
*Dataset : Nezha (Yu et al., FSE 2023) — github.com/IntelligentDDS/Nezha*
