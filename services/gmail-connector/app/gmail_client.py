"""Gmail API client for reading emails and applying security labels."""

import base64
import logging
from typing import Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from .config import settings

logger = logging.getLogger(__name__)

# Label names that will appear in Gmail
LABEL_SAFE = "ESG-Safe"
LABEL_PHISHING = "ESG-Phishing"
LABEL_QUARANTINE = "ESG-Quarantine"
LABEL_BLOCKED = "ESG-Blocked"

SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]


class GmailClient:
    """Handles all Gmail API interactions."""

    def __init__(self):
        self.service = None
        self.label_ids: dict[str, str] = {}

    def authenticate(self) -> None:
        """Load OAuth2 credentials from token.json and build the Gmail service."""
        creds = None
        try:
            creds = Credentials.from_authorized_user_file(
                settings.GMAIL_TOKEN_FILE, SCOPES
            )
        except Exception as e:
            logger.error("Failed to load token.json: %s", e)
            raise RuntimeError(
                "token.json not found or invalid. "
                "Run 'python scripts/setup_gmail_auth.py' first."
            ) from e

        # Refresh the token if it has expired
        if creds and creds.expired and creds.refresh_token:
            logger.info("Refreshing expired Gmail token...")
            creds.refresh(Request())
            # Save the refreshed token back
            with open(settings.GMAIL_TOKEN_FILE, "w") as f:
                f.write(creds.to_json())
            logger.info("Token refreshed and saved.")

        if not creds or not creds.valid:
            raise RuntimeError(
                "Gmail credentials are invalid. "
                "Run 'python scripts/setup_gmail_auth.py' to re-authenticate."
            )

        self.service = build("gmail", "v1", credentials=creds)
        logger.info("Gmail API client authenticated successfully.")

        # Ensure our custom labels exist
        self._ensure_labels()

    def _ensure_labels(self) -> None:
        """Create ESG labels in Gmail if they don't already exist."""
        results = self.service.users().labels().list(userId="me").execute()
        existing = {lbl["name"]: lbl["id"] for lbl in results.get("labels", [])}

        label_colors = {
            LABEL_SAFE: {"backgroundColor": "#16a765", "textColor": "#ffffff"},
            LABEL_PHISHING: {"backgroundColor": "#cc3a21", "textColor": "#ffffff"},
            LABEL_QUARANTINE: {"backgroundColor": "#fad165", "textColor": "#000000"},
            LABEL_BLOCKED: {"backgroundColor": "#a46a21", "textColor": "#ffffff"},
        }

        for label_name in [LABEL_SAFE, LABEL_PHISHING, LABEL_QUARANTINE, LABEL_BLOCKED]:
            if label_name in existing:
                self.label_ids[label_name] = existing[label_name]
                logger.info("Label '%s' already exists (id=%s)", label_name, existing[label_name])
            else:
                body = {
                    "name": label_name,
                    "labelListVisibility": "labelShow",
                    "messageListVisibility": "show",
                    "color": label_colors.get(label_name, {}),
                }
                result = self.service.users().labels().create(
                    userId="me", body=body
                ).execute()
                self.label_ids[label_name] = result["id"]
                logger.info("Created label '%s' (id=%s)", label_name, result["id"])

    def fetch_unread_emails(self, max_results: int = 10) -> list[dict]:
        """Fetch unread emails that haven't been labeled by ESG yet."""
        # Query: unread emails that don't have any ESG label
        query = "is:unread -label:ESG-Safe -label:ESG-Phishing -label:ESG-Quarantine -label:ESG-Blocked"

        try:
            results = (
                self.service.users()
                .messages()
                .list(userId="me", q=query, maxResults=max_results)
                .execute()
            )
        except Exception as e:
            logger.error("Failed to list messages: %s", e)
            return []

        messages = results.get("messages", [])
        if not messages:
            return []

        logger.info("Found %d unread, unscanned emails.", len(messages))

        full_messages = []
        for msg_info in messages:
            try:
                msg = (
                    self.service.users()
                    .messages()
                    .get(userId="me", id=msg_info["id"], format="raw")
                    .execute()
                )
                full_messages.append(msg)
            except Exception as e:
                logger.error("Failed to fetch message %s: %s", msg_info["id"], e)

        return full_messages

    def get_raw_bytes(self, message: dict) -> bytes:
        """Extract raw RFC 2822 email bytes from a Gmail API message."""
        raw = message.get("raw", "")
        # Gmail returns URL-safe base64
        return base64.urlsafe_b64decode(raw)

    def apply_label(self, gmail_message_id: str, decision: str) -> None:
        """Apply an ESG security label to an email in Gmail."""
        label_map = {
            "ALLOW": LABEL_SAFE,
            "QUARANTINE": LABEL_QUARANTINE,
            "BLOCK": LABEL_BLOCKED,
            "PHISHING": LABEL_PHISHING,
        }

        label_name = label_map.get(decision, LABEL_SAFE)
        label_id = self.label_ids.get(label_name)

        if not label_id:
            logger.warning("No label ID found for '%s', skipping.", label_name)
            return

        try:
            self.service.users().messages().modify(
                userId="me",
                id=gmail_message_id,
                body={"addLabelIds": [label_id]},
            ).execute()
            logger.info(
                "Applied label '%s' to Gmail message %s", label_name, gmail_message_id
            )
        except Exception as e:
            logger.error(
                "Failed to apply label to message %s: %s", gmail_message_id, e
            )

    def get_user_email(self) -> Optional[str]:
        """Get the authenticated user's email address."""
        try:
            profile = self.service.users().getProfile(userId="me").execute()
            return profile.get("emailAddress")
        except Exception:
            return None
