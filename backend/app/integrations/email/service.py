"""
app/integrations/email/service.py
=================================
High-level email service: builds templated messages and sends them through
the configured adapter.
"""
from __future__ import annotations

from app.core.config import settings
from app.integrations.email.adapters import get_email_adapter
from app.integrations.email.base import EmailMessage


class EmailService:
    def __init__(self) -> None:
        self.adapter = get_email_adapter()

    def _send(self, to: str, subject: str, body_text: str, body_html: str | None = None) -> bool:
        return self.adapter.send(
            EmailMessage(
                to=to,
                subject=subject,
                body_text=body_text,
                body_html=body_html,
                from_address=settings.EMAIL_FROM_ADDRESS,
                from_name=settings.EMAIL_FROM_NAME,
            )
        )

    def send_email_verification(self, to: str, token: str) -> bool:
        link = f"{settings.FRONTEND_BASE_URL}/auth/verify-email?token={token}"
        body = (
            "Verify your email address\n\n"
            f"Click the link below to verify your account:\n{link}\n\n"
            "If you did not sign up, you can ignore this email."
        )
        return self._send(to, "Verify your email", body)

    def send_password_reset(self, to: str, token: str) -> bool:
        link = f"{settings.FRONTEND_BASE_URL}/auth/reset-password?token={token}"
        body = (
            "Reset your password\n\n"
            f"Click the link below to set a new password:\n{link}\n\n"
            "If you did not request a reset, ignore this email."
        )
        return self._send(to, "Reset your password", body)

    def send_login_notification(self, to: str, ip: str, user_agent: str) -> bool:
        body = (
            "New login to your account\n\n"
            f"IP: {ip}\nUser agent: {user_agent}\n\n"
            "If this wasn't you, please reset your password immediately."
        )
        return self._send(to, "New login", body)

    def send_approval_request(self, to: str, description: str, link: str) -> bool:
        body = (
            "AI action requires your approval\n\n"
            f"{description}\n\nReview and decide: {link}"
        )
        return self._send(to, "Action requires approval", body)

    def send_monthly_report(self, to: str, attachment_text: str) -> bool:
        return self._send(to, "Your monthly business report", attachment_text)


email_service = EmailService()
