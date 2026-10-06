"""
app/integrations/email/adapters.py
==================================
Concrete email adapters: console (dev), smtp (prod), noop (testing).
"""
from __future__ import annotations

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.core.config import settings
from app.integrations.email.base import EmailAdapter, EmailMessage


class ConsoleEmailAdapter(EmailAdapter):
    """Prints emails to stdout — useful for local development."""

    name = "console"

    def send(self, message: EmailMessage) -> bool:
        print("\n=========== EMAIL ===========")
        print(f"To:      {message.to}")
        print(f"From:    {message.from_address or settings.EMAIL_FROM_ADDRESS}")
        print(f"Subject: {message.subject}")
        print("------ body ------")
        print(message.body_text)
        print("=============================\n")
        return True


class NoopEmailAdapter(EmailAdapter):
    """Discards every email — useful in tests."""

    name = "noop"

    def send(self, message: EmailMessage) -> bool:
        return True


class SmtpEmailAdapter(EmailAdapter):
    """Sends real email via SMTP."""

    name = "smtp"

    def send(self, message: EmailMessage) -> bool:
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = message.subject
            msg["From"] = (
                f"{message.from_name or settings.EMAIL_FROM_NAME} "
                f"<{message.from_address or settings.EMAIL_FROM_ADDRESS}>"
            )
            msg["To"] = message.to
            msg.attach(MIMEText(message.body_text, "plain"))
            if message.body_html:
                msg.attach(MIMEText(message.body_html, "html"))

            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
                if settings.SMTP_USE_TLS:
                    server.starttls()
                if settings.SMTP_USERNAME and settings.SMTP_PASSWORD:
                    server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
                server.send_message(msg)
            return True
        except Exception as exc:
            print(f"[SMTP] Failed to send email to {message.to}: {exc}")
            return False


def get_email_adapter() -> EmailAdapter:
    provider = settings.EMAIL_PROVIDER.lower()
    mapping = {
        "console": ConsoleEmailAdapter,
        "noop": NoopEmailAdapter,
        "smtp": SmtpEmailAdapter,
    }
    cls = mapping.get(provider, ConsoleEmailAdapter)
    return cls()
