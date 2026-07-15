from fastapi import APIRouter
from ..database import get_db_pool

router = APIRouter()

@router.get("/quarantine")
async def get_quarantine(limit: int = 50, offset: int = 0):
    pool = await get_db_pool()
    query = """
    SELECT e.message_id, e.timestamp_received, e.sender_email, e.subject,
           d.decision, d.threat_score, d.reasoning
    FROM emails e
    JOIN decisions d ON e.message_id = d.message_id
    WHERE d.decision = 'QUARANTINE' OR d.decision = 'BLOCK'
    ORDER BY e.timestamp_received DESC
    LIMIT $1 OFFSET $2
    """
    async with pool.acquire() as conn:
        rows = await conn.fetch(query, limit, offset)
        import json
        res = []
        for r in rows:
            d = dict(r)
            if isinstance(d['reasoning'], str):
                d['reasoning'] = json.loads(d['reasoning'])
            res.append(d)
        return res
