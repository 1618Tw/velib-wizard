"""Email alert helpers.

Sends one email via SMTP. Used by /health when the system flips to unhealthy.
Dedupe is handled by the caller — this module is intentionally stateless.
"""
from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage

from config import settings

log = logging.getLogger("velib.notifier")


def alerts_enabled() -> bool:
    return bool(settings.smtp_user and settings.smtp_password)


def send_email_alert(subject: str, body: str) -> bool:
    if not alerts_enabled():
        log.info("alert suppressed (SMTP not configured): %s", subject)
        return False

    to = settings.alert_to or settings.smtp_user

    msg = EmailMessage()
    msg["From"] = settings.smtp_user
    msg["To"] = to
    msg["Subject"] = f"[Vélib Wizard] {subject}"
    msg.set_content(body)

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as server:
            server.starttls()
            server.login(settings.smtp_user, settings.smtp_password)
            server.send_message(msg)
        log.info("alert sent to %s: %s", to, subject)
        return True
    except Exception as exc:
        log.exception("alert send failed: %s", exc)
        return False
