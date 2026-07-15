import asyncpg
import logging
from .config import settings

logger = logging.getLogger(__name__)

# Global pool
pool = None

async def get_db_pool():
    global pool
    if not pool:
        logger.info(f"Connecting to Postgres at {settings.POSTGRES_HOST}...")
        pool = await asyncpg.create_pool(
            host=settings.POSTGRES_HOST,
            port=settings.POSTGRES_PORT,
            database=settings.POSTGRES_DB,
            user=settings.POSTGRES_USER,
            password=settings.POSTGRES_PASSWORD,
            min_size=1,
            max_size=10
        )
    return pool

async def close_db_pool():
    global pool
    if pool:
        await pool.close()
