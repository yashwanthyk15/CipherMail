import email
import email.policy
from email.message import EmailMessage
import re
import hashlib
from datetime import datetime, timezone
from typing import Tuple, List
import logging
from bs4 import BeautifulSoup
from .models import ParsedEmail, URLInfo, AttachmentInfo

logger = logging.getLogger(__name__)

class EmailParser:
    URL_REGEX = re.compile(
        r'(?:(?:https?|ftp)://)?[\w/\-?=%.]+\.[\w/\-&?=%.]+',
        re.IGNORECASE
    )

    @classmethod
    def parse(cls, raw_data: bytes, envelope_from: str = None, envelope_rcpt: List[str] = None) -> Tuple[ParsedEmail, bytes]:
        msg: EmailMessage = email.message_from_bytes(raw_data, policy=email.policy.default)
        
        # 1. Headers Extraction
        headers_raw = {k: v for k, v in msg.items()}
        
        # From header
        from_header = msg.get('From', '')
        if not from_header:
            sender_email = envelope_from if envelope_from else 'UNKNOWN_SENDER'
            sender_name = None
        else:
            # Simple parsing: "Name" <email> or just email
            match = re.search(r'<(.*?)>', from_header)
            if match:
                sender_email = match.group(1).strip()
                sender_name = from_header.split('<')[0].strip(' "')
            else:
                sender_email = from_header.strip()
                sender_name = None

        if not sender_email:
            sender_email = 'UNKNOWN_SENDER'

        # Subject
        subject = msg.get('Subject', '')
        
        # Date
        date_str = msg.get('Date')
        try:
            if date_str:
                timestamp = email.utils.parsedate_to_datetime(date_str)
                # Convert to naive UTC
                if timestamp.tzinfo is not None:
                    timestamp = timestamp.astimezone(timezone.utc).replace(tzinfo=None)
            else:
                timestamp = datetime.now(timezone.utc).replace(tzinfo=None)
        except Exception:
            timestamp = datetime.now(timezone.utc).replace(tzinfo=None)

        # Recipients
        recipients = envelope_rcpt if envelope_rcpt else []
        if not recipients:
            to_header = msg.get('To', '')
            if to_header:
                recipients = [addr.strip() for addr in to_header.split(',')]
            
        # 2. Body Extraction
        body_plain = ""
        body_html = ""
        attachments = []

        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition"))

                if "attachment" in content_disposition or "inline" in content_disposition and part.get_filename():
                    # Process attachment
                    if len(attachments) < 50:
                        att = cls._process_attachment(part)
                        if att:
                            attachments.append(att)
                    else:
                        logger.warning(f"Exceeded max attachments (50). Skipping remaining.")
                elif content_type == "text/plain":
                    payload = part.get_payload(decode=True)
                    if payload:
                        body_plain += payload.decode(errors='replace')
                elif content_type == "text/html":
                    payload = part.get_payload(decode=True)
                    if payload:
                        body_html += payload.decode(errors='replace')
        else:
            payload = msg.get_payload(decode=True)
            if payload:
                content_type = msg.get_content_type()
                if content_type == "text/html":
                    body_html = payload.decode(errors='replace')
                else:
                    body_plain = payload.decode(errors='replace')

        # 3. URL Extraction
        urls = cls._extract_urls(body_plain, body_html)

        parsed = ParsedEmail(
            timestamp_received=timestamp,
            sender_email=sender_email,
            sender_name=sender_name,
            recipients=recipients,
            subject=subject,
            body_plain=body_plain if body_plain else None,
            body_html=body_html if body_html else None,
            urls=urls,
            attachments=attachments,
            headers_raw=headers_raw,
            size_bytes=len(raw_data)
        )

        return parsed, raw_data

    @classmethod
    def _process_attachment(cls, part) -> AttachmentInfo:
        filename = part.get_filename()
        payload = part.get_payload(decode=True) or b""
        
        sha256 = hashlib.sha256(payload).hexdigest()
        
        if not filename:
            filename = sha256
            
        # Sanitize filename to ASCII
        filename = filename.encode('ascii', 'ignore').decode('ascii')
        if not filename:
            filename = "unknown_attachment"
            
        extension = filename.split('.')[-1].lower() if '.' in filename else ''
        mime_type = part.get_content_type()
        
        return AttachmentInfo(
            filename=filename,
            size_bytes=len(payload),
            mime_type=mime_type,
            extension=f".{extension}" if extension else "",
            sha256=sha256
        )

    @classmethod
    def _extract_urls(cls, plain: str, html: str) -> List[URLInfo]:
        found_urls = {}
        
        # Extract from HTML using BeautifulSoup
        if html:
            try:
                soup = BeautifulSoup(html, 'html.parser')
                for a_tag in soup.find_all('a', href=True):
                    href = a_tag['href'].strip()
                    if href.startswith(('http://', 'https://', 'ftp://')):
                        text = a_tag.get_text(strip=True)
                        found_urls[href] = URLInfo(url=href, is_link=True, anchor_text=text)
            except Exception as e:
                logger.error(f"Error parsing HTML: {e}")
                
        # Extract from plain text using regex
        text_to_search = f"{plain} {html}"
        matches = cls.URL_REGEX.findall(text_to_search)
        for match in matches:
            if match not in found_urls:
                if not match.startswith(('http://', 'https://', 'ftp://')):
                    url = f"http://{match}"
                else:
                    url = match
                found_urls[url] = URLInfo(url=url, is_link=False)
                
        return list(found_urls.values())
