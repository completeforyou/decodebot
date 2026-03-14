# decodebot/database/files_db.py
import asyncpg

class FilesDB:
    def __init__(self, pool):
        self.pool = pool

    async def insert_file(self, code, message_id, channel_id, caption):
        """Inserts a new file, saving the entire caption."""
        async with self.pool.acquire() as conn:
            existing_code = await conn.fetchval(
                "SELECT code FROM files WHERE message_id = $1 AND channel_id = $2", 
                message_id, channel_id
            )
            
            if existing_code:
                await conn.execute("UPDATE files SET caption = $1 WHERE code = $2", caption, existing_code)
                return existing_code
                
            await conn.execute(
                "INSERT INTO files (code, message_id, channel_id, caption) VALUES ($1, $2, $3, $4)", 
                code, message_id, channel_id, caption
            )
            return code

    async def get_file(self, code):
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(
                "SELECT message_id, channel_id FROM files WHERE code = $1", 
                code
            )
        
    async def search_by_keyword(self, keyword, limit=50):
        """Fuzzy search using ILIKE on the caption column."""
        async with self.pool.acquire() as conn:
            # Add % around the keyword for partial matching (e.g., "%action%")
            search_pattern = f"%{keyword}%"
            return await conn.fetch(
                "SELECT code, message_id, channel_id FROM files WHERE caption ILIKE $1 LIMIT $2", 
                search_pattern, limit
            )

    async def search_by_tag(self, tag, limit=50):
        """Optimized: Added a limit to prevent memory blowouts on large search results."""
        async with self.pool.acquire() as conn:
            return await conn.fetch(
                "SELECT code, message_id, channel_id FROM files WHERE $1 = ANY(tags) LIMIT $2", 
                tag, limit
            )
        
    async def get_file_by_origin(self, message_id, channel_id):
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(
                "SELECT code, caption FROM files WHERE message_id = $1 AND channel_id = $2", 
                message_id, channel_id
            )
    
    async def update_caption(self, code: str, caption: str):
        """Updates the caption for a specific file code."""
        async with self.pool.acquire() as conn:
            result = await conn.execute(
                "UPDATE files SET caption = $1 WHERE code = $2", 
                caption, code
            )
            return result == "UPDATE 1"
        
    async def update_tags(self, code: str, tags: list):
        """Updates the tags for a specific file code."""
        async with self.pool.acquire() as conn:
            # Execute returns the command tag (e.g., 'UPDATE 1' or 'UPDATE 0')
            result = await conn.execute(
                "UPDATE files SET tags = $1 WHERE code = $2", 
                tags, code
            )
            # Return True if a row was actually updated
            return result == "UPDATE 1"

    async def delete_file(self, code: str):
        async with self.pool.acquire() as conn:
            result = await conn.execute(
                "DELETE FROM files WHERE code = $1", 
                code
            )
            return result == "DELETE 1"
    
    async def get_random_files(self, limit=20):
        """Fetches a random selection of files for the user to browse."""
        async with self.pool.acquire() as conn:
            return await conn.fetch(
                "SELECT code, message_id, channel_id FROM files ORDER BY RANDOM() LIMIT $1", 
                limit
            )