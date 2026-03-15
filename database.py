# database.py
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import text
from core.config import DATABASE_URL
from models.base import Base

# Import models to register them with Base
from models.user import User
from models.file import File

# Configure the Async Engine with connection pooling best practices
engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    pool_size=5,
    max_overflow=5,
    pool_pre_ping=True, # Automatically reconnect if DB connection drops
    pool_recycle=3600
)

# Global session factory
AsyncSessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False)

async def init_db():
    """Creates all tables and indexes if they don't exist."""
    async with engine.begin() as conn:
        # Create extension for fast text search
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm;"))
        # Create tables
        await conn.run_sync(Base.metadata.create_all)