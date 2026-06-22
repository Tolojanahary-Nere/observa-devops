# ─────────────────────────────────────────────────────────────────────────────
# Dockerfile — Image multi-stage pour FastAPI
# ─────────────────────────────────────────────────────────────────────────────
# Pourquoi multi-stage ?
#   Stage "builder" : installe les dépendances (inclut les outils de compilation)
#   Stage "runtime" : image finale légère sans les outils de build
#   Résultat : image ~3x plus petite, surface d'attaque réduite
# ─────────────────────────────────────────────────────────────────────────────

# ── Stage 1 : Builder ─────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

# Métadonnées OCI (bonne pratique)
LABEL org.opencontainers.image.source="https://github.com/yourusername/observa"
LABEL org.opencontainers.image.description="Observa FastAPI Application"

# Variables d'environnement pour pip
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build

# Copier uniquement requirements pour bénéficier du cache Docker
# Si requirements.txt ne change pas, cette couche est cachée
COPY requirements.txt .

# Installation dans un répertoire isolé
RUN pip install --upgrade pip \
    && pip install --prefix=/install -r requirements.txt


# ── Stage 2 : Runtime ─────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# Utilisateur non-root pour la sécurité (principe du moindre privilège)
RUN groupadd --gid 1001 appgroup \
    && useradd --uid 1001 --gid appgroup --no-create-home appuser

WORKDIR /app

# Copier les packages installés depuis le builder
COPY --from=builder /install /usr/local

# Copier le code source
COPY --chown=appuser:appgroup app/ ./app/

# Basculer vers l'utilisateur non-root
USER appuser

# Port exposé (documentation uniquement, pas une règle de firewall)
EXPOSE 8000

# Health check intégré à l'image Docker
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# Commande par défaut : uvicorn avec workers adaptés aux CPU
# --workers 1 en dev, ajuster selon les CPU en production
CMD ["uvicorn", "app.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "1", \
     "--loop", "uvloop", \
     "--log-level", "info", \
     "--access-log"]
