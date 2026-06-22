"""
app/routers/health.py
─────────────────────────────────────────────────────────────────────────────
Endpoints de santé et de métriques.

/health  → Utilisé par Docker (HEALTHCHECK), load balancers et orchestrateurs
/metrics → Scrappé par Prometheus toutes les 15s
"""
import redis.asyncio as aioredis
from fastapi import APIRouter, Depends
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import Response

from app.config import settings
from app.database import get_db

router = APIRouter(tags=["Observability"])


@router.get("/health", summary="Health Check")
async def health_check(db: AsyncSession = Depends(get_db)):
    """
    Vérifie la santé de l'application et de ses dépendances.
    Retourne 200 si tout va bien, 503 si une dépendance est down.

    Pourquoi vérifier les dépendances ?
    → Un service peut être "up" mais inutilisable si la DB est down.
    → Les orchestrateurs (K8s, ECS) utilisent ce check pour router le trafic.
    """
    checks = {"api": "healthy", "database": "unknown", "redis": "unknown"}
    is_healthy = True

    # ── Check PostgreSQL ──────────────────────────────────────────────────────
    try:
        await db.execute(text("SELECT 1"))
        checks["database"] = "healthy"
    except Exception as e:
        checks["database"] = f"unhealthy: {str(e)[:100]}"
        is_healthy = False

    # ── Check Redis ───────────────────────────────────────────────────────────
    try:
        r = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        await r.ping()
        await r.aclose()
        checks["redis"] = "healthy"
    except Exception as e:
        checks["redis"] = f"unhealthy: {str(e)[:100]}"
        is_healthy = False

    status_code = 200 if is_healthy else 503
    return Response(
        content=str({"status": "healthy" if is_healthy else "degraded", "checks": checks}),
        status_code=status_code,
        media_type="application/json",
    )


@router.get("/metrics", summary="Prometheus Metrics", include_in_schema=False)
async def metrics():
    """
    Endpoint scrappé par Prometheus.

    include_in_schema=False : on ne l'expose pas dans la doc Swagger
    (usage interne monitoring uniquement).
    CONTENT_TYPE_LATEST : format texte spécifique attendu par Prometheus.
    """
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )
