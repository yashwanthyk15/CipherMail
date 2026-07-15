import asyncio
import logging
from fastapi import FastAPI, Depends, Request
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .database import get_db_pool, close_db_pool
from .routes import inbox, quarantine, alerts, stats, simulator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="ESG API Dashboard Backend")

# Allow CORS for dashboard
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_event():
    # Attempt to connect to backend services with some retries
    for attempt in range(10):
        try:
            await get_db_pool()
            break
        except Exception as e:
            logger.error(f"Failed to connect to postgres (attempt {attempt+1}/10): {e}")
            await asyncio.sleep(5)
            
    # Normally we might start a background task here to listen to Kafka for real-time alerts
    # to broadcast via WebSockets.
    asyncio.create_task(kafka_alert_listener())

async def kafka_alert_listener():
    # Listens to email.ai_results topic, calculates decision, writes to DB, and broadcasts via websocket
    from aiokafka import AIOKafkaConsumer
    import json
    from .websocket import manager
    
    while True:
        try:
            consumer = AIOKafkaConsumer(
                "email.ai_results",
                bootstrap_servers=settings.KAFKA_BROKER,
                group_id="api-threat-analyzer-group",
                value_deserializer=lambda m: json.loads(m.decode('utf-8'))
            )
            await consumer.start()
            try:
                async for msg in consumer:
                    data = msg.value
                    message_id = data.get("message_id")
                    classification = data.get("gemini_classification", {})
                    
                    threat_score = classification.get("phishing_risk", 0)
                    is_phishing = threat_score > 60
                    decision = 'BLOCK' if is_phishing else 'ALLOW'
                    severity = 'HIGH' if threat_score > 80 else 'MEDIUM' if threat_score > 50 else 'LOW'
                    
                    pool = await get_db_pool()
                    if not pool:
                        continue
                        
                    async with pool.acquire() as conn:
                        # Check if already processed
                        exists = await conn.fetchval("SELECT 1 FROM decisions WHERE message_id = $1", message_id)
                        if exists:
                            continue
                            
                        # Insert threat analysis
                        analysis_id = await conn.fetchval("""
                            INSERT INTO threat_analysis (message_id, gemini_classification, composite_threat_score)
                            VALUES ($1, $2, $3)
                            RETURNING analysis_id
                        """, message_id, json.dumps(classification), threat_score)
                        
                        # Insert decision
                        await conn.execute("""
                            INSERT INTO decisions (message_id, analysis_id, decision, threat_score, reasoning)
                            VALUES ($1, $2, $3, $4, $5)
                        """, message_id, analysis_id, decision, threat_score, json.dumps({"explanation": classification.get("reason", "")}))
                        
                        if is_phishing:
                            row = await conn.fetchrow("SELECT sender_email, subject FROM emails WHERE message_id = $1", message_id)
                            if row:
                                await conn.execute("""
                                    INSERT INTO alerts (message_id, severity, threat_type, sender_email, subject, action_taken)
                                    VALUES ($1, $2, $3, $4, $5, $6)
                                """, message_id, severity, "PHISHING" if is_phishing else "SAFE", row['sender_email'], row['subject'], decision)
                                
                                alert_msg = {
                                    "alert_id": str(message_id),
                                    "message_id": str(message_id),
                                    "severity": severity,
                                    "threat_type": "PHISHING" if is_phishing else "SAFE",
                                    "sender_email": row['sender_email'],
                                    "subject": row['subject'],
                                    "action_taken": decision,
                                    "timestamp": "Just now"
                                }
                                await manager.broadcast_alert(alert_msg)
            finally:
                await consumer.stop()
        except Exception as e:
            logger.error(f"Error in Kafka alert listener: {e}")
            await asyncio.sleep(5)

@app.on_event("shutdown")
async def shutdown_event():
    await close_db_pool()

@app.get("/health")
async def health_check():
    pool = await get_db_pool()
    return {
        "service": "api",
        "status": "healthy",
        "postgres_connected": pool is not None
    }

app.include_router(inbox.router, prefix="/api")
app.include_router(quarantine.router, prefix="/api")
app.include_router(alerts.router, prefix="/api")
app.include_router(stats.router, prefix="/api")
app.include_router(simulator.router, prefix="/api/admin")
