"""
app/middleware/prometheus.py
─────────────────────────────────────────────────────────────────────────────
Middleware d'instrumentation Prometheus pour FastAPI.

Métriques exposées :
  - http_requests_total        (Counter)   → nombre de requêtes par méthode/route/status
  - http_request_duration_seconds (Histogram) → latence P50/P95/P99 par endpoint
  - http_requests_in_progress  (Gauge)     → requêtes en cours (détecte les leaks)
  - http_request_exceptions_total (Counter) → erreurs non gérées

Pourquoi un middleware et pas un décorateur ?
  → Couverture automatique de TOUTES les routes sans modifier le code métier.
  → Principe Open/Closed : on ajoute des métriques sans toucher les routers.
"""
import time
from typing import Callable

from prometheus_client import Counter, Gauge, Histogram
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Match

# ── Définition des métriques ──────────────────────────────────────────────────
# Buckets en secondes adaptés à une API REST (ms → secondes)
REQUEST_LATENCY = Histogram(
    name="http_request_duration_seconds",
    documentation="Latence des requêtes HTTP en secondes",
    labelnames=["method", "endpoint", "http_status"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

REQUEST_COUNT = Counter(
    name="http_requests_total",
    documentation="Nombre total de requêtes HTTP",
    labelnames=["method", "endpoint", "http_status"],
)

REQUESTS_IN_PROGRESS = Gauge(
    name="http_requests_in_progress",
    documentation="Nombre de requêtes HTTP en cours de traitement",
    labelnames=["method", "endpoint"],
)

EXCEPTIONS_COUNT = Counter(
    name="http_request_exceptions_total",
    documentation="Nombre total d'exceptions non gérées",
    labelnames=["method", "endpoint", "exception_type"],
)


class PrometheusMiddleware(BaseHTTPMiddleware):
    """
    Intercepte chaque requête HTTP pour mesurer sa durée et incrémenter
    les compteurs appropriés.

    Pattern : on résout le template de route (ex: /tasks/{id}) pour éviter
    l'explosion de cardinalité des labels (chaque ID serait une label différente).
    """

    def __init__(self, app, app_name: str = "observa"):
        super().__init__(app)
        self.app_name = app_name
        self.kwargs = {}

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        method = request.method
        # Résolution du template de route (évite la cardinalité infinie)
        endpoint = self._get_route_template(request)

        # Skip les métriques pour l'endpoint /metrics lui-même (évite le bruit)
        if endpoint == "/metrics":
            return await call_next(request)

        REQUESTS_IN_PROGRESS.labels(method=method, endpoint=endpoint).inc()
        start_time = time.perf_counter()
        status_code = 500

        try:
            response: Response = await call_next(request)
            status_code = response.status_code
            return response
        except Exception as exc:
            EXCEPTIONS_COUNT.labels(
                method=method,
                endpoint=endpoint,
                exception_type=type(exc).__name__,
            ).inc()
            raise
        finally:
            duration = time.perf_counter() - start_time
            REQUESTS_IN_PROGRESS.labels(method=method, endpoint=endpoint).dec()
            REQUEST_LATENCY.labels(
                method=method,
                endpoint=endpoint,
                http_status=status_code,
            ).observe(duration)
            REQUEST_COUNT.labels(
                method=method,
                endpoint=endpoint,
                http_status=status_code,
            ).inc()

    @staticmethod
    def _get_route_template(request: Request) -> str:
        """
        Résout le template de la route FastAPI depuis l'objet Request.
        Ex: GET /tasks/42 → /tasks/{task_id}
        Évite l'explosion de cardinalité des labels Prometheus.
        """
        for route in request.app.routes:
            match, _ = route.matches(request.scope)
            if match == Match.FULL:
                return route.path  # type: ignore[union-attr]
        return request.url.path
