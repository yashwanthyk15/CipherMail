from fastapi import APIRouter
from ..database import get_db_pool

router = APIRouter()

@router.get("/stats")
async def get_stats():
    pool = await get_db_pool()
    query = """
    SELECT 
        COUNT(*) as total_processed,
        COALESCE(SUM(CASE WHEN decision = 'ALLOW' THEN 1 ELSE 0 END), 0) as allowed,
        COALESCE(SUM(CASE WHEN decision = 'QUARANTINE' THEN 1 ELSE 0 END), 0) as quarantined,
        COALESCE(SUM(CASE WHEN decision = 'BLOCK' THEN 1 ELSE 0 END), 0) as blocked,
        COALESCE(AVG(threat_score), 0) as avg_threat_score
    FROM decisions
    """
    async with pool.acquire() as conn:
        row = await conn.fetchrow(query)
        if row:
            return dict(row)
        return {"total_processed": 0, "allowed": 0, "quarantined": 0, "blocked": 0, "avg_threat_score": 0}
