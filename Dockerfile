# Image de base Python 3.12 slim (léger)
FROM python:3.12-slim

# Métadonnées
LABEL maintainer="Eunice"
LABEL description="Plateforme de détection d'anomalies multi-modale"
LABEL version="1.0.0"

# Variables d'environnement
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# Répertoire de travail
WORKDIR /app

# Installer les dépendances système (minimales)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copier requirements.txt d'abord (pour cache Docker)
COPY requirements.txt .

# Installer les dépendances Python
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Copier le code du projet
COPY pipeline/ ./pipeline/
COPY api/ ./api/
COPY dashboard/ ./dashboard/
COPY models/ ./models/
COPY config.yaml .
COPY demo.py .

# Créer le dossier alertes (pour la persistance)
RUN mkdir -p /app/alertes && \
    touch /app/alertes/alertes.json && \
    echo '[]' > /app/alertes/alertes.json

# Ports exposés
# 8000 : API FastAPI
# 8501 : Dashboard Streamlit
EXPOSE 8000 8501

# Commande par défaut (peut être remplacée par docker-compose)
CMD ["python", "demo.py"]