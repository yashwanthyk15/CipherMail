from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from ..database import get_db_pool
from ..websocket import manager

router = APIRouter()

@router.get("/alerts")
async def get_alerts(limit: int = 50):
    pool = await get_db_pool()
    query = """
    SELECT alert_id, timestamp, severity, threat_type, sender_email, subject, action_taken
    FROM alerts
    ORDER BY timestamp DESC
    LIMIT $1
    """
    async with pool.acquire() as conn:
        rows = await conn.fetch(query, limit)
        return [dict(row) for row in rows]

@router.websocket("/ws/alerts")
async def websocket_alerts(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # We just keep connection alive, messages are pushed from kafka listener
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
