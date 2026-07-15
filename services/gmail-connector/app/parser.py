"""Parses raw Gmail messages into the standardized format our Kafka pipeline expects."""

import email
import email.policy
import hashlib
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

URL_REGEX = re.compile(
    r'https?://[^\s<>"\')\]]+|'
    r'href=["\']([^"\']+)["\']',
    re.IGNORECASE,
)


def parse_gmail_message(raw_bytes: bytes, gmail_message_id: str) -> dict:
    """
    Parse raw RFC 2822 email bytes into a dict matching our Kafka email.events schema.

    This is the same format the SMTP gateway produces, so the rest of the pipeline
    (ai-worker, reputation-worker, decision engine) works identically.
    """
    msg = email.message_from_bytes(raw_bytes, policy=email.policy.default)

    # --- Sender ---
    sender_email = "UNKNOWN_SENDER"
    sender_name = None
    from_header = msg.get("From", "")
    if from_header:
        # Parse "Display Name <email@example.com>" format
        parsed = email.utils.parseaddr(from_header)
        sender_name = parsed[0] if parsed[0] else None
        sender_email = parsed[1] if parsed[1] else "UNKNOWN_SENDER"

    # --- Recipients ---
    recipients = []
    for header_name in ("To", "Cc"):
        header_val = msg.get(header_name, "")
        if header_val:
            for _, addr in email.utils.getaddresses([header_val]):
                if addr:
                    recipients.append(addr)

    # --- Subject ---
    subject = msg.get("Subject", "") or ""

    # --- Timestamp ---
    timestamp = datetime.now(timezone.utc)
    date_header = msg.get("Date")
    if date_header:
        try:
            parsed_date = email.utils.parsedate_to_datetime(date_header)
            timestamp = parsed_date.astimezone(timezone.utc)
        except Exception:
            logger.warning("Failed to parse Date header, using current time.")

    # --- Body ---
    body_plain = None
    body_html = None
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            disposition = str(part.get("Content-Disposition", ""))
            if "attachment" in disposition:
                continue
            try:
                payload = part.get_content()
                if isinstance(payload, bytes):
                    payload = payload.decode("utf-8", errors="replace")
                if content_type == "text/plain" and not body_plain:
                    body_plain = payload
                elif content_type == "text/html" and not body_html:
                    body_html = payload
            except Exception:
                pass
    else:
        content_type = msg.get_content_type()
        try:
            payload = msg.get_content()
            if isinstance(payload, bytes):
                payload = payload.decode("utf-8", errors="replace")
            if content_type == "text/plain":
                body_plain = payload
            elif content_type == "text/html":
                body_html = payload
        except Exception:
            pass

    # --- URLs ---
    urls = []
    search_text = (body_plain or "") + " " + (body_html or "")
    found_urls = set()
    for match in URL_REGEX.finditer(search_text):
        url = match.group(1) if match.group(1) else match.group(0)
        url = url.rstrip(".,;:!?")
        if url and url not in found_urls and len(url) < 2048:
            found_urls.add(url)
            urls.append({
                "url": url,
                "is_link": bool(match.group(1)),
                "anchor_text": None,
            })

    # --- Attachments ---
    attachments = []
    if msg.is_multipart():
        for part in msg.walk():
            disposition = str(part.get("Content-Disposition", ""))
            if "attachment" not in disposition:
                continue
            try:
                content = part.get_payload(decode=True) or b""
                filename = part.get_filename() or ""
                if not filename:
                    sha = hashlib.sha256(content).hexdigest()[:12]
                    filename = f"attachment_{sha}"
                mime_type = part.get_content_type() or "application/octet-stream"
                ext = filename.rsplit(".", 1)[-1] if "." in filename else ""
                attachments.append({
                    "filename": filename,
                    "size_bytes": len(content),
                    "mime_type": mime_type,
                    "extension": ext,
                    "sha256": hashlib.sha256(content).hexdigest(),
                    "is_suspicious": None,
                })
            except Exception as e:
                logger.warning("Failed to parse attachment: %s", e)

    # --- Headers ---
    headers_raw = {}
    for key in msg.keys():
        val = msg.get(key)
        if key in headers_raw:
            if isinstance(headers_raw[key], list):
                headers_raw[key].append(val)
            else:
                headers_raw[key] = [headers_raw[key], val]
        else:
            headers_raw[key] = val

    # --- Build the event payload ---
    message_id = str(uuid.uuid4())

    return {
        "message_id": message_id,
        "gmail_message_id": gmail_message_id,
        "source": "gmail",
        "timestamp_received": timestamp.isoformat(),
        "sender_email": sender_email,
        "sender_name": sender_name,
        "recipients": recipients,
        "subject": subject,
        "body_plain": body_plain,
        "body_html": body_html,
        "body_excerpt": (body_plain or body_html or "")[:500],
        "urls": urls,
        "attachments": attachments,
        "headers_raw": headers_raw,
        "size_bytes": len(raw_bytes),
    }
