"""
Gmail sender via SMTP + App Password.
No OAuth, no Google Cloud project needed.

Setup (one-time, ~30 seconds):
  1. Go to myaccount.google.com/security
  2. Enable 2-Step Verification if not already on
  3. Search "App passwords" → create one (name it "autointern")
  4. Paste the 16-char password into .env as GMAIL_APP_PASSWORD
"""

import asyncio
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.config import settings

logger = logging.getLogger(__name__)

_SMTP_HOST = "smtp.gmail.com"
_SMTP_PORT = 465


def _check_config() -> None:
    if not settings.GMAIL_APP_PASSWORD:
        raise RuntimeError(
            "Gmail not configured. Generate an App Password at "
            "myaccount.google.com/security → App passwords, "
            "then set GMAIL_APP_PASSWORD in .env."
        )
    if not settings.FROM_EMAIL:
        raise RuntimeError("FROM_EMAIL not set in .env.")


def _smtp_send(to: str, subject: str, body: str) -> str:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.FROM_EMAIL
    msg["To"] = to
    msg.attach(MIMEText(body, "plain"))

    password = (settings.GMAIL_APP_PASSWORD or "").replace(" ", "")
    with smtplib.SMTP_SSL(_SMTP_HOST, _SMTP_PORT) as server:
        server.login(settings.FROM_EMAIL, password)
        server.send_message(msg)

    msg_id = f"smtp-{to}-{subject[:30]}"
    logger.info("Sent email to %s | subject: %s", to, subject)
    return msg_id


async def send_cold_email(to: str, subject: str, body: str) -> str:
    """
    Send a cold email via Gmail SMTP.
    Runs the blocking SMTP call in a thread so it doesn't block the event loop.
    Returns a pseudo message ID.
    """
    _check_config()
    return await asyncio.to_thread(_smtp_send, to, subject, body)
