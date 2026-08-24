"""
Exceptions personnalisées du pipeline d'observabilité.
Permet de distinguer les différentes catégories d'erreurs :
- ConfigurationError : problème de configuration
- DataError         : donnée introuvable ou manquante (HTTP 404)
- InvalidInputError : entrée utilisateur mal formée (HTTP 400)
- ModelError        : problème avec un modèle ML
- PipelineError     : exception de base pour tout le reste
"""


class PipelineError(Exception):
    """Exception de base du pipeline. Toutes les autres en héritent."""


class ConfigurationError(PipelineError):
    """
    Erreur liée à la configuration.

    Levée quand :
    - config.yaml est introuvable
    - Une clé requise est manquante
    - Le format YAML est invalide
    """


class DataError(PipelineError):
    """
    Erreur liée aux données.

    Levée quand :
    - Un fichier de données est introuvable
    - Le format des données est invalide
    - Une colonne attendue est manquante
    """


class ModelError(PipelineError):
    """
    Erreur liée aux modèles ML.

    Levée quand :
    - Un modèle .pkl est introuvable
    - Le chargement échoue (incompatibilité de version)
    - Une prédiction échoue
    """


class InvalidInputError(PipelineError):
    """
    Erreur liée à une entrée utilisateur invalide.

    Distincte de DataError : ici, ce n'est pas la donnée qui est en cause,
    c'est l'entrée fournie par l'utilisateur qui est mal formée.

    Levée quand :
    - Le format d'un paramètre est invalide (ex : window '24_89' au lieu de HH_MM valide)
    - Une valeur enum est incorrecte (ex : source='inconnu' au lieu de 'normal'/'anomalies')

    Se traduit en HTTP 400 Bad Request côté API.
    """
