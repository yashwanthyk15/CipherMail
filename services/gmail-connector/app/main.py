"""
Gmail Connector Main Service.

Polls Gmail for new unread emails, pushes them through the ESG Kafka pipeline,
and applies security labels back to Gmail when decisions arrive.
"""

import asyncio
import json
import logging
import signal
import sys
import time

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
import redis

from .config import settings
from .gmail_client import GmailClient
from .parser import parse_gmail_message

# --- Logging Setup ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)-20s | %(levelname)-7s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)
logger = logging.getLogger("gmail-connector")

# Suppress noisy Google API discovery cache logs
logging.getLogger("googleapiclient.discovery_cache").setLevel(logging.ERROR)

# The ai-worker publishes results to this topic
KAFKA_TOPIC_AI_RESULTS = "email.ai_results"


def score_to_decision(phishing_risk: int) -> str:
    """Convert a 0-100 phishing risk score to a security decision."""
    if phishing_risk >= 80:
        return "PHISHING"
    elif phishing_risk >= 60:
        return "QUARANTINE"
    elif phishing_risk >= 40:
        return "QUARANTINE"
    else:
        return "ALLOW"


class GmailConnectorService:
    """Main service that bridges Gmail with the ESG Kafka pipeline."""

    def __init__(self):
        self.gmail = GmailClient()
        self.producer: AIOKafkaProducer | None = None
        self.consumer: AIOKafkaConsumer | None = None
        self.redis_client: redis.Redis | None = None
        self.running = True
        self.emails_scanned = 0
        self.labels_applied = 0

    async def start(self) -> None:
        """Initialize all connections and start the service."""
        logger.info("=" * 60)
        logger.info("  EMAIL SECURITY GATEWAY - Gmail Connector")
        logger.info("=" * 60)

        # 1. Authenticate with Gmail
        logger.info("[1/4] Authenticating with Gmail API...")
        self.gmail.authenticate()
        user_email = self.gmail.get_user_email()
        logger.info("  > Monitoring inbox: %s", user_email)

        # 2. Connect to Redis (for mapping ESG message_id <-> Gmail message_id)
        logger.info("[2/4] Connecting to Redis...")
        self.redis_client = await self._connect_redis()
        logger.info("  > Redis connected at %s:%s", settings.REDIS_HOST, settings.REDIS_PORT)

        # 3. Connect Kafka producer
        logger.info("[3/4] Connecting Kafka producer...")
        self.producer = await self._connect_producer()
        logger.info("  > Kafka producer ready")

        # 4. Connect Kafka consumer (for AI results)
        logger.info("[4/4] Connecting Kafka consumer...")
        self.consumer = await self._connect_consumer()
        logger.info("  > Kafka consumer subscribed to '%s'", KAFKA_TOPIC_AI_RESULTS)

        logger.info("")
        logger.info("  Gmail Connector is LIVE - polling every %ds", settings.GMAIL_POLL_INTERVAL_SECONDS)
        logger.info("=" * 60)

        # Run both loops concurrently
        await asyncio.gather(
            self._poll_gmail_loop(),
            self._listen_decisions_loop(),
        )

    async def _connect_redis(self) -> redis.Redis:
        """Connect to Redis with retry."""
        for attempt in range(10):
            try:
                client = redis.Redis(
                    host=settings.REDIS_HOST,
                    port=settings.REDIS_PORT,
                    decode_responses=True,
                )
                client.ping()
                return client
            except Exception as e:
                wait = min(2 ** attempt, 30)
                logger.warning("Redis not ready (attempt %d): %s - retrying in %ds", attempt + 1, e, wait)
                await asyncio.sleep(wait)
        raise RuntimeError("Could not connect to Redis after 10 attempts")

    async def _connect_producer(self) -> AIOKafkaProducer:
        """Connect Kafka producer with retry."""
        for attempt in range(10):
            try:
                producer = AIOKafkaProducer(
                    bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
                    value_serializer=lambda v: json.dumps(v).encode("utf-8"),
                )
                await producer.start()
                return producer
            except Exception as e:
                wait = min(2 ** attempt, 30)
                logger.warning("Kafka producer not ready (attempt %d): %s - retrying in %ds", attempt + 1, e, wait)
                await asyncio.sleep(wait)
        raise RuntimeError("Could not connect Kafka producer after 10 attempts")

    async def _connect_consumer(self) -> AIOKafkaConsumer:
        """Connect Kafka consumer with retry."""
        for attempt in range(10):
            try:
                consumer = AIOKafkaConsumer(
                    KAFKA_TOPIC_AI_RESULTS,
                    bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
                    group_id=settings.KAFKA_GROUP_ID,
                    value_deserializer=lambda v: json.loads(v.decode("utf-8")),
                    auto_offset_reset="latest",
                )
                await consumer.start()
                return consumer
            except Exception as e:
                wait = min(2 ** attempt, 30)
                logger.warning("Kafka consumer not ready (attempt %d): %s - retrying in %ds", attempt + 1, e, wait)
                await asyncio.sleep(wait)
        raise RuntimeError("Could not connect Kafka consumer after 10 attempts")

    async def _poll_gmail_loop(self) -> None:
        """Continuously poll Gmail for new unread emails and push to Kafka."""
        while self.running:
            try:
                messages = self.gmail.fetch_unread_emails(
                    max_results=settings.GMAIL_MAX_RESULTS
                )

                for msg in messages:
                    gmail_id = msg["id"]
                    raw_bytes = self.gmail.get_raw_bytes(msg)

                    # Parse into our standard format
                    parsed = parse_gmail_message(raw_bytes, gmail_id)
                    esg_message_id = parsed["message_id"]

                    # Store mapping: ESG UUID -> Gmail message ID (TTL 1 hour)
                    self.redis_client.setex(
                        f"gmail_map:{esg_message_id}",
                        3600,
                        gmail_id,
                    )

                    # Publish FLAT email data to Kafka — the ai-worker expects
                    # top-level keys like message_id, sender_email, subject, etc.
                    await self.producer.send_and_wait(
                        settings.KAFKA_TOPIC_EMAIL_EVENTS,
                        value=parsed,
                    )

                    self.emails_scanned += 1
                    logger.info(
                        "[SCAN #%d] from=%s subj='%s' -> Kafka",
                        self.emails_scanned,
                        parsed["sender_email"],
                        (parsed["subject"] or "(no subject)")[:50],
                    )

            except Exception as e:
                logger.error("Error in Gmail poll loop: %s", e, exc_info=True)

            await asyncio.sleep(settings.GMAIL_POLL_INTERVAL_SECONDS)

    async def _listen_decisions_loop(self) -> None:
        """Listen for AI result events from Kafka and apply labels back to Gmail."""
        while self.running:
            try:
                async for msg in self.consumer:
                    try:
                        event = msg.value
                        esg_message_id = event.get("message_id")

                        if not esg_message_id:
                            continue

                        # Look up the Gmail message ID from Redis
                        gmail_id = self.redis_client.get(f"gmail_map:{esg_message_id}")
                        if not gmail_id:
                            # Not a Gmail-sourced email (could be from SMTP gateway or simulator)
                            continue

                        # Extract phishing risk from the AI classification
                        classification = event.get("gemini_classification", {})
                        phishing_risk = classification.get("phishing_risk", 0)

                        # Convert score to decision
                        decision = score_to_decision(phishing_risk)

                        # Apply the label in Gmail!
                        self.gmail.apply_label(gmail_id, decision)
                        self.labels_applied += 1

                        logger.info(
                            "[LABEL #%d] decision=%s risk=%d -> Gmail msg %s",
                            self.labels_applied,
                            decision,
                            phishing_risk,
                            gmail_id,
                        )

                    except Exception as e:
                        logger.error("Error processing AI result: %s", e)

            except Exception as e:
                logger.error("Kafka consumer error: %s - reconnecting in 5s", e)
                await asyncio.sleep(5)

    async def stop(self) -> None:
        """Gracefully shut down all connections."""
        self.running = False
        logger.info("Shutting down Gmail Connector...")
        if self.producer:
            await self.producer.stop()
        if self.consumer:
            await self.consumer.stop()
        if self.redis_client:
            self.redis_client.close()
        logger.info("Gmail Connector stopped. Scanned=%d, Labeled=%d", self.emails_scanned, self.labels_applied)


def main():
    service = GmailConnectorService()

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    def handle_signal(*_):
        logger.info("Received shutdown signal.")
        loop.create_task(service.stop())

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, handle_signal)
        except NotImplementedError:
            # Windows doesn't support add_signal_handler
            pass

    try:
        loop.run_until_complete(service.start())
    except KeyboardInterrupt:
        loop.run_until_complete(service.stop())
    finally:
        loop.close()


if __name__ == "__main__":
    main()
