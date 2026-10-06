"""
app/integrations/email/base.py
==============================
Email provider abstraction.

The system never hard-codes a single email provider. The actual provider
is selected by the EMAIL_PROVIDER env var (console | smtp | noop).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class EmailMessage:
    to: str
    subject: str
    body_text: str
    body_html: Optional[str] = None
    from_address: Optional[str] = None
    from_name: Optional[str] = None


class EmailAdapter(ABC):
    """Interface for every email provider."""

    name: str = "abstract"

    @abstractmethod
    def send(self, message: EmailMessage) -> bool:
        """Return True on success, False on failure."""
        raise NotImplementedError
