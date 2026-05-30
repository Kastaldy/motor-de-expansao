"""
db/database.py — Configuração de conexão PostgreSQL + PostGIS
Suporta sessão async (FastAPI) e sync (jobs/scripts).
"""

from collections.abc import AsyncGenerator

from api.config import settings
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session, sessionmaker

# --- Engine async (FastAPI) ---
async_engine = create_async_engine(
    settings.DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    echo=settings.ENVIRONMENT == "development",
)

AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# --- Engine sync (jobs, scripts, ML) ---
sync_engine = create_engine(
    settings.DATABASE_URL_SYNC,
    pool_size=5,
    max_overflow=10,
    echo=False,
)

SyncSessionLocal = sessionmaker(bind=sync_engine, autocommit=False, autoflush=False)


# --- Dependency FastAPI ---
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# --- Context manager sync (jobs) ---
def get_sync_db() -> Session:
    """Usar como context manager: with get_sync_db() as db: ..."""
    return SyncSessionLocal()
