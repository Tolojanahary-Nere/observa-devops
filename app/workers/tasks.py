"""
app/workers/tasks.py
─────────────────────────────────────────────────────────────────────────────
Définition des tâches Celery asynchrones.

Note : les tâches Celery sont synchrones (pas async/await) car Celery gère
son propre event loop. Pour du vrai async dans Celery, il faudrait
utiliser gevent ou eventlet comme pool — non nécessaire ici.
"""
import time
import random

from app.workers.celery_app import celery_app, logger


@celery_app.task(
    name="tasks.process_data",
    bind=True,           # Accès à self pour retry, task_id, etc.
    max_retries=3,
    default_retry_delay=30,
)
def process_data(self, task_name: str, payload: dict | None = None) -> dict:
    """
    Tâche exemple simulant un traitement de données.

    bind=True : permet d'accéder à self.request.id (ID Celery),
    self.retry() pour les retries automatiques avec backoff.
    """
    logger.info(f"[{self.request.id}] Démarrage de la tâche '{task_name}'")
    start = time.monotonic()

    try:
        # Simulation d'un traitement (remplacer par logique métier réelle)
        duration = random.uniform(0.5, 3.0)
        time.sleep(duration)

        # Simulation d'erreur aléatoire (5% de chance)
        if random.random() < 0.05:
            raise ValueError("Erreur simulée de traitement")

        result = {
            "task_name": task_name,
            "payload": payload,
            "processing_time_ms": round((time.monotonic() - start) * 1000, 2),
            "status": "completed",
        }
        logger.info(f"[{self.request.id}] Tâche '{task_name}' terminée en {duration:.2f}s")
        return result

    except ValueError as exc:
        logger.error(f"[{self.request.id}] Erreur dans '{task_name}': {exc}")
        # Retry avec backoff exponentiel
        raise self.retry(exc=exc, countdown=2 ** self.request.retries)


@celery_app.task(name="tasks.health_check")
def health_check() -> dict:
    """Tâche de santé pour vérifier que le worker est opérationnel."""
    return {"status": "healthy", "worker": "observa_worker"}
