import asyncpg

class FilesDB:
    def __init__(self, pool):
        self.pool = pool

    async def insert_file(self, code, message_id, channel_id, tags):
        async with self.pool.acquire() as conn:
            try:
                await conn.execute(
                    "INSERT INTO files (code, message_id, channel_id, tags) VALUES ($1, $2, $3, $4)", 
                    code, message_id, channel_id, tags
                )
                return code
            except asyncpg.exceptions.UniqueViolationError:
                return await conn.fetchval('''
                    UPDATE files SET tags = $1 
                    WHERE message_id = $2 AND channel_id = $3 
                    RETURNING code
                ''', tags, message_id, channel_id)

    async def get_file(self, code):
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(
                "SELECT message_id, channel_id FROM files WHERE code = $1", 
                code
            )

    async def search_by_tag(self, tag):
        async with self.pool.acquire() as conn:
            return await conn.fetch(
                "SELECT code, message_id, channel_id FROM files WHERE $1 = ANY(tags)", 
                tag
            )