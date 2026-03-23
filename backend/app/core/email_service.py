"""
Centralized Email Alert Service for BTC-TEST Platform.

Non-blocking email sending via background threads.
Uses stdlib smtplib — zero external dependencies.
"""

import logging
import smtplib
import threading
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr

from app.core.config import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Low-level sender (runs in background thread)
# ---------------------------------------------------------------------------


def _send_smtp(recipients: list[str], subject: str, html_body: str) -> None:
    """Send an email via SMTP. Called inside a daemon thread."""
    if not settings.emails_enabled:
        logger.info("Emails disabled (SMTP not configured). Skipping.")
        return

    from_email = str(settings.EMAILS_FROM_EMAIL)
    from_name = settings.EMAILS_FROM_NAME or "BTC-TEST"

    # Validate recipients
    valid_recipients = [r for r in recipients if r and "@" in r]
    if not valid_recipients:
        logger.warning("No valid recipients. Skipping email.")
        return

    msg = MIMEMultipart("alternative")
    msg["From"] = formataddr((from_name, from_email))
    msg["To"] = ", ".join(valid_recipients)
    msg["Subject"] = subject
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    max_attempts = 2
    for attempt in range(1, max_attempts + 1):
        try:
            if settings.SMTP_SSL:
                server = smtplib.SMTP_SSL(settings.SMTP_HOST or "", settings.SMTP_PORT)
            else:
                server = smtplib.SMTP(settings.SMTP_HOST or "", settings.SMTP_PORT)
                if settings.SMTP_TLS:
                    server.starttls()

            if settings.SMTP_USER and settings.SMTP_PASSWORD:
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)

            server.sendmail(from_email, valid_recipients, msg.as_string())
            server.quit()
            logger.info(
                f"Email sent: '{subject}' → {len(valid_recipients)} recipient(s)"
            )
            return
        except Exception as e:
            logger.error(f"Email send attempt {attempt}/{max_attempts} failed: {e}")
            if attempt < max_attempts:
                time.sleep(3)

    logger.error(f"Email permanently failed after {max_attempts} attempts: '{subject}'")


def send_email_background(recipients: list[str], subject: str, html_body: str) -> None:
    """Fire-and-forget email via daemon thread."""
    thread = threading.Thread(
        target=_send_smtp,
        args=(recipients, subject, html_body),
        daemon=True,
    )
    thread.start()


# ---------------------------------------------------------------------------
# Superuser email helper
# ---------------------------------------------------------------------------


def _superuser_email() -> str:
    return str(settings.FIRST_SUPERUSER)


# ---------------------------------------------------------------------------
# A. TEST SCHEDULED ALERT
# ---------------------------------------------------------------------------


def send_test_scheduled_alert(
    teacher_email: str,
    test_title: str,
    scheduled_at: str | None,
    subjects: list[str],
    total_questions: int,
    marking_scheme: str,
) -> None:
    recipients = [teacher_email, _superuser_email()]
    subject = "BTC-TEST | Test Scheduled"
    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:auto;padding:24px;background:#111;color:#eee;border-radius:12px;">
        <h2 style="color:#a855f7;margin-top:0;">📋 Test Scheduled</h2>
        <table style="width:100%;border-collapse:collapse;margin-top:16px;">
            <tr><td style="padding:8px 0;color:#999;">Title</td><td style="padding:8px 0;font-weight:bold;">{test_title}</td></tr>
            <tr><td style="padding:8px 0;color:#999;">Scheduled</td><td style="padding:8px 0;">{scheduled_at or "Immediate"}</td></tr>
            <tr><td style="padding:8px 0;color:#999;">Subject(s)</td><td style="padding:8px 0;">{", ".join(subjects) if subjects else "General"}</td></tr>
            <tr><td style="padding:8px 0;color:#999;">Questions</td><td style="padding:8px 0;">{total_questions}</td></tr>
            <tr><td style="padding:8px 0;color:#999;">Marking</td><td style="padding:8px 0;">{marking_scheme}</td></tr>
        </table>
        <hr style="border-color:#333;margin:24px 0 12px;">
        <p style="font-size:12px;color:#666;">Bright Tutorials Centre — Automated Alert</p>
    </div>
    """
    send_email_background(recipients, subject, html)


# ---------------------------------------------------------------------------
# B. STUDENT ATTEMPT STARTED ALERT
# ---------------------------------------------------------------------------


def send_attempt_started_alert(
    teacher_email: str,
    student_name: str,
    student_email: str,
    test_title: str,
    login_time: str,
) -> None:
    recipients = [teacher_email, _superuser_email()]
    subject = "BTC-TEST | Student Attempt Started"
    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:auto;padding:24px;background:#111;color:#eee;border-radius:12px;">
        <h2 style="color:#22c55e;margin-top:0;">🎓 Student Logged Into Test</h2>
        <table style="width:100%;border-collapse:collapse;margin-top:16px;">
            <tr><td style="padding:8px 0;color:#999;">Student</td><td style="padding:8px 0;font-weight:bold;">{student_name}</td></tr>
            <tr><td style="padding:8px 0;color:#999;">Email</td><td style="padding:8px 0;">{student_email}</td></tr>
            <tr><td style="padding:8px 0;color:#999;">Test</td><td style="padding:8px 0;">{test_title}</td></tr>
            <tr><td style="padding:8px 0;color:#999;">Login Time</td><td style="padding:8px 0;">{login_time}</td></tr>
        </table>
        <hr style="border-color:#333;margin:24px 0 12px;">
        <p style="font-size:12px;color:#666;">Bright Tutorials Centre — Automated Alert</p>
    </div>
    """
    send_email_background(recipients, subject, html)


# ---------------------------------------------------------------------------
# C. PAYMENT SUCCESS ALERT
# ---------------------------------------------------------------------------


def send_payment_success_alert(
    student_name: str,
    student_email: str,
    standard: str | None,
    amount: float,
    transaction_id: str,
    method: str = "Razorpay",
) -> None:
    recipients = [_superuser_email()]  # Superuser ONLY
    subject = "BTC-TEST | Payment Received"
    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:auto;padding:24px;background:#111;color:#eee;border-radius:12px;">
        <h2 style="color:#facc15;margin-top:0;">💰 Payment Received</h2>
        <table style="width:100%;border-collapse:collapse;margin-top:16px;">
            <tr><td style="padding:8px 0;color:#999;">Student</td><td style="padding:8px 0;font-weight:bold;">{student_name}</td></tr>
            <tr><td style="padding:8px 0;color:#999;">Email</td><td style="padding:8px 0;">{student_email}</td></tr>
            <tr><td style="padding:8px 0;color:#999;">Class</td><td style="padding:8px 0;">{standard or "N/A"}</td></tr>
            <tr><td style="padding:8px 0;color:#999;">Amount</td><td style="padding:8px 0;">₹{amount}</td></tr>
            <tr><td style="padding:8px 0;color:#999;">Transaction ID</td><td style="padding:8px 0;font-family:monospace;">{transaction_id}</td></tr>
            <tr><td style="padding:8px 0;color:#999;">Method</td><td style="padding:8px 0;">{method}</td></tr>
        </table>
        <hr style="border-color:#333;margin:24px 0 12px;">
        <p style="font-size:12px;color:#666;">Bright Tutorials Centre — Automated Alert</p>
    </div>
    """
    send_email_background(recipients, subject, html)
