"""
app/database.py
─────────────────────────────────────────────────────────────────────────────
Couche d'accès à la base de données avec SQLAlchemy async.

Points clés pour l'entretien :
  - `create_async_engine` avec pool_size adapté à la charge prévisible
  - `async_sessionmaker` avec expire_on_commit=False (évite les lazy-loads
    après commit qui causeraient des DetachedInstanceError)
  - Dépendance FastAPI `get_db` utilise le pattern contextmanager pour
    garantir la fermeture de session même en cas d'exception
"""
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

# ── Engine ────────────────────────────────────────────────────────────────────
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,           # Log SQL en mode debug uniquement
    pool_size=10,                  # Connexions persistantes dans le pool
    max_overflow=20,               # Connexions temporaires supplémentaires
    pool_pre_ping=True,            # Vérifie la connexion avant usage (resilience)
    pool_recycle=3600,             # Recycle les connexions après 1h
)

# ── Session factory ───────────────────────────────────────────────────────────
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,        # Critique : évite les DetachedInstanceError
    autocommit=False,
    autoflush=False,
)


# ── Base pour les modèles SQLAlchemy ─────────────────────────────────────────
class Base(DeclarativeBase):
    pass


# ── Dépendance FastAPI ────────────────────────────────────────────────────────
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Générateur de session DB injectable via Depends(get_db).
    Le `try/finally` garantit la fermeture de session même si une exception
    est levée dans l'handler de route.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
