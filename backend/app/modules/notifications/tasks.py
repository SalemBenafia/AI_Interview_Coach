"""
app/modules/notifications/tasks.py
=====================================
Real email delivery via aiosmtplib (MailHog in dev, any real SMTP server in
production -- see technologies.txt §11 "Dev Email System: MailHog"). Every
send is logged to NotificationLog regardless of channel, so the candidate's
in-app notification feed and email history share one source of truth.
"""
from __future__ import annotations

import asyncio

import aiosmtplib
import structlog
from email.message import EmailMessage

from app.core.celery_app import celery_app
from app.core.settings import settings
from app.db.models import NotificationChannel, NotificationLog, NotificationStatus
from app.db.session import get_db_context

logger = structlog.get_logger()


async def _send_email_async(*, to: str, subject: str, body: str, candidate_id: str | None = None) -> None:
    message = EmailMessage()
    message["From"] = settings.SMTP_FROM
    message["To"] = to
    message["Subject"] = subject
    message.set_content(body)

    log = NotificationLog(
        candidate_id=candidate_id,
        channel=NotificationChannel.EMAIL,
        recipient=to,
        subject=subject,
        body=body,
        status=NotificationStatus.PENDING,
    )

    try:
        await aiosmtplib.send(
            message,
            hostname=settings.SMTP_HOST,
            port=settings.SMTP_PORT,
            username=settings.SMTP_USER or None,
            password=settings.SMTP_PASSWORD or None,
            use_tls=False,
            start_tls=bool(settings.SMTP_USER),
        )
        log.status = NotificationStatus.SENT
        from datetime import datetime, timezone
        log.sent_at = datetime.now(tz=timezone.utc)
    except Exception as exc:
        logger.error("email_send_failed", to=to, error=str(exc))
        log.status = NotificationStatus.FAILED
        log.error_message = str(exc)
        raise
    finally:
        async with get_db_context() as db:
            db.add(log)


@celery_app.task(name="app.modules.notifications.tasks.send_password_reset_email", bind=True, max_retries=2)
def send_password_reset_email(self, email: str, reset_token: str) -> None:
    body = (
        "We received a request to reset your AI Interview Coach password.\n\n"
        f"Reset token: {reset_token}\n\n"
        "If you didn't request this, you can safely ignore this email."
    )
    try:
        asyncio.run(_send_email_async(to=email, subject="Reset your password", body=body))
    except Exception as exc:
        raise self.retry(exc=exc)


@celery_app.task(name="app.modules.notifications.tasks.send_report_ready_email", bind=True, max_retries=2)
def send_report_ready_email(self, email: str, session_id: str) -> None:
    body = (
        "Your AI Interview Coach feedback report is ready.\n\n"
        f"View it at: /interview/{session_id}/report\n\n"
        "Keep practicing -- consistency is what moves your score."
    )
    try:
        asyncio.run(_send_email_async(to=email, subject="Your interview feedback is ready", body=body))
    except Exception as exc:
        raise self.retry(exc=exc)


@celery_app.task(name="app.modules.notifications.tasks.send_practice_reminder_email", bind=True, max_retries=2)
def send_practice_reminder_email(self, email: str) -> None:
    body = (
        "It's been a while since your last mock interview. "
        "Consistent practice is the single biggest driver of improvement -- "
        "log in and run another session today."
    )
    try:
        asyncio.run(_send_email_async(to=email, subject="Time for another practice interview?", body=body))
    except Exception as exc:
        raise self.retry(exc=exc)
