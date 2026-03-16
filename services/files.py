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
        # TABLESAMPLE SYSTEM(5) takes a random 5% sample of the table pages
        # This is incredibly fast compared to order_by(random())
        query = select(File).with_hint(File, "TABLESAMPLE SYSTEM (5)").limit(limit)
        
        # Note: If the table is very small, TABLESAMPLE might return empty. 
        # In that case, we can fallback to the standard method.
        result = await session.execute(query)
        files = result.scalars().all()
        
        if not files:
            # Fallback for very small databases
            fallback_query = select(File).order_by(func.random()).limit(limit)
            result = await session.execute(fallback_query)
            files = result.scalars().all()
            
        return files
    
async def insert_file(code: str, message_id: int, channel_id: int, caption: str) -> str:
    async with AsyncSessionLocal() as session:
        new_file = File(
            code=code, 
            message_id=message_id, 
            channel_id=channel_id, 
            caption=caption,
            tags=[]
        )
        session.add(new_file)
        await session.commit()
        return code

async def get_file_by_origin(message_id: int, channel_id: int):
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(File).filter_by(message_id=message_id, channel_id=channel_id)
        )
        return result.scalars().first()

async def update_tags(code: str, tags: list) -> bool:
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(File).filter_by(code=code))
        file_record = result.scalars().first()
        if file_record:
            file_record.tags = tags
            await session.commit()
            return True
        return False

async def update_caption(code: str, new_caption: str) -> bool:
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(File).filter_by(code=code))
        file_record = result.scalars().first()
        if file_record:
            file_record.caption = new_caption
            await session.commit()
            return True
        return False

async def delete_file(code: str) -> bool:
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(File).filter_by(code=code))
        file_record = result.scalars().first()
        if file_record:
            await session.delete(file_record)
            await session.commit()
            return True
        return False