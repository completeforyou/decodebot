# decodebot/database/files_db.py
import asyncpg

class FilesDB:
    def __init__(self, pool):
        self.pool = pool

    async def insert_file(self, code, message_id, channel_id, tags):
        async with self.pool.acquire() as conn:
            # 1. First, cleanly check if this exact message was already saved
            existing_code = await conn.fetchval(
                "SELECT code FROM files WHERE message_id = $1 AND channel_id = $2", 
                message_id, channel_id
            )
            
            # If it exists, just update the tags and return the old code
            if existing_code:
                await conn.execute("UPDATE files SET tags = $1 WHERE code = $2", tags, existing_code)
                return existing_code
                
            # 2. If it is new, insert it. (If the code collides here, it raises an error we catch in the handler)
            await conn.execute(
                "INSERT INTO files (code, message_id, channel_id, tags) VALUES ($1, $2, $3, $4)", 
                code, message_id, channel_id, tags
            )
            return code

    async def get_file(self, code):
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(
                "SELECT message_id, channel_id FROM files WHERE code = $1", 
                code
            )

    async def search_by_tag(self, tag, limit=50):
        """Optimized: Added a limit to prevent memory blowouts on large search results."""
        async with self.pool.acquire() as conn:
            return await conn.fetch(
                "SELECT code, message_id, channel_id FROM files WHERE $1 = ANY(tags) LIMIT $2", 
                tag, limit
            )
        
async def get_file_by_origin(self, message_id, channel_id):
        """Looks up a file using its original channel and message ID."""
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(
                "SELECT code, tags FROM files WHERE message_id = $1 AND channel_id = $2", 
                message_id, channel_id
            )