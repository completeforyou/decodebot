# services/channels.py
from typing import Dict, Optional
from sqlalchemy import select
from database import AsyncSessionLocal
from models.channel import ApprovedChannel
from core.config import logger

# 1. We explicitly tell the linter this will eventually be a Dictionary
_channels_cache: Optional[Dict[int, str]] = None

async def _load_cache():
    """Loads all channels from the database into memory."""
    global _channels_cache
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(ApprovedChannel))
        channels = result.scalars().all()
        _channels_cache = {c.channel_id: c.channel_name for c in channels}

async def is_approved(channel_id: int) -> bool:
    """Checks if a channel ID is in the approved list."""
    if _channels_cache is None:
        await _load_cache()
        
    # 2. We add "is not None" so the linter knows it's 100% safe to check
    return _channels_cache is not None and channel_id in _channels_cache

async def get_all_channels() -> Dict[int, str]:
    """Returns a dictionary of all approved channels."""
    if _channels_cache is None:
        await _load_cache()
        
    # 3. We provide an empty dictionary fallback for the linter
    return _channels_cache if _channels_cache is not None else {}

async def add_channel(channel_id: int, name: str) -> bool:
    """Adds a new channel to the database and cache."""
    global _channels_cache
    async with AsyncSessionLocal() as session:
        # Check if it already exists
        result = await session.execute(select(ApprovedChannel).filter_by(channel_id=channel_id))
        if result.scalars().first():
            return False 
            
        new_channel = ApprovedChannel(channel_id=channel_id, channel_name=name)
        session.add(new_channel)
        await session.commit()
        
        # Update cache safely
        if _channels_cache is not None:
            _channels_cache[channel_id] = name
        return True

async def remove_channel(channel_id: int) -> bool:
    """Removes a channel from the database and cache."""
    global _channels_cache
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(ApprovedChannel).filter_by(channel_id=channel_id))
        channel = result.scalars().first()
        
        if not channel:
            return False
            
        await session.delete(channel)
        await session.commit()
        
        # Update cache safely
        if _channels_cache is not None and channel_id in _channels_cache:
            del _channels_cache[channel_id]
        return True