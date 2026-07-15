import asyncio
import logging
import json
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from .config import settings
from .classifier import AIClassifier

logging.basicConfig(level=settings.LOG_LEVEL)
logger = logging.getLogger(__name__)

async def process_email(msg, producer, classifier):
    try:
        email_data = json.loads(msg.value.decode('utf-8'))
        message_id = email_data.get("message_id")
        
        logger.info(f"Processing AI classification for {message_id}")
        
        classification_result = await classifier.classify(email_data)
        
        # Publish result
        result_event = {
            "message_id": message_id,
            "gemini_classification": classification_result
        }
        
        await producer.send_and_wait(
            settings.KAFKA_TOPIC_AI_RESULTS,
            json.dumps(result_event).encode('utf-8')
        )
        logger.info(f"Published AI classification for {message_id}")
        
    except Exception as e:
        logger.error(f"Error processing message: {e}")
        try:
            # Publish to DLQ
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
    logger.info("Starting AI Worker...")
    
    consumer = AIOKafkaConsumer(
        settings.KAFKA_TOPIC_EMAIL_EVENTS,
        bootstrap_servers=settings.KAFKA_BROKER,
        group_id="ai-worker-group"
    )
    
    producer = AIOKafkaProducer(
        bootstrap_servers=settings.KAFKA_BROKER
    )
    
    classifier = AIClassifier(api_key=settings.GEMINI_API_KEY)
    
    # Retry connection
    for _ in range(10):
        try:
            await consumer.start()
            await producer.start()
            break
        except Exception as e:
            logger.error(f"Waiting for Kafka... {e}")
            await asyncio.sleep(5)
            
    logger.info("Connected to Kafka. Waiting for messages...")
    
    try:
        async for msg in consumer:
            # We don't await here directly to process concurrently, but we should limit concurrency.
            # For simplicity in this demo worker, we'll just process sequentially.
            await process_email(msg, producer, classifier)
    finally:
        await consumer.stop()
        await producer.stop()

if __name__ == "__main__":
    asyncio.run(main())
