# services/features.py
from sqlalchemy import select
from database import AsyncSessionLocal
from models.feature import Feature

# Optimization: A simple dictionary cache to prevent DB hits on every command
_feature_cache = {}

async def get_feature_status(name: str) -> bool:
    """Checks if a feature is active. Defaults to True if not found."""
    # 1. Check our fast memory cache first
    if name in _feature_cache:
        return _feature_cache[name]

    # 2. If not in cache, check the database
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Feature).filter_by(name=name))
        feature = result.scalars().first()
        
        if feature:
            _feature_cache[name] = feature.is_active
            return feature.is_active
            
        # If the feature isn't in the DB at all, we assume it's enabled by default
        return True

async def toggle_feature(name: str) -> bool:
    """Flips a feature's status between True and False."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Feature).filter_by(name=name))
        feature = result.scalars().first()

        if feature:
            # If it exists, flip the boolean
            feature.is_active = not feature.is_active
        else:
            # If it doesn't exist, create it and set it to False (since default is True)
            feature = Feature(name=name, is_active=False)
            session.add(feature)

        await session.commit()
        
        # Update our fast cache with the new status
        _feature_cache[name] = feature.is_active
        return feature.is_active