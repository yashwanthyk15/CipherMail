from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from uuid import UUID, uuid4

class URLInfo(BaseModel):
    url: str
    is_link: bool
    anchor_text: Optional[str] = None

class AttachmentInfo(BaseModel):
    filename: str
    size_bytes: int
    mime_type: str
    extension: str
    sha256: str
    is_suspicious: Optional[bool] = None

class ParsedEmail(BaseModel):
    message_id: UUID = Field(default_factory=uuid4)
    timestamp_received: datetime = Field(default_factory=datetime.utcnow)
    sender_email: str
    sender_name: Optional[str] = None
    recipients: List[str]
    subject: str
    body_plain: Optional[str] = None
    body_html: Optional[str] = None
    urls: List[URLInfo] = []
    attachments: List[AttachmentInfo] = []
    headers_raw: Dict[str, Any] = {}
    size_bytes: int
    # raw_bytes omitted from this model since it's large, but will be stored in db
