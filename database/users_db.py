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