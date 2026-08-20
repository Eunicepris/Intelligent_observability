> ⚠️ **Rapport historique**
>
> Ce document décrit **l'état du projet au premier jour de développement du pipeline**. Il est conservé à des fins de traçabilité de l'évolution du projet.
>
> **Pour l'état actuel du système**, consultez :
> - `rapport_plateforme_deploiement.md` — description complète de la plateforme finale (pipeline, API, dashboard, Docker, CI/CD)
> - `rapport_pipeline_core.md` — détails techniques du pipeline core (partiellement obsolète également)
> - `rapport_classification_type_panne.md` — composante ML ajoutée après ce rapport

---

# Rapport — Construction du pipeline (Jour 1)
## Fondations du pipeline automatique de détection d'anomalies

---

## 1. Objectifs de la session

Transformer les notebooks Jupyter (études comparatives) en un pipeline Python modulaire réutilisable pour la détection automatique d'anomalies dans les systèmes microservices.

**Objectifs spécifiques** :
- Créer la structure du projet
- Persister les modèles entraînés
- Développer les premiers modules du pipeline
- Valider le fonctionnement end-to-end sur une fenêtre réelle

---

## 2. Travaux réalisés

### 2.1 Structure du projet

Création de la structure de dossiers pour le pipeline :

```
Intelligent_observability/
├── notebooks/               (existant — 11 notebooks)
├── pipeline/                ← NOUVEAU
│   ├── __init__.py
│   ├── ingestion.py         ← DÉVELOPPÉ
│   ├── detection.py         ← DÉVELOPPÉ
│   ├── alertes.py           (vide, à faire)
│   └── main.py              (vide, à faire)
├── models/                  ← NOUVEAU
│   └── (6 fichiers .pkl)
├── api/                     ← NOUVEAU
│   └── main.py              (vide, à faire)
├── dashboard/               ← NOUVEAU
│   └── app.py               (vide, à faire)
├── config.yaml              ← NOUVEAU
└── requirements.txt         (mis à jour)
```

### 2.2 Configuration centralisée

Création de `config.yaml` regroupant tous les paramètres du pipeline :
- Chemins des données
- Systèmes supportés (Train Ticket, Online Boutique)
- Paramètres des 3 algorithmes de détection
- Stratégie de fusion par défaut
- Configuration API

Cette approche facilite la modification des paramètres sans toucher au code.

### 2.3 Dépendances

Mise à jour du `requirements.txt` pour inclure les bibliothèques nécessaires au pipeline :
- FastAPI et uvicorn (API REST)
- Streamlit et Plotly (dashboard)
- Pydantic (validation des données)
- PyYAML (configuration)

Installation réalisée avec `pip install -r requirements.txt`.

### 2.4 Sauvegarde des modèles entraînés

Création du notebook `notebooks/12_sauvegarde_modeles.ipynb` qui entraîne et sauvegarde 6 modèles :

| Modèle | Système | Fichier | Taille |
|--------|---------|---------|--------|
| LOF (46 services) | Train Ticket | `lof_tt.pkl` | 11 MB |
| LOF (10 services) | Online Boutique | `lof_ob.pkl` | 4.4 MB |
| TF-IDF (355 termes) | Train Ticket | `tfidf_tt.pkl` | 20 KB |
| TF-IDF (15 termes) | Online Boutique | `tfidf_ob.pkl` | 1.5 KB |
| IF par service (28) | Train Ticket | `if_traces_tt.pkl` | 21 MB |
| IF par service (10) | Online Boutique | `if_traces_ob.pkl` | 7.7 MB |

**Total** : 43 MB de modèles pré-entraînés prêts à être chargés instantanément.

**Impact** : plus besoin de réentraîner les modèles à chaque exécution — le pipeline peut démarrer en quelques secondes au lieu de plusieurs minutes.

**Note (évolution ultérieure)** : un 7ème modèle a été ajouté par la suite — `classifier_type_panne.pkl` (Random Forest supervisé pour la classification du type de panne). Voir `rapport_classification_type_panne.md`.

### 2.5 Module d'ingestion (`pipeline/ingestion.py`)

Développement de la classe `IngestionEngine` avec :

**Méthodes principales** :
- `charger_metriques(source, date)` — toutes les métriques d'une date
- `charger_metriques_fenetre(source, date, window)` — filtré sur une fenêtre 1 min
- `charger_logs(source, date, window)` — logs d'une fenêtre avec extraction de templates
- `charger_traces(source, date, window)` — traces d'une fenêtre avec durée en ms
- `charger_fenetre_complete(source, date, window)` — les 3 modalités d'un coup

**Méthode statique** :
- `extraire_template(log_str)` — extraction de template avec remplacement UUID/HEX/NUM

**Test réalisé** :
```
Chargement fenêtre 08_43 de Train Ticket (anomalies)
  Métriques : 46 lignes
  Logs      : 2 435 lignes
  Traces    : 4 445 lignes
```

Le module fonctionne correctement et charge les 3 modalités en quelques secondes.

### 2.6 Module de détection (`pipeline/detection.py`)

Développement de la classe `DetecteurAnomalies` avec :

**Chargement automatique** : les 3 modèles sont chargés depuis `models/` au démarrage.

**Méthodes de détection** :
- `detecter_metriques(df)` — applique LOF par service, retourne True si un point anormal
- `detecter_logs(df, service_cible=None)` — calcule la similarité TF-IDF vs baseline
- `detecter_traces(df)` — applique IF par service et calcule le taux d'anomalies
- `detecter_toutes(fenetre_data)` — applique les 3 détecteurs en une fois

