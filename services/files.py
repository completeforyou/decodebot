# services/files.py
from sqlalchemy import select, func
from database import AsyncSessionLocal
from models.file import File
from core.config import DECODE_CHANNEL_ID

async def get_file(code: str):
    async with AsyncSessionLocal() as session:
        query = select(File).filter_by(code=code)
        
        # RULE 1: Decode command ONLY works for the specific decode channel
        if DECODE_CHANNEL_ID != 0:
            query = query.filter(File.channel_id == DECODE_CHANNEL_ID)
            
        result = await session.execute(query)
        return result.scalars().first()

async def search_by_keyword(keyword: str, limit: int = 50):
    async with AsyncSessionLocal() as session:
        search_pattern = f"%{keyword}%"
        query = select(File).filter(File.caption.ilike(search_pattern))
        
        # RULE 2: Search EXCLUDES the decode channel
        if DECODE_CHANNEL_ID != 0:
            query = query.filter(File.channel_id != DECODE_CHANNEL_ID)
            
        query = query.limit(limit)
        result = await session.execute(query)
        return result.scalars().all()

async def get_random_files(limit: int = 20):
    async with AsyncSessionLocal() as session:
        query = select(File)
        
        # RULE 3: Random EXCLUDES the decode channel
        if DECODE_CHANNEL_ID != 0:
            query = query.filter(File.channel_id != DECODE_CHANNEL_ID)
            
        query = query.order_by(func.random()).limit(limit)
        
        result = await session.execute(query)
        return result.scalars().all()
    
async def insert_file(code: str, message_id: int, channel_id: int, caption: str) -> str | None:
    async with AsyncSessionLocal() as session:
        # 1. Check if this exact message already exists
        existing = await session.execute(
            select(File).filter_by(message_id=message_id, channel_id=channel_id)
        )
        if existing.scalars().first():
            return None # Skip inserting, it's already in the DB!
        
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