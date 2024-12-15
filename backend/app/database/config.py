from collections.abc import AsyncGenerator
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import AsyncAdaptedQueuePool
from app.config import get_settings
from contextlib import asynccontextmanager

settings = get_settings()

db_engine = create_async_engine(
    settings.PG_DATABASE_URL,
    poolclass=AsyncAdaptedQueuePool,
    pool_size=5,
    max_overflow=10,
    echo=True,
)

async_session_maker = sessionmaker(
    db_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

@asynccontextmanager
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception as e:
            await session.rollback()
            raise e
        finally:
            await session.close()
