# services/files.py
from sqlalchemy import select, update, delete, func
from database import AsyncSessionLocal
from models.file import File
from core.config import logger

async def get_file(code: str):
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(File).filter_by(code=code))
        return result.scalars().first()

async def search_by_keyword(keyword: str, limit: int = 50):
    async with AsyncSessionLocal() as session:
        search_pattern = f"%{keyword}%"
        # Uses ILIKE for case-insensitive matching
        result = await session.execute(
            select(File).filter(File.caption.ilike(search_pattern)).limit(limit)
        )
        return result.scalars().all()

async def get_random_files(limit: int = 20):
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(File).order_by(func.random()).limit(limit)
        )
        return result.scalars().all()