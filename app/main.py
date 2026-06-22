"""
app/main.py
─────────────────────────────────────────────────────────────────────────────
Entrypoint principal de l'application FastAPI.

Architecture du démarrage :
  1. Création de l'app FastAPI avec métadonnées OpenAPI
  2. Ajout du middleware Prometheus (AVANT les routes pour tout capturer)
  3. Création des tables DB au démarrage (via lifespan)
  4. Inclusion des routers
  5. Gestionnaire d'exceptions global

Pourquoi lifespan et pas @app.on_event ?
  → on_event est déprécié depuis FastAPI 0.93.
  → lifespan est le pattern recommandé : code avant `yield` = startup,
    code après = shutdown. Permet le cleanup propre des ressources.
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.database import Base, engine
from app.middleware.prometheus import PrometheusMiddleware
from app.routers import health, tasks

# ── Logging ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ── Lifespan (startup / shutdown) ─────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Gestionnaire de cycle de vie de l'application.
    yield sépare le code de démarrage du code d'arrêt.
    """
    # ── STARTUP ───────────────────────────────────────────────────────────────
    logger.info(f"🚀 Démarrage de {settings.APP_NAME} v{settings.APP_VERSION}")

    # Création des tables si elles n'existent pas (remplacer par Alembic en prod)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("✅ Tables DB initialisées")

    yield  # ← L'application tourne ici

    # ── SHUTDOWN ──────────────────────────────────────────────────────────────
    logger.info("🛑 Arrêt propre de l'application...")
    await engine.dispose()
    logger.info("✅ Connexions DB fermées")


# ── Application FastAPI ───────────────────────────────────────────────────────
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=(
        "API asynchrone de démonstration avec observabilité complète.\n\n"
        "**Stack** : FastAPI + PostgreSQL + Redis + Celery + Prometheus"
    ),
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

# ── Middlewares ───────────────────────────────────────────────────────────────
# IMPORTANT : l'ordre des middlewares est LIFO (Last In, First Out).
# Prometheus doit être ajouté en dernier pour englober TOUTES les requêtes.

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.DEBUG else ["https://yourdomain.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if settings.METRICS_ENABLED:
    app.add_middleware(PrometheusMiddleware, app_name=settings.APP_NAME)
    logger.info("📊 Middleware Prometheus activé → /metrics")


# ── Gestionnaire d'exceptions global ─────────────────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Capture toutes les exceptions non gérées et retourne un JSON propre.
    En production, ne jamais exposer le détail de l'erreur au client.
    """
    logger.exception(f"Erreur non gérée sur {request.method} {request.url}: {exc}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "Erreur interne du serveur",
            "type": "internal_server_error",
        },
    )


# ── Routes ────────────────────────────────────────────────────────────────────
app.include_router(health.router)
app.include_router(tasks.router, prefix="/api/v1")


@app.get("/", include_in_schema=False)
async def root():
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/api/docs",
        "metrics": "/metrics",
        "health": "/health",
    }
