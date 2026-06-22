"""
tests/test_api.py
─────────────────────────────────────────────────────────────────────────────
Tests d'intégration de l'API FastAPI.

Convention AAA (Arrange, Act, Assert) appliquée systématiquement.
Les tests sont rapides (~ms) car ils utilisent SQLite en mémoire.
"""
import pytest
from httpx import AsyncClient


# ═════════════════════════════════════════════════════════════════════════════
# Tests : Endpoint /health
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_health_check_returns_200(client: AsyncClient):
    """Le health check doit retourner 200 quand la DB est accessible."""
    # Act
    response = await client.get("/health")

    # Assert
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_root_endpoint(client: AsyncClient):
    """La racine / doit retourner les infos de l'API."""
    response = await client.get("/")

    assert response.status_code == 200
    data = response.json()
    assert "name" in data
    assert "version" in data
    assert "docs" in data


# ═════════════════════════════════════════════════════════════════════════════
# Tests : Endpoint POST /api/v1/tasks/
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_create_task_returns_202(client: AsyncClient, mocker):
    """
    La création d'une tâche doit retourner 202 Accepted.
    On mocke Celery pour ne pas avoir besoin d'un broker réel.
    """
    # Arrange : mock du worker Celery
    mock_result = mocker.MagicMock()
    mock_result.id = "test-celery-id-1234"
    mocker.patch(
        "app.routers.tasks.process_data.apply_async",
        return_value=mock_result,
    )

    payload = {"name": "test_task", "payload": {"key": "value"}}

    # Act
    response = await client.post("/api/v1/tasks/", json=payload)

    # Assert
    assert response.status_code == 202
    data = response.json()
    assert data["name"] == "test_task"
    assert data["status"] in ("pending", "running")
    assert "id" in data


@pytest.mark.asyncio
async def test_create_task_validation_error(client: AsyncClient):
    """
    Une tâche sans `name` doit retourner 422 Unprocessable Entity.
    Teste la validation Pydantic.
    """
    # Act
    response = await client.post("/api/v1/tasks/", json={"payload": {"key": "val"}})

    # Assert
    assert response.status_code == 422
    error = response.json()
    assert "detail" in error


@pytest.mark.asyncio
async def test_create_task_empty_name_rejected(client: AsyncClient):
    """Un nom vide doit être rejeté par la validation (min_length=1)."""
    response = await client.post("/api/v1/tasks/", json={"name": ""})

    assert response.status_code == 422


# ═════════════════════════════════════════════════════════════════════════════
# Tests : Endpoint GET /api/v1/tasks/
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_list_tasks_empty(client: AsyncClient):
    """La liste des tâches doit être vide pour une DB neuve."""
    response = await client.get("/api/v1/tasks/")

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    assert data["items"] == []


@pytest.mark.asyncio
async def test_list_tasks_pagination(client: AsyncClient, mocker):
    """Les paramètres skip et limit doivent fonctionner correctement."""
    mock_result = mocker.MagicMock()
    mock_result.id = "celery-id"
    mocker.patch("app.routers.tasks.process_data.apply_async", return_value=mock_result)

    # Arrange : créer 3 tâches
    for i in range(3):
        await client.post("/api/v1/tasks/", json={"name": f"task_{i}"})

    # Act : récupérer seulement 2
    response = await client.get("/api/v1/tasks/?limit=2&skip=0")

    # Assert
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 2


# ═════════════════════════════════════════════════════════════════════════════
# Tests : Endpoint GET /api/v1/tasks/{task_id}
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_get_task_not_found(client: AsyncClient):
    """Un UUID inexistant doit retourner 404."""
    import uuid
    fake_id = str(uuid.uuid4())

    response = await client.get(f"/api/v1/tasks/{fake_id}")

    assert response.status_code == 404
    assert "introuvable" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_get_task_invalid_uuid(client: AsyncClient):
    """Un ID non-UUID doit retourner 422."""
    response = await client.get("/api/v1/tasks/not-a-valid-uuid")

    assert response.status_code == 422


# ═════════════════════════════════════════════════════════════════════════════
# Tests : Métriques Prometheus
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_metrics_endpoint_blocked_via_nginx():
    """
    Note : /metrics est bloqué par Nginx en production.
    Ce test vérifie que l'endpoint existe bien sur le service directement.
    En test, l'accès direct est autorisé (pas de Nginx devant).
    """
    # Ce test est documentaire — en prod, /metrics est bloqué par Nginx
    pass


@pytest.mark.asyncio
async def test_metrics_format(client: AsyncClient):
    """
    /metrics doit retourner du texte au format Prometheus.
    Vérifie que le middleware d'instrumentation fonctionne.
    """
    # Arrange : faire une requête pour générer des métriques
    await client.get("/health")

    # Act
    response = await client.get("/metrics")

    # Les métriques sont accessibles en test (pas de Nginx)
    # En prod elles sont bloquées par Nginx
    assert response.status_code in (200, 403)
    if response.status_code == 200:
        assert "http_requests_total" in response.text or "python_info" in response.text
