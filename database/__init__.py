import asyncpg
from .files_db import FilesDB
from .users_db import UsersDB

class Database:
    def __init__(self, db_url):
        self.db_url = db_url
        self.pool = None
        self.files = None
        self.users = None

    async def connect(self):
        """Creates a connection pool and initializes all database tables."""
        self.pool = await asyncpg.create_pool(self.db_url, min_size=1, max_size=10)
        
        # Attach our sub-modules
        self.files = FilesDB(self.pool)
        self.users = UsersDB(self.pool)

        async with self.pool.acquire() as conn:
            # 1. Existing Files Table
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS files (
                    code TEXT PRIMARY KEY, 
                    message_id INTEGER,
                    channel_id BIGINT,
                    tags TEXT[],
                    caption TEXT,
                    UNIQUE(message_id, channel_id)
                )
            ''')
            # 2. Users Table
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id BIGINT PRIMARY KEY,
                    username TEXT,
                    is_premium BOOLEAN DEFAULT FALSE,
                    trial_started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    search_credits INTEGER DEFAULT 5,
                    last_checkin DATE,
                    referred_by BIGINT REFERENCES users(user_id)
                )
            ''')
            # 3. Search Analytics Table
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS search_logs (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT REFERENCES users(user_id),
                    keyword TEXT,
                    searched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

    async def close(self):
        if self.pool:
            await self.pool.close()