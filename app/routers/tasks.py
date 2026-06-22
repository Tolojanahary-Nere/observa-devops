"""
app/routers/tasks.py
─────────────────────────────────────────────────────────────────────────────
Router CRUD pour les tâches asynchrones.

Architecture :
  POST /tasks     → Crée la tâche en DB + envoie au worker Celery
  GET  /tasks     → Liste paginée des tâches
  GET  /tasks/{id} → Détail d'une tâche (inclut le résultat Celery)
"""
import uuid
from typing import Any

from celery.result import AsyncResult
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Task, TaskStatus
from app.workers.celery_app import celery_app
from app.workers.tasks import process_data

router = APIRouter(prefix="/tasks", tags=["Tasks"])


# ── Schémas Pydantic ──────────────────────────────────────────────────────────
class TaskCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, example="data_processing")
    payload: dict[str, Any] | None = Field(None, example={"source": "api", "records": 1000})


class TaskResponse(BaseModel):
    id: uuid.UUID
    name: str
    status: TaskStatus
    celery_task_id: str | None
    result: str | None
    error_message: str | None

    model_config = {"from_attributes": True}


class TaskListResponse(BaseModel):
    total: int
    items: list[TaskResponse]


# ── Endpoints ─────────────────────────────────────────────────────────────────
@router.post(
    "/",
    response_model=TaskResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Créer et soumettre une tâche",
)
async def create_task(
    task_in: TaskCreate,
    db: AsyncSession = Depends(get_db),
) -> Task:
    """
    Pattern Transactional Outbox simplifié :
    1. On sauvegarde la tâche en DB (état = PENDING)
    2. On envoie au worker Celery
    3. On met à jour avec le celery_task_id

    202 Accepted : la requête est acceptée mais le traitement est asynchrone.
    """
    # Création en DB
    task = Task(
        name=task_in.name,
        payload=str(task_in.payload) if task_in.payload else None,
        status=TaskStatus.PENDING,
    )
    db.add(task)
    await db.flush()  # Obtenir l'ID sans commit définitif

    # Soumission au worker Celery
    celery_result = process_data.apply_async(
        args=[task_in.name],
        kwargs={"payload": task_in.payload},
        task_id=str(uuid.uuid4()),
    )

    # Mise à jour avec l'ID Celery
    task.celery_task_id = celery_result.id
    task.status = TaskStatus.RUNNING
    await db.flush()

    return task


@router.get(
    "/",
    response_model=TaskListResponse,
    summary="Lister les tâches avec pagination",
)
async def list_tasks(
    skip: int = Query(0, ge=0, description="Décalage pour la pagination"),
    limit: int = Query(20, ge=1, le=100, description="Nombre max de résultats"),
    status: TaskStatus | None = Query(None, description="Filtrer par statut"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    stmt = select(Task)
    if status:
        stmt = stmt.where(Task.status == status)
    stmt = stmt.offset(skip).limit(limit).order_by(Task.created_at.desc())

    result = await db.execute(stmt)
    tasks = result.scalars().all()

    # Count total
    count_stmt = select(Task)
    if status:
        count_stmt = count_stmt.where(Task.status == status)
    count_result = await db.execute(count_stmt)
    total = len(count_result.scalars().all())

    return {"total": total, "items": tasks}


@router.get(
    "/{task_id}",
    response_model=TaskResponse,
    summary="Récupérer le détail d'une tâche",
)
async def get_task(
    task_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> Task:
    """
    Récupère la tâche depuis la DB et synchronise le statut Celery.
    Permet d'avoir un état toujours à jour même si le callback Celery
    n'a pas encore mis à jour la DB.
    """
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()

    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tâche {task_id} introuvable",
        )

    # Sync avec l'état Celery si tâche en cours
    if task.celery_task_id and task.status == TaskStatus.RUNNING:
        celery_result = AsyncResult(task.celery_task_id, app=celery_app)
        if celery_result.ready():
            if celery_result.successful():
                task.status = TaskStatus.SUCCESS
                task.result = str(celery_result.result)
            else:
                task.status = TaskStatus.FAILURE
                task.error_message = str(celery_result.result)

    return task
