import asyncio
import logging
from fastapi import FastAPI
from aiosmtpd.controller import Controller
from aiokafka import AIOKafkaProducer
import asyncpg

from .config import settings
from .smtp_handler import EmailSecurityHandler

logging.basicConfig(level=settings.LOG_LEVEL)
logger = logging.getLogger(__name__)

app = FastAPI(title="ESG SMTP Gateway")

# Global resources
kafka_producer = None
postgres_pool = None
smtp_server = None

async def init_kafka():
    global kafka_producer
    logger.info(f"Connecting to Kafka at {settings.KAFKA_BROKER}...")
    producer = AIOKafkaProducer(
        bootstrap_servers=settings.KAFKA_BROKER,
        client_id="smtp-gateway"
    )
    await producer.start()
    kafka_producer = producer
    logger.info("Connected to Kafka")

async def init_postgres():
    global postgres_pool
    logger.info(f"Connecting to Postgres at {settings.POSTGRES_HOST}...")
    postgres_pool = await asyncpg.create_pool(
        host=settings.POSTGRES_HOST,
        port=settings.POSTGRES_PORT,
        database=settings.POSTGRES_DB,
        user=settings.POSTGRES_USER,
        password=settings.POSTGRES_PASSWORD,
        min_size=1,
        max_size=10
    )
    logger.info("Connected to Postgres")

@app.on_event("startup")
async def startup_event():
    # Attempt to connect to backend services with some retries
    for attempt in range(10):
        try:
            if not postgres_pool:
                await init_postgres()
            if not kafka_producer:
                await init_kafka()
            break
        except Exception as e:
            logger.error(f"Failed to connect to backends (attempt {attempt+1}/10): {e}")
            await asyncio.sleep(5)
    
    # Start SMTP Server
    global smtp_server
    from aiosmtpd.smtp import SMTP
    handler = EmailSecurityHandler(
        kafka_producer=kafka_producer,
        postgres_pool=postgres_pool,
        kafka_topic=settings.KAFKA_TOPIC_EMAIL_EVENTS
    )
    loop = asyncio.get_running_loop()
    smtp_server = await loop.create_server(
        lambda: SMTP(handler),
        host=settings.SMTP_LISTEN_HOST,
        port=settings.SMTP_LISTEN_PORT
    )
    logger.info(f"SMTP Server started on {settings.SMTP_LISTEN_HOST}:{settings.SMTP_LISTEN_PORT}")

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Shutting down...")
    if smtp_server:
        smtp_server.close()
        await smtp_server.wait_closed()
    if kafka_producer:
        await kafka_producer.stop()
    if postgres_pool:
        await postgres_pool.close()

@app.get("/health")
async def health_check():
    status = {
        "service": "smtp-gateway",
        "status": "healthy",
        "postgres_connected": postgres_pool is not None,
        "kafka_connected": kafka_producer is not None
    }
    return status
