"""
tests/conftest.py
─────────────────────────────────────────────────────────────────────────────
Fixtures pytest partagées pour tous les tests.

Architecture de test :
  - Base de données SQLite en mémoire (pas besoin de PostgreSQL en CI)
  - TestClient async avec httpx (compatible FastAPI async)
  - Chaque test reçoit une DB vierge (isolation totale)

Pourquoi SQLite pour les tests ?
  - Zéro infrastructure nécessaire (tourne en CI sans service PostgreSQL)
  - Limite : si on utilise des features PostgreSQL-spécifiques (UUID, JSONB),
    il faut soit un PostgreSQL de test, soit des mocks ciblés.
"""
import asyncio
from collections.abc import AsyncGenerator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app

# ── Moteur SQLite en mémoire pour les tests ───────────────────────────────────
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,          # Même connexion pour tout le test (mémoire)
)

TestSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


@pytest_asyncio.fixture(scope="session")
def event_loop():
    """Boucle asyncio partagée pour la session de test entière."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Crée les tables et fournit une session DB propre pour chaque test.
    Les tables sont recréées à chaque test → isolation totale.
    """
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with TestSessionLocal() as session:
        yield session

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture(scope="function")
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """
    Client HTTP async pour tester l'API FastAPI.
    Remplace la dépendance `get_db` par la session de test.
    """
    async def override_get_db():
        yield db_session

    # Override de la dépendance DB
    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

    # Nettoyage des overrides
    app.dependency_overrides.clear()
