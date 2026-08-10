"""
Gmail API service for sending emails with optional attachments.

Uses OAuth2 credentials (credentials.json → token.json flow).
Gracefully handles "not configured" state if credentials are missing.
"""

import os
import base64
import logging
import mimetypes
from email.message import EmailMessage
from pathlib import Path

logger = logging.getLogger(__name__)

# Gmail API scopes
SCOPES = ["https://www.googleapis.com/auth/gmail.send"]

# Paths for OAuth credentials
CREDENTIALS_FILE = Path(__file__).parent / "credentials.json"
TOKEN_FILE = Path(__file__).parent / "token.json"

try:
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    HAS_GMAIL_DEPS = True
except ImportError:
    HAS_GMAIL_DEPS = False


def _get_gmail_service():
    """Build and return an authenticated Gmail API service, or None if not configured."""
    if not HAS_GMAIL_DEPS:
        logger.warning("Gmail API dependencies not installed — email sending disabled.")
        return None

    if not CREDENTIALS_FILE.exists():
        logger.warning("Gmail credentials.json not found — email sending disabled.")
        return None

    try:
        creds = None

        # Load existing token
        if TOKEN_FILE.exists():
            creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)

        # Refresh or re-authenticate
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(CREDENTIALS_FILE), SCOPES
                )
                creds = flow.run_local_server(port=0)

            # Save token for future use
            with open(TOKEN_FILE, "w") as f:
                f.write(creds.to_json())

        return build("gmail", "v1", credentials=creds)

    except Exception as e:
        logger.error(f"Failed to initialize Gmail service: {e}")
        return None


def send_email(
    to: str,
    subject: str,
    body: str,
    attachment_data: bytes = None,
    attachment_name: str = None,
) -> dict:
    """Send an email via Gmail API.

    Args:
        to: Recipient email address.
        subject: Email subject.
        body: Email body text.
        attachment_data: Optional raw bytes of the file to attach.
        attachment_name: Optional filename for the attachment.

    Returns:
        dict with 'success' bool and 'message' string.
    """
    service = _get_gmail_service()
    if service is None:
        return {
            "success": False,
            "message": "Gmail API is not configured. Place credentials.json in the relay-server directory and restart.",
        }

    try:
        # Build MIME message
        message = EmailMessage()
        message.set_content(body)
        message["To"] = to
        message["Subject"] = subject
        message["From"] = "me"

        # Add attachment if provided
        if attachment_data and attachment_name:
            # Determine MIME type
            mime_type, _ = mimetypes.guess_type(attachment_name)
            if mime_type:
                maintype, subtype = mime_type.split("/", 1)
            else:
                maintype, subtype = "application", "octet-stream"

            message.add_attachment(
                attachment_data,
                maintype=maintype,
                subtype=subtype,
                filename=attachment_name,
            )

        # Encode and send
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
        sent = (
            service.users()
            .messages()
            .send(userId="me", body={"raw": raw})
            .execute()
        )

        logger.info(f"Email sent to {to}, message ID: {sent.get('id')}")
        return {
            "success": True,
            "message": f"Email sent successfully to {to}.",
            "message_id": sent.get("id"),
        }

    except Exception as e:
        logger.error(f"Failed to send email: {e}")
        return {"success": False, "message": f"Failed to send email: {str(e)}"}
