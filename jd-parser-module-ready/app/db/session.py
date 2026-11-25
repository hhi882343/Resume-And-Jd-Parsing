"""Database engine and session factory supporting SQLite and MySQL."""

from typing import AsyncGenerator, Optional

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import settings


@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    """Ensure SQLite enforces foreign key integrity constraints."""
    module_name = type(dbapi_connection).__module__
    if "sqlite" in module_name:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def create_app_async_engine(database_url: Optional[str] = None) -> AsyncEngine:
    """Create an async SQLAlchemy engine with connection pool settings."""
    url = database_url or settings.DATABASE_URL
    connect_args = {}
    if "sqlite" in url:
        connect_args["check_same_thread"] = False

    return create_async_engine(
        url,
        echo=False,
        future=True,
        connect_args=connect_args,
    )


async_engine = create_app_async_engine()

async_session_maker = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for providing transactional async database sessions."""
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


def get_sync_engine(sync_url: Optional[str] = None) -> Engine:
    """Create a synchronous SQLAlchemy engine for Alembic migrations and utility scripts."""
    url = sync_url or settings.get_sync_database_url()
    connect_args = {}
    if "sqlite" in url:
        connect_args["check_same_thread"] = False

    return create_engine(url, echo=False, future=True, connect_args=connect_args)
