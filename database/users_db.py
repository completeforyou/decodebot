# decodebot/database/users_db.py
import asyncpg
from core.config import logger

class UsersDB:
    def __init__(self, pool):
        """Initialize with the database connection pool."""
        self.pool = pool

    async def add_or_update_user(self, user_id: int, username: str) -> bool:
        """
        Inserts a new user or updates username.
        Returns True if the user was newly created, False if they already existed.
        """
        async with self.pool.acquire() as conn:
            try:
                # xmax is a hidden system column in Postgres. If xmax is 0, it means it was an INSERT. 
                # If it's > 0, it means it triggered the UPDATE clause.
                result = await conn.fetchrow('''
                    INSERT INTO users (user_id, username) 
                    VALUES ($1, $2)
                    ON CONFLICT (user_id) DO UPDATE 
                    SET username = EXCLUDED.username
                    RETURNING (xmax = 0) AS is_new;
                ''', user_id, username)
                
                return result['is_new'] if result else False
            except Exception as e:
                logger.error(f"Error saving user {user_id}: {e}")
                return False

    async def use_search_credit(self, user_id: int) -> bool:
        """
        Deducts one search credit from a non-premium user.
        Returns True if successful, False if the user had no credits.
        """
        async with self.pool.acquire() as conn:
            result = await conn.execute(
                "UPDATE users SET search_credits = search_credits - 1 WHERE user_id = $1 AND search_credits > 0",
                user_id
            )
            # 'UPDATE 1' means 1 row was changed, so they had credits
            return result == "UPDATE 1"

    async def make_premium(self, user_id: int):
        """Upgrades a user to premium status."""
        async with self.pool.acquire() as conn:
            # We use an UPDATE statement to change the boolean to TRUE
            await conn.execute(
                "UPDATE users SET is_premium = TRUE WHERE user_id = $1",
                user_id
            )

    async def process_checkin(self, user_id: int):
        """Handles the daily check-in logic."""
        async with self.pool.acquire() as conn:
            # Check if user exists first
            user = await conn.fetchrow("SELECT user_id FROM users WHERE user_id = $1", user_id)
            if not user:
                return False, "User not found."
            
            # The query ensures we only update if 'last_checkin' is null or in the past
            updated = await conn.execute('''
                UPDATE users 
                SET last_checkin = CURRENT_DATE, 
                    search_credits = search_credits + 1 
                WHERE user_id = $1 
                  AND (last_checkin IS NULL OR last_checkin < CURRENT_DATE)
            ''', user_id)
            
            if updated == "UPDATE 1":
                return True, "Check-in successful! You earned 1 search credit."
            else:
                return False, "You have already checked in today! Come back tomorrow."

    async def process_referral(self, new_user_id: int, referrer_id: int):
        """Processes a referral and rewards the referrer."""
        async with self.pool.acquire() as conn:
            # Make sure the new user hasn't already been referred
            user = await conn.fetchrow("SELECT referred_by FROM users WHERE user_id = $1", new_user_id)
            if user and user['referred_by'] is None:
                # 1. Update the new user's referred_by column
                await conn.execute("UPDATE users SET referred_by = $1 WHERE user_id = $2", referrer_id, new_user_id)
                # 2. Reward the referrer with 5 credits
                await conn.execute("UPDATE users SET search_credits = search_credits + 5 WHERE user_id = $1", referrer_id)
                return True
            return False