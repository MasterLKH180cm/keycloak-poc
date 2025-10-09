import datetime
import logging
import time

from app.core.config import settings
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base

logger = logging.getLogger(__name__)

# Create async engine with proper connection pooling for production
keycloak_db_engine = create_async_engine(
    settings.keycloak_database_url.replace("postgresql://", "postgresql+asyncpg://"),
    echo=settings.debug,
    pool_size=20,
    max_overflow=30,
    pool_pre_ping=True,
    pool_recycle=3600,  # Recycle connections every hour
)

# Create async session maker
AsyncKeycloakLocal = async_sessionmaker(
    keycloak_db_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

Base = declarative_base()


async def get_keycloak_db():
    """Dependency for getting database session"""
    async with AsyncKeycloakLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception as e:
            await session.rollback()
            logger.error(f"Database session error: {e}")
            raise
        finally:
            await session.close()


async def init_keycloak_db():
    """Initialize database tables"""
    async with keycloak_db_engine.begin() as conn:
        # Import all models to ensure they are registered
        from app.models.user import Base

        await conn.run_sync(Base.metadata.create_all)
    logger.info("Keycloak database tables created successfully")


# Create async engine with proper connection pooling for production
session_db_engine = create_async_engine(
    settings.session_database_url.replace("postgresql://", "postgresql+asyncpg://"),
    echo=settings.debug,
    pool_size=20,
    max_overflow=30,
    pool_pre_ping=True,
    pool_recycle=3600,  # Recycle connections every hour
)

# Create async session maker
AsyncSessionLocal = async_sessionmaker(
    session_db_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

Base = declarative_base()


async def get_session_db():
    """Dependency for getting database session"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception as e:
            await session.rollback()
            logger.error(f"Database session error: {e}")
            raise
        finally:
            await session.close()


async def init_session_db():
    """Initialize database tables"""
    async with session_db_engine.begin() as conn:
        # Import all models to ensure they are registered
        from app.models.session_models import Base as SessionBase
        from app.models.user import Base

        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(SessionBase.metadata.create_all)
    logger.info("Session database tables created successfully")


class Base(Base):
    __abstract__ = True

    def __init__(self):
        self.session = AsyncSessionLocal()

    @classmethod
    def get_by_key(cls, key):
        return cls.query.get(key)

    def save(self):
        try:
            start_time = time.time()
            logger.debug("start saving to db")
            self.session.add(self)
            self.session.commit()
            processed_time = datetime.datetime.utcfromtimestamp(
                time.time() - start_time
            ).strftime("%M:%S.%f")
            logger.debug(
                "saved to db, entity: %s, processed time: %s",
                type(self).__name__,
                processed_time,
            )
        except Exception as e:
            logger.warning(e, exc_info=True)
            logger.warning("save to db failed, entity: %s", type(self).__name__)
            raise e

    def delete(self):
        self.session.delete(self)
        self.session.commit()
