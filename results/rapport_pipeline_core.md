> ⚠️ **Rapport historique — Pipeline core initial**
>
> Ce document décrit **l'état du pipeline après la construction des 4 modules initiaux** (ingestion, détection, alertes, main). Il ne reflète pas l'état actuel du projet, qui a évolué de manière significative après ce rapport.
>
> **Évolutions non couvertes dans ce rapport** :
> - Ajout du module `pipeline/classification_type.py` (Random Forest supervisé, F1=63%)
> - Ajout des modules `pipeline/exceptions.py` (hiérarchie d'exceptions) et `pipeline/logger.py` (logging centralisé)
> - Refactoring avec **injection de dépendances** au constructeur de `PipelineComplet` (pattern Facade explicite)
> - Middleware HTTP de logging dans l'API
> - Gestion des codes HTTP appropriés (400/404/500)
> - Chargement des pipelines au démarrage via `lifespan` FastAPI
> - Champ `type_panne` dans les résultats du pipeline
> - Actions spécifiques par type de panne
> - Chemin de données passé de `/home/eunice/.../data` (absolu) à `data` (relatif)
>
> **Pour l'état actuel complet du système**, consultez :
> - `rapport_plateforme_deploiement.md` — plateforme complète avec API, dashboard, Docker, CI/CD
> - `rapport_classification_type_panne.md` — composante ML ajoutée
>
> Ce rapport est conservé à des fins de traçabilité de l'évolution du projet.

---

# Rapport — Construction du pipeline core
## Plateforme de détection d'anomalies multi-modale

---

## 1. Vue d'ensemble

### 1.1 Contexte

Ce rapport documente la construction du **pipeline core** — le cœur du système de détection d'anomalies pour architectures microservices. Le pipeline transforme les études comparatives des notebooks Jupyter en un système Python modulaire, réutilisable et automatisé.

### 1.2 Objectifs atteints

- Création d'une structure de projet claire et modulaire
- Persistence de 6 modèles pré-entraînés (43 MB total)
- Développement de 4 modules Python fonctionnels et testés
- Validation end-to-end sur les 2 systèmes (Train Ticket et Online Boutique)
- Système d'alertes persistant en JSON
- Classification en 4 niveaux de sévérité

### 1.3 Résultat

Un pipeline fonctionnel qui, en une ligne de code Python, peut :

```python
pipeline = PipelineComplet('train_ticket')
resultat = pipeline.traiter_fenetre('2023-01-29', '08_43')
```

Et retourne un résultat structuré complet avec détection, classification, confiance et action recommandée.

---

## 2. Architecture du pipeline

### 2.1 Structure du projet

```
Intelligent_observability/
├── notebooks/                      (12 notebooks existants)
│   ├── 01-10 : études comparatives
│   └── 12_sauvegarde_modeles.ipynb ← NOUVEAU
│
├── pipeline/                       ← CŒUR DU SYSTÈME
│   ├── __init__.py
│   ├── ingestion.py                (chargement des données)
│   ├── detection.py                (détection + fusion + classification)
│   ├── alertes.py                  (gestion des alertes)
│   └── main.py                     (orchestration)
│
├── models/                         ← MODÈLES PERSISTANTS
│   ├── lof_tt.pkl              (11 MB - 46 services)
│   ├── lof_ob.pkl              (4.4 MB - 10 services)
│   ├── tfidf_tt.pkl            (20 KB - 355 termes)
│   ├── tfidf_ob.pkl            (1.5 KB - 15 termes)
│   ├── if_traces_tt.pkl        (21 MB - 28 services)
│   └── if_traces_ob.pkl        (7.7 MB - 10 services)
│
├── api/                            (à faire - branche suivante)
├── dashboard/                      (à faire - branche suivante)
│
├── config.yaml                     (configuration centralisée)
├── requirements.txt                (dépendances mises à jour)
└── alertes.json                    (persistence des alertes)
```

### 2.2 Flux de données du pipeline

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│             │    │             │    │             │    │             │    │             │
│  INGESTION  │───▶│  DÉTECTION  │───▶│   FUSION    │───▶│CLASSIFICAT. │───▶│   ALERTES   │
│             │    │  (3 modal.) │    │             │    │             │    │             │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
      ↓                  ↓                  ↓                  ↓                  ↓
  Fenêtre 1 min    3 booléens          Bool unique      CRITICAL/            alertes.json
                                                        WARNING/LOW/          (persistance)
                                                        NORMAL
```

Chaque étape est **encapsulée dans un module Python indépendant** et testable séparément.

---

## 3. Composante 1 — Configuration centralisée

### 3.1 Fichier `config.yaml`

Regroupement de tous les paramètres du pipeline dans un fichier YAML unique :

```yaml
data:
  base_path: /home/eunice/Bureau/Train_ticket/Intelligent_observability/data

systemes:
  train_ticket:
    dates: [2023-01-29, 2023-01-30]
  online_boutique:
    dates: [2022-08-22, 2022-08-23]

detection:
  metriques:
    n_neighbors: 20
    contamination: 0.05
  logs:
    max_features: 500
    seuil_tt: 0.95
    seuil_ob: 0.7
  traces:
    contamination: 0.10
    seuil_taux: 0.12

fusion:
  strategie: or

api:
  port: 8000
```

### 3.2 Avantages

- **Séparation code/config** : modifier un seuil ne nécessite pas de modifier le code
- **Documentation implicite** : les paramètres sont visibles au premier coup d'œil
- **Portabilité** : facile d'adapter à un nouveau système ou environnement

---

## 4. Composante 2 — Persistence des modèles

### 4.1 Notebook `12_sauvegarde_modeles.ipynb`

Notebook Jupyter dédié à l'entraînement et la sauvegarde des 6 modèles.

**Processus** :
1. Chargement des données normales (construct_data) pour chaque système
2. Entraînement des 3 algorithmes par système
3. Sauvegarde avec `pickle` dans le dossier `models/`

### 4.2 Modèles sauvegardés

| Fichier | Contenu | Taille |
|---------|---------|--------|
| `lof_tt.pkl` | LOF pour 46 services de Train Ticket | 11 MB |
| `lof_ob.pkl` | LOF pour 10 services d'Online Boutique | 4.4 MB |
| `tfidf_tt.pkl` | Vectoriseur TF-IDF + vecteur de référence TT | 20 KB |
| `tfidf_ob.pkl` | Vectoriseur TF-IDF + vecteur de référence OB | 1.5 KB |
| `if_traces_tt.pkl` | Isolation Forest pour 28 services TT | 21 MB |
| `if_traces_ob.pkl` | Isolation Forest pour 10 services OB | 7.7 MB |

**Total** : 43 MB.

### 4.3 Format de sauvegarde

Chaque fichier pickle contient un dictionnaire structuré :

```python
# LOF et IF (par service)
{
    'modeles': {service: model, ...},
    'scalers': {service: scaler, ...}
}

# TF-IDF (global)
{
    'vectorizer' : TfidfVectorizer,
    'vecteur_ref': np.array
}
```

### 4.4 Impact

- **Démarrage rapide** : le pipeline démarre en 2-3 secondes au lieu de 3-5 minutes
- **Reproductibilité** : les modèles sont figés, garantissant des résultats identiques
- **Déployabilité** : les modèles peuvent être partagés/versionnés indépendamment du code

---

## 5. Composante 3 — Module d'ingestion

### 5.1 Fichier `pipeline/ingestion.py`

Module de chargement des données depuis les fichiers Nezha structurés.

### 5.2 Classe `IngestionEngine`

**Responsabilités** :
- Charger les métriques (par date ou par fenêtre)
- Charger les logs d'une fenêtre spécifique
- Charger les traces d'une fenêtre spécifique
- Extraire les templates depuis les messages de logs

**Interface** :

```python
class IngestionEngine:
    def __init__(self, base_path)
    def charger_metriques(source, date)
    def charger_metriques_fenetre(source, date, window)
    def charger_logs(source, date, window)
    def charger_traces(source, date, window)
    def charger_fenetre_complete(source, date, window)
    
    @staticmethod
    def extraire_template(log_str)
```

### 5.3 Extraction des templates de logs

Fonction robuste qui transforme les messages bruts en templates réutilisables :

**Exemple** :
```
Message brut :
"16:43:08.363 INFO c.s.ContactsServiceImpl#34 TraceID: 5d0bbaa5c74d96842aabc39c7b39d067 
 SpanID: 235ae8f8f73e3fb3 [findContactsById][contactsRepository.findById]"

Template extrait :
"findContactsById | contactsRepository.findById"
```

**Substitutions** :
- UUID → `<UUID>`
- Chaînes hexadécimales longues → `<HEX>`
- Nombres → `<NUM>`

Cette normalisation permet à TF-IDF de reconnaître les patterns malgré la variabilité des identifiants.

### 5.4 Test de validation

```
Chargement fenêtre 08_43 de Train Ticket (anomalies)
  Métriques : 46 lignes
  Logs      : 2 435 lignes
  Traces    : 4 445 lignes
```

Le module charge les 3 modalités en environ 2 secondes.

---

## 6. Composante 4 — Module de détection

### 6.1 Fichier `pipeline/detection.py`

Module central regroupant :
- Détection par modalité (3 méthodes)
- Fusion des détections
- Classification en 4 niveaux
- Score de confiance
- Recommandation d'action

### 6.2 Classe `DetecteurAnomalies`

**Chargement automatique** : au démarrage, les 3 modèles pré-entraînés sont chargés depuis `models/`.

**Méthodes de détection** :

```python
def detecter_metriques(df_metriques):
    """Retourne True si LOF détecte au moins un point anormal."""

def detecter_logs(df_logs, service_cible=None):
    """Retourne True si TF-IDF similarité < seuil."""

def detecter_traces(df_traces):
    """Retourne True si IF taux d'anomalies > seuil."""

def detecter_toutes(fenetre_data):
    """Applique les 3 détecteurs et retourne un dict {modalité: bool}."""
```

### 6.3 Seuils configurés

Basés sur les analyses des notebooks 06-08 :

| Système | Modalité | Seuil |
|---------|----------|-------|
| Train Ticket | Logs (TF-IDF) | similarité < 0.95 |
| Online Boutique | Logs (TF-IDF) | similarité < 0.70 |
| Les deux | Traces (IF) | taux > 12% |

### 6.4 Fonctions de fusion

Trois stratégies supportées (validées dans le notebook 10) :

```python
def fusionner(detections, strategie='or'):
    if strategie == 'or':             # F1 = 100% sur TT et OB
        return any(valeurs)
    elif strategie == 'vote_majoritaire': # F1 = 100% TT, 96.9% OB
        return sum(valeurs) >= 2
    elif strategie == 'and':          # F1 = 93.3% TT, 71.8% OB
        return all(valeurs)
```

### 6.5 Classification en 4 niveaux

Enrichissement par rapport à la version binaire initiale :

| Niveau | Nombre de modalités | Signification |
|--------|-------------------|---------------|
| CRITICAL | 3/3 | Anomalie confirmée par les 3 sources |
| WARNING | 2/3 | Anomalie probable, 2 sources d'accord |
| LOW | 1/3 | Signal faible, une seule source |
| NORMAL | 0/3 | Aucune modalité ne détecte |

### 6.6 Actions recommandées

Chaque niveau est associé à une action opérationnelle :

- **CRITICAL** : Action immédiate requise — investigation prioritaire
- **WARNING** : Alerte modérée — investigation à planifier
- **LOW** : Signal faible — vérifier la modalité concernée
- **NORMAL** : Surveillance passive — aucune action requise

---

## 7. Composante 5 — Module d'alertes

### 7.1 Fichier `pipeline/alertes.py`

Système simple mais fonctionnel de persistence et consultation des alertes.

### 7.2 Classe `SystemeAlertes`

**Stockage** : fichier JSON `alertes.json` à la racine du projet.

**Format d'une alerte** :

```json
{
  "timestamp": "2026-07-28T11:53:24.123456",
  "systeme": "train_ticket",
  "fenetre": "2023-01-29 08_43",
  "severite": "WARNING",
  "confiance": 0.67,
  "modalites": {
    "metriques": true,
    "logs": false,
    "traces": true
  },
  "services_suspects": [],
  "action": "Alerte modérée — investigation à planifier"
}
```

### 7.3 Fonctionnalités

- `enregistrer(resultat)` — ajoute une nouvelle alerte
- `obtenir(limite, severite, systeme)` — consulte avec filtres
- `statistiques()` — compteurs par sévérité et système
- `effacer()` — reset complet

### 7.4 Extensibilité

En production, ce module peut être facilement remplacé par :
- Une base de données (PostgreSQL, MongoDB)
- Un système de messagerie (Kafka, RabbitMQ)
- Un service de notification (email, Slack, PagerDuty)

L'interface reste la même, seule l'implémentation change.

---

## 8. Composante 6 — Pipeline principal

### 8.1 Fichier `pipeline/main.py`

Orchestre l'ensemble du flux via la classe `PipelineComplet`.

### 8.2 Flux complet dans `traiter_fenetre()`

```python
def traiter_fenetre(self, date, window):
    # 1. Ingestion des 3 modalités
    donnees = self.ingestion.charger_fenetre_complete('anomalies', date, window)
    
    # 2. Détection multi-modale
    detections = self.detecteur.detecter_toutes(donnees)
    
    # 3. Fusion
    est_anomalie = fusionner(detections, self.strategie)
    
    # 4. Classification
    severite  = classifier(detections)
    confiance = score_confiance(detections)
    action    = obtenir_action(severite)
    
    # 5. Construire le résultat structuré
    resultat = { ... }
    
    # 6. Enregistrer l'alerte si applicable
    if severite in ['CRITICAL', 'WARNING', 'LOW']:
        self.alertes.enregistrer(resultat)
    
    return resultat
```

### 8.3 Interface unifiée

Utilisation simplifiée en 3 lignes :

```python
pipeline = PipelineComplet('train_ticket')
resultat = pipeline.traiter_fenetre('2023-01-29', '08_43')
print(resultat['severite'])  # 'WARNING'
```

### 8.4 Traitement en batch

Support du traitement de plusieurs fenêtres :

```python
fenetres = [('2023-01-29', '08_43'), ('2023-01-29', '08_44'), ...]
resultats = pipeline.traiter_batch(fenetres)
```

---

## 9. Validation end-to-end

### 9.1 Test 1 — Train Ticket, panne `return` sur ts-contacts

**Fenêtre** : 2023-01-29 08_43

**Résultat** :

```
⚠️ WARNING (67%)
Modalités :
  ✓ metriques    : Détecte
  ○ logs         : Normal
  ✓ traces       : Détecte

Action : Alerte modérée — investigation à planifier
```

**Analyse scientifique** : ce résultat est **cohérent avec les prédictions** du notebook 10 :
- LOF sur métriques confirme l'anomalie
- TF-IDF ne détecte pas — les pannes `return` ne produisent pas de messages d'erreur dans les logs Java
- IF sur traces confirme via les durées anormales

### 9.2 Test 2 — Online Boutique, panne `cpu_contention` sur frontend

**Fenêtre** : 2022-08-22 03_53

**Résultat** :

```
💡 LOW (33%)
Modalités :
  ✓ metriques    : Détecte
  ○ logs         : Normal
  ○ traces       : Normal

Action : Signal faible — vérifier la modalité concernée
```

**Analyse scientifique** : LOF détecte correctement le CPU anormal. Les logs et traces d'Online Boutique sont moins verbeux — c'est pour cela que les 2 autres modalités ne détectent pas cette fenêtre spécifique.

### 9.3 Test négatif — Fenêtre normale

**Fenêtre** : 2022-08-22 08_43 (absente du ground truth OB)

**Résultat** :

```
✓ NORMAL (0%)
Modalités :
  ○ metriques    : Normal
  ○ logs         : Normal
  ○ traces       : Normal

Action : Surveillance passive — aucune action requise
```

**Validation** : le pipeline ne génère pas de faux positif sur une fenêtre normale — comportement attendu.

### 9.4 Statistiques après tests

```
Total alertes : 5
Par sévérité  : {CRITICAL: 0, WARNING: 3, LOW: 2, NORMAL: 0}
Par système   : {train_ticket: 3, online_boutique: 2}
```

Les alertes sont correctement enregistrées dans `alertes.json`.

---

## 10. Métriques du travail réalisé

### 10.1 Fichiers créés

| Type | Fichiers | Total |
|------|----------|-------|
| Modules Python | 4 (ingestion, detection, alertes, main) | 4 |
| Modèles pickle | 6 (LOF, TF-IDF, IF × 2 systèmes) | 6 |
| Configuration | 1 (config.yaml) | 1 |
| Notebook | 1 (sauvegarde_modeles) | 1 |
| Données runtime | 1 (alertes.json) | 1 |

**Total** : 13 fichiers nouveaux.

### 10.2 Lignes de code

- `pipeline/ingestion.py` : environ 200 lignes
- `pipeline/detection.py` : environ 250 lignes
- `pipeline/alertes.py` : environ 150 lignes
- `pipeline/main.py` : environ 180 lignes

**Total pipeline** : environ 780 lignes de Python.

### 10.3 Durée totale

Environ 4h de travail intensif pour construire le pipeline core.

---

## 11. Points forts du pipeline

### 11.1 Modularité

Chaque composante est dans un module séparé, testable indépendamment. Les responsabilités sont clairement définies :

- `ingestion.py` — je charge les données
- `detection.py` — je détecte les anomalies
- `alertes.py` — je gère les alertes
- `main.py` — j'orchestre tout

### 11.2 Réutilisabilité

Les modules peuvent être importés depuis :
- Un notebook Jupyter
- Un script Python
- Une API REST
- Un dashboard
- Un test unitaire

### 11.3 Configurabilité

Grâce à `config.yaml`, adapter le pipeline à un nouveau contexte se fait sans modifier le code.

### 11.4 Extensibilité

Ajouter une nouvelle modalité (traces distribuées, métriques applicatives, événements) est simple :

1. Ajouter une méthode dans `DetecteurAnomalies`
2. Modifier `detecter_toutes()` pour l'inclure
3. Adapter `fusionner()` si nécessaire

### 11.5 Cohérence scientifique

Le pipeline reproduit **exactement** les résultats des notebooks 03-10. Les algorithmes utilisés sont ceux qui ont montré la meilleure robustesse dans les études comparatives.

---

## 12. Limitations connues

### 12.1 Localisation basique

Le pipeline actuel ne fait **pas** la localisation du service défaillant. C'est une décision assumée :
- L'exploration a montré un Top-1 = 11.9% avec les traces
- L'amélioration nécessite une analyse de graphe (article FSE 2023)
- Cela sortirait du cadre de cette phase

### 12.2 Baseline limitée

Le TF-IDF sur Online Boutique n'a que 2 fenêtres normales pour s'entraîner, résultant en un vocabulaire limité (15 termes). Ceci est une limitation du dataset Nezha, pas du pipeline.

### 12.3 Pas d'apprentissage en ligne

Les modèles sont figés après entraînement. Un système de production devrait périodiquement re-entraîner les modèles avec de nouvelles données normales pour rester à jour.

---

## 13. Prochaines étapes

### 13.1 Branche `feature/pipeline-complet` (en cours)

- [x] Pipeline core (ingestion + detection + fusion + classification + alertes)
- [ ] API FastAPI pour exposer le pipeline via HTTP
- [ ] Dashboard Streamlit pour interface visuelle
- [ ] README complet avec instructions d'utilisation
- [ ] Script de démonstration end-to-end

### 13.2 Extensions futures possibles

- **Localisation avancée** : implémentation de l'analyse de graphe (article FSE 2023)
- **Streaming** : lecture des données en temps réel via Kafka
- **Dockerisation** : conteneurisation pour déploiement
- **CI/CD** : GitHub Actions pour tests automatiques
- **Base de données** : remplacement du JSON par PostgreSQL

---

## 14. Conclusion

### 14.1 Bilan

Le pipeline core est **complet, fonctionnel et validé**. Il reproduit exactement les résultats des études comparatives (F1 = 100% en détection multi-modale avec fusion OR) et fournit une base solide pour construire une plateforme opérationnelle.

### 14.2 Valeur ajoutée

Ce travail transforme des études scientifiques en un système exploitable. La différence est fondamentale :

**Avant** : notebooks Jupyter avec du code copié-collé, modèles réentraînés à chaque exécution, pas de persistence.

**Après** : modules Python professionnels, modèles sauvegardés et rechargés instantanément, système d'alertes persistant, interface unifiée d'utilisation.

### 14.3 Contribution du travail

- **Méthodologique** : structuration modulaire d'un système ML complexe
- **Technique** : intégration de 3 algorithmes hétérogènes (LOF, TF-IDF, IF)
- **Opérationnelle** : passage d'expérimentation à système utilisable
- **Documentaire** : chaque décision est traçable et justifiée

---

## Annexe A — Interface publique du pipeline

### Utilisation simple

```python
from pipeline.main import PipelineComplet

# Initialiser
pipeline = PipelineComplet(systeme='train_ticket')

# Analyser une fenêtre
resultat = pipeline.traiter_fenetre('2023-01-29', '08_43')

# Utiliser le résultat
if resultat['severite'] == 'CRITICAL':
    print(f"Urgent : {resultat['action']}")
```

### Format du résultat

```python
{
    'systeme'  : 'train_ticket',
    'fenetre'  : '2023-01-29 08_43',
    'anomalie' : True,
    'severite' : 'WARNING',
    'confiance': 0.67,
    'modalites': {
        'metriques': True,
        'logs'     : False,
        'traces'   : True,
    },
    'action'   : 'Alerte modérée — investigation à planifier',
}
```

---

## Annexe B — Commandes utiles

### Tester le pipeline

```bash
python -m pipeline.main
```

### Tester un module isolé

```bash
python -m pipeline.ingestion   # test ingestion
python -m pipeline.detection   # test détection
python -m pipeline.alertes     # test alertes
```

### Voir les alertes

```bash
cat alertes.json | python -m json.tool
```

---

*Rapport de construction du pipeline core*
*Plateforme de détection d'anomalies multi-modale*
*Projet de maîtrise en génie logiciel*
