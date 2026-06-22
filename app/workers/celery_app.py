"""
app/workers/celery_app.py
─────────────────────────────────────────────────────────────────────────────
Configuration du worker Celery avec Redis comme broker ET backend de résultats.

Points clés pour l'entretien :
  - task_acks_late=True : le message n'est acquitté qu'APRÈS traitement,
    garantissant qu'une tâche ne soit pas perdue si le worker crashe.
  - task_reject_on_worker_lost=True : re-queue automatique si le worker meurt.
  - result_expires : évite l'accumulation infinie de résultats dans Redis.
  - Soft/hard time limits : protection contre les tâches bloquées infiniment.
"""
from celery import Celery
from celery.utils.log import get_task_logger

from app.config import settings

logger = get_task_logger(__name__)

# ── Initialisation ────────────────────────────────────────────────────────────
celery_app = Celery(
    "observa_worker",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.workers.tasks"],
)

# ── Configuration ─────────────────────────────────────────────────────────────
celery_app.conf.update(
    # Sérialisation
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],

    # Timezone
    timezone="UTC",
    enable_utc=True,

    # Fiabilité
    task_acks_late=True,                # ACK après traitement (at-least-once)
    task_reject_on_worker_lost=True,    # Re-queue si worker crash
    worker_prefetch_multiplier=1,       # 1 tâche à la fois par worker process

    # Résultats
    result_expires=3600,               # Expire après 1h dans Redis

    # Limites temporelles
    task_soft_time_limit=300,           # SIGTERM à 5min (cleanup gracieux)
    task_time_limit=360,               # SIGKILL à 6min (protection absolue)

    # Monitoring via Flower (optionnel)
    worker_send_task_events=True,
    task_send_sent_event=True,
)
