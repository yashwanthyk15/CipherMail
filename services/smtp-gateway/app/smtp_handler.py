import asyncio
import logging
from aiosmtpd.handlers import Message
from typing import Optional
from .email_parser import EmailParser
from .models import ParsedEmail

logger = logging.getLogger(__name__)

class EmailSecurityHandler:
    def __init__(self, kafka_producer, postgres_pool, kafka_topic: str):
        self.kafka_producer = kafka_producer
        self.postgres_pool = postgres_pool
        self.kafka_topic = kafka_topic
        self.MAX_SIZE = 50 * 1024 * 1024 # 50 MB

    async def handle_DATA(self, server, session, envelope):
        # 1. Size check
        if len(envelope.content) > self.MAX_SIZE:
            logger.warning(f"Rejected email from {envelope.mail_from}: exceeds 50MB")
            return '552 Message too large'

        try:
            # 2. Parse Email
            parsed_email, raw_bytes = EmailParser.parse(
                envelope.content, 
                envelope_from=envelope.mail_from, 
                envelope_rcpt=envelope.rcpt_tos
            )
            
            logger.info(f"Parsed email: {parsed_email.message_id} from {parsed_email.sender_email}")

            # 3. Store in Postgres
            await self._store_in_db(parsed_email, raw_bytes)

            # 4. Publish to Kafka
            await self._publish_to_kafka(parsed_email)

            return '250 Message accepted for delivery'
            
        except Exception as e:
            logger.error(f"Error processing email: {e}", exc_info=True)
            # In a real gateway, we might want to still accept it or return a 4xx temp failure.
            # Returning 451 Temp Failure so the sender retries if it's a transient DB/Kafka issue.
            return '451 Requested action aborted: local error in processing'

    async def _store_in_db(self, email: ParsedEmail, raw_bytes: bytes):
        query = """
        INSERT INTO emails (
            message_id, timestamp_received, sender_email, sender_name,
            recipients, subject, body_plain, body_html, headers_raw,
            raw_email_blob, size_bytes
        ) VALUES (
            $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11
        )
        """
        import json
        
        async with self.postgres_pool.acquire() as conn:
            await conn.execute(
                query,
                email.message_id,
                email.timestamp_received,
                email.sender_email,
                email.sender_name,
                email.recipients,
                email.subject,
                email.body_plain,
                email.body_html,
                json.dumps(email.headers_raw),
                raw_bytes,
                email.size_bytes
            )

    async def _publish_to_kafka(self, email: ParsedEmail):
        # Send minimal representation to Kafka
        event_data = {
            "message_id": str(email.message_id),
            "sender_email": email.sender_email,
            "subject": email.subject,
            "urls": [u.dict() for u in email.urls],
            "attachments": [a.dict() for a in email.attachments],
            "headers_raw": email.headers_raw,
            "body_excerpt": (email.body_plain or "")[:500]
        }
        import json
        payload = json.dumps(event_data).encode('utf-8')
        await self.kafka_producer.send_and_wait(self.kafka_topic, payload)