**Fonctions annexes** :
- `fusionner(detections, strategie)` — 3 stratégies : `or`, `vote_majoritaire`, `and`
- `classifier(detections)` — classification en CRITICAL / WARNING / NORMAL
- `score_confiance(detections)` — score entre 0 et 1
- `obtenir_action(severite)` — action recommandée

---

## 3. Validation end-to-end

### 3.1 Test réalisé

Détection sur la fenêtre 08_43 de Train Ticket (2023-01-29) qui contient une panne de type `return` sur le service `ts-contacts-service`.

### 3.2 Résultats du pipeline

```
Détections par modalité :
  Métriques  : True   (LOF détecte)
  Logs       : False  (TF-IDF ne détecte pas)
  Traces     : True   (IF détecte)

Fusion OR      : True  → anomalie détectée
Classification : WARNING (2 modalités sur 3 confirment)
Confiance      : 67%
Action recommandée : Alerte modérée — investigation à planifier
```

### 3.3 Interprétation

Le pipeline détecte correctement l'anomalie. Le résultat est **cohérent avec l'analyse scientifique** effectuée précédemment :

- **Métriques (LOF)** confirme l'anomalie — les mesures montrent une déviation
- **Logs (TF-IDF)** ne confirme pas — cohérent avec la nature de la panne `return` qui ne génère pas de messages d'erreur (les logs restent en INFO)
- **Traces (IF)** confirme l'anomalie — les durées des spans sont impactées

La classification `WARNING` (2 modalités sur 3) reflète correctement la difficulté de détection de ce type de panne.

---

## 4. Bilan

### 4.1 Ce qui a été accompli

| Composante | Statut |
|------------|--------|
| Structure du projet | ✓ |
| Configuration centralisée | ✓ |
| Dépendances installées | ✓ |
| 6 modèles sauvegardés | ✓ |
| Module ingestion | ✓ testé |
| Module détection | ✓ testé |
| Test end-to-end | ✓ réussi |

### 4.2 Ce qui reste à faire (à la date de ce rapport)

**Modules Python** :
- `pipeline/alertes.py` — système d'alertes JSON
- `pipeline/main.py` — orchestration complète du pipeline

**Interfaces** :
- `api/main.py` — API FastAPI
- `dashboard/app.py` — dashboard Streamlit

**Documentation** :
- README complet
- Script de démonstration
- Tests unitaires (optionnel)

**Note (évolution ultérieure)** : tous ces éléments ont été réalisés après ce jour 1. Le projet a également été enrichi de :
- Module `classification_type.py` (classification supervisée du type de panne)
- Refactoring complet avec injection de dépendances, hiérarchie d'exceptions et logging centralisé
- Conteneurisation Docker (Dockerfile + docker-compose)
- Pipeline CI/CD GitHub Actions (5 jobs)
- 27 tests automatisés (unitaires + intégration)

### 4.3 Prochaines étapes prioritaires

1. **Module `alertes.py`** — enregistrement des détections dans un fichier JSON
2. **Module `main.py`** — classe `PipelineComplet` orchestrant toutes les étapes
3. **API FastAPI** — endpoints POST /api/detecter et GET /api/alertes
4. **Dashboard Streamlit** — interface visuelle
5. **README** — documentation d'utilisation

---

## 5. Contributions

### 5.1 Réutilisation du travail existant

Le pipeline exploite directement les résultats scientifiques des notebooks 03-10 :
- Les 3 algorithmes sélectionnés sont ceux qui ont montré la meilleure robustesse
- La stratégie de fusion OR (F1 = 100% sur les 2 systèmes) est utilisée par défaut
- Les seuils ont été calibrés sur les données réelles

### 5.2 Modularité et réutilisabilité

L'architecture en modules permet :
- **Réutilisation** : les modules peuvent être importés depuis d'autres notebooks
- **Testabilité** : chaque module peut être testé indépendamment
- **Évolutivité** : ajout facile de nouvelles modalités ou algorithmes
- **Déployabilité** : le pipeline peut être conteneurisé et déployé

### 5.3 Séparation du code et des paramètres

Grâce au fichier `config.yaml`, les paramètres du pipeline (chemins, seuils, stratégie) sont séparés du code. Un opérateur peut ajuster le comportement du système sans modifier le code Python.

---

## 6. Métriques de la session

- **Durée** : environ 2h30
- **Fichiers créés** : 8 (config, notebook 12, 2 modules Python, 6 fichiers .pkl)
- **Lignes de code** : environ 400 lignes Python
- **Modèles sauvegardés** : 6 (43 MB au total)
- **Test end-to-end** : réussi

---

## 7. Conclusion

La session a permis de poser des fondations solides pour le pipeline automatique. Les 2 modules développés (`ingestion.py` et `detection.py`) sont fonctionnels, testés, et reproduisent exactement les résultats des notebooks d'analyse.

Le test end-to-end confirme que le pipeline détecte correctement les anomalies avec une classification cohérente. La détection de la fenêtre 08_43 correspond exactement à ce que l'analyse scientifique prédisait : anomalie détectée par 2 modalités sur 3, classifiée WARNING.

Les prochaines étapes consistent à compléter les modules restants (alertes, orchestration) puis à ajouter les interfaces utilisateur (API et dashboard) pour livrer une plateforme fonctionnelle.

---

*Rapport de progression — Construction du pipeline de détection d'anomalies (jour 1)*
*Projet : plateforme cloud-native d'observabilité intelligente*
