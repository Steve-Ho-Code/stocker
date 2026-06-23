from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base

from .config import settings

# Adjust the database URL for asyncpg
async_db_url = settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")

engine = create_async_engine(async_db_url)

SessionLocal = async_sessionmaker(engine, expire_on_commit=False)

Base = declarative_base()
