"""
Configuration centralisée du logging pour le pipeline.

Fournit une fonction pour configurer le logging de manière cohérente
dans tous les modules. Utilisation :

    from pipeline.logger import setup_logging
    logger = setup_logging(__name__)
    logger.info("Message")
"""
import logging
import sys
from pathlib import Path
from typing import Optional


# Format des messages de log
DEFAULT_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
DEFAULT_DATE_FORMAT = '%Y-%m-%d %H:%M:%S'


def setup_logging(
    name: str = __name__,
    level: str = 'INFO',
    log_file: Optional[str] = None,
) -> logging.Logger:
    """
    Configure et retourne un logger.
    
    Args:
        name     : nom du logger (généralement __name__ du module appelant)
        level    : niveau de log (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file : optionnel, chemin vers un fichier de log
    
    Returns:
        un logger configuré prêt à l'emploi
    
    Example:
        >>> logger = setup_logging(__name__)
        >>> logger.info("Pipeline démarré")
    """
    logger = logging.getLogger(name)
    
    # Éviter la duplication des handlers si déjà configuré
    if logger.handlers:
        return logger
    
    logger.setLevel(getattr(logging, level.upper()))
    
    # Handler pour la console
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(
        logging.Formatter(DEFAULT_FORMAT, datefmt=DEFAULT_DATE_FORMAT)
    )
    logger.addHandler(console_handler)
    
    # Handler pour fichier (optionnel)
    if log_file:
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(
            logging.Formatter(DEFAULT_FORMAT, datefmt=DEFAULT_DATE_FORMAT)
        )
        logger.addHandler(file_handler)
    
    return logger


def configure_root_logger(level: str = 'INFO') -> None:
    """
    Configure le logger racine (utile pour capturer les logs de tous les modules).
    
    À appeler une seule fois au démarrage de l'application.
    
    Args:
        level : niveau de log global
    """
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format=DEFAULT_FORMAT,
        datefmt=DEFAULT_DATE_FORMAT,
        handlers=[logging.StreamHandler(sys.stdout)],
    )