"""
Exceptions personnalisées du pipeline d'observabilité.

Permet de distinguer les différentes catégories d'erreurs :
- ConfigurationError : problème de configuration
- DataError         : problème de données (fichier, format)
- ModelError        : problème avec un modèle ML
- PipelineError     : exception de base pour tout le reste
"""


class PipelineError(Exception):
    """Exception de base du pipeline. Toutes les autres en héritent."""
    pass


class ConfigurationError(PipelineError):
    """
    Erreur liée à la configuration.
    
    Levée quand :
    - config.yaml est introuvable
    - Une clé requise est manquante
    - Le format YAML est invalide
    """
    pass


class DataError(PipelineError):
    """
    Erreur liée aux données.
    
    Levée quand :
    - Un fichier de données est introuvable
    - Le format des données est invalide
    - Une colonne attendue est manquante
    """
    pass


class ModelError(PipelineError):
    """
    Erreur liée aux modèles ML.
    
    Levée quand :
    - Un modèle .pkl est introuvable
    - Le chargement échoue (incompatibilité de version)
    - Une prédiction échoue
    """
    pass