# services/users.py
from sqlalchemy import select, update
from database import AsyncSessionLocal
from models.user import User
from datetime import date
from core.config import logger

# Optimization: LRU-style cache to prevent hitting the DB for every message
_known_users_cache = {}
MAX_KNOWN_USERS = 1000

async def add_or_update_user(user_id: int, username: str) -> bool:
    """Checks cache first, then DB. Returns True if user is newly created."""
    if user_id in _known_users_cache:
        return False # Already exists

    async with AsyncSessionLocal() as session:
        try:
            result = await session.execute(select(User).filter_by(user_id=user_id))
            user = result.scalars().first()
            
            if not user:
                user = User(user_id=user_id, username=username)
                session.add(user)
                await session.commit()
                _known_users_cache[user_id] = True
                return True
                
            _known_users_cache[user_id] = True
            return False
        except Exception as e:
            await session.rollback()
            logger.error(f"Error adding user {user_id}: {e}")
            return False

async def get_user(user_id: int):
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).filter_by(user_id=user_id))
        return result.scalars().first()

async def use_search_credit(user_id: int) -> bool:
    """Deducts a credit securely using row-level locking."""
    async with AsyncSessionLocal() as session:
        try:
            # with_for_update() locks the row so two rapid clicks don't bypass the credit check
            result = await session.execute(select(User).filter_by(user_id=user_id).with_for_update())
            user = result.scalars().first()
            
            if user and user.search_credits > 0:
                user.search_credits -= 1
                await session.commit()
                return True
            return False
        except Exception as e:
            await session.rollback()
            logger.error(f"Error deducting credit: {e}")
            return False

async def process_checkin(user_id: int):
    async with AsyncSessionLocal() as session:
        try:
            result = await session.execute(select(User).filter_by(user_id=user_id).with_for_update())
            user = result.scalars().first()
            
            if not user:
                return False, "User not found."
                
            today = date.today()
            if user.last_checkin is None or user.last_checkin < today:
                user.last_checkin = today
                user.search_credits += 1
                await session.commit()
                return True, "Check-in successful! You earned 1 search credit."
            
            return False, "You have already checked in today! Come back tomorrow."
        except Exception as e:
            await session.rollback()
            return False, "An error occurred during check-in."
        
async def process_referral(new_user_id: int, referrer_id: int) -> bool:
    """
    Processes a referral and rewards the referrer with 5 credits.
    Returns True if the referral was successful.
    """
    async with AsyncSessionLocal() as session:
        try:
            # 1. Lock the new user row to prevent concurrent modifications
            result_new = await session.execute(
                select(User).filter_by(user_id=new_user_id).with_for_update()
            )
            new_user = result_new.scalars().first()

            # 2. Check if they are eligible (haven't been referred before)
            if new_user and new_user.referred_by is None:
                new_user.referred_by = referrer_id
                
                # 3. Lock the referrer row to safely add credits
                result_referrer = await session.execute(
                    select(User).filter_by(user_id=referrer_id).with_for_update()
                )
                referrer = result_referrer.scalars().first()
                
                if referrer:
                    referrer.search_credits += 5
                
                await session.commit()
                return True
                
            return False
            
        except Exception as e:
            await session.rollback()
            logger.error(f"Error processing referral: {e}")
            return False