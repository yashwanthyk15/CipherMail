import asyncio
import logging
import json
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
import redis.asyncio as redis
from .config import settings
from .scanner import ReputationScanner

logging.basicConfig(level=settings.LOG_LEVEL)
logger = logging.getLogger(__name__)

async def process_email(msg, producer, scanner, redis_client):
    try:
        email_data = json.loads(msg.value.decode('utf-8'))
        message_id = email_data.get("message_id")
        
        logger.info(f"Processing reputation analysis for {message_id}")
        
        urls = [u.get('url') for u in email_data.get('urls', [])]
        hashes = [a.get('sha256') for a in email_data.get('attachments', [])]
        
        url_results = await scanner.scan_urls(urls, redis_client)
        attachment_results = await scanner.scan_hashes(hashes, redis_client)
        
        # Publish result
        result_event = {
            "message_id": message_id,
            "url_analysis": url_results,
            "attachment_analysis": attachment_results
        }
        
        await producer.send_and_wait(
            settings.KAFKA_TOPIC_REP_RESULTS,
            json.dumps(result_event).encode('utf-8')
        )
        logger.info(f"Published reputation analysis for {message_id}")
        
    except Exception as e:
        logger.error(f"Error processing message: {e}")
        try:
            dlq_event = {
                "error": str(e),
                "original_message": email_data if 'email_data' in locals() else None
            }
            await producer.send_and_wait(
                "email.events.dlq",
                json.dumps(dlq_event).encode('utf-8')
            )
            logger.info("Published failed message to DLQ")
        except Exception as dlq_e:
            logger.error(f"Failed to publish to DLQ: {dlq_e}")
async def main():
    logger.info("Starting Reputation Worker...")
    
    consumer = AIOKafkaConsumer(
        settings.KAFKA_TOPIC_EMAIL_EVENTS,
        bootstrap_servers=settings.KAFKA_BROKER,
        group_id="rep-worker-group"
    )
    
    producer = AIOKafkaProducer(
        bootstrap_servers=settings.KAFKA_BROKER
    )
    
    redis_client = redis.Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, decode_responses=True)
    scanner = ReputationScanner(api_key=settings.VIRUSTOTAL_API_KEY)
    
    # Retry connection
    for _ in range(10):
        try:
            await consumer.start()
            await producer.start()
            await redis_client.ping()
            break
        except Exception as e:
            logger.error(f"Waiting for Kafka/Redis... {e}")
            await asyncio.sleep(5)
            
    logger.info("Connected. Waiting for messages...")
    
    try:
        async for msg in consumer:
            await process_email(msg, producer, scanner, redis_client)
    finally:
        await consumer.stop()
        await producer.stop()
        await redis_client.close()

if __name__ == "__main__":
    asyncio.run(main())
