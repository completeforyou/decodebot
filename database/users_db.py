# decodebot/database/users_db.py
import asyncpg
from core.config import logger

class UsersDB:
    def __init__(self, pool):
        """Initialize with the database connection pool."""
        self.pool = pool

    async def add_or_update_user(self, user_id: int, username: str):
        """
        Inserts a new user into the database or updates their username if they already exist.
        """
        async with self.pool.acquire() as conn:
            try:
                await conn.execute('''
                    INSERT INTO users (user_id, username) 
                    VALUES ($1, $2)
                    ON CONFLICT (user_id) DO UPDATE 
                    SET username = EXCLUDED.username;
                ''', user_id, username)
            except Exception as e:
                logger.error(f"Error saving user {user_id}: {e}")

    async def get_user(self, user_id: int):
        """Fetches the user's premium status and remaining credits."""
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(
                "SELECT is_premium, search_credits FROM users WHERE user_id = $1",
                user_id
            )

    async def use_search_credit(self, user_id: int):
        """Deducts one search credit from a non-premium user."""
        async with self.pool.acquire() as conn:
            await conn.execute(
                "UPDATE users SET search_credits = search_credits - 1 WHERE user_id = $1 AND search_credits > 0",
                user_id
            )

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