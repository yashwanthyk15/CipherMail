from fastapi import APIRouter, HTTPException
from ..database import get_db_pool

router = APIRouter()

@router.get("/inbox")
async def get_inbox(limit: int = 50, offset: int = 0):
    pool = await get_db_pool()
    query = """
    SELECT e.message_id, e.timestamp_received, e.sender_email, e.subject,
           d.decision, d.threat_score
    FROM emails e
    JOIN decisions d ON e.message_id = d.message_id
    WHERE d.decision = 'ALLOW'
    ORDER BY e.timestamp_received DESC
    LIMIT $1 OFFSET $2
    """
    async with pool.acquire() as conn:
        rows = await conn.fetch(query, limit, offset)
        return [dict(row) for row in rows]

@router.get("/inbox/{message_id}")
async def get_inbox_detail(message_id: str):
    pool = await get_db_pool()
    query = """
    SELECT e.message_id, e.timestamp_received, e.sender_email, e.subject,
           e.body_plain, e.body_html,
           d.decision, d.threat_score, d.reasoning,
           t.spf_score, t.dkim_score, t.urls_found, t.attachments_found, t.gemini_classification
    FROM emails e
    JOIN decisions d ON e.message_id = d.message_id
    JOIN threat_analysis t ON e.message_id = t.message_id
    WHERE e.message_id = $1
    """
    import uuid
    try:
        msg_uuid = uuid.UUID(message_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid message_id format")

    async with pool.acquire() as conn:
        row = await conn.fetchrow(query, msg_uuid)
        if not row:
            raise HTTPException(status_code=404, detail="Email not found")
        
        import json
        result = dict(row)
        if isinstance(result['reasoning'], str):
            result['reasoning'] = json.loads(result['reasoning'])
        if isinstance(result['gemini_classification'], str):
            result['gemini_classification'] = json.loads(result['gemini_classification'])
            
        return result
