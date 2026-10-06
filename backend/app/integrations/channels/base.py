"""
app/integrations/channels/base.py
=================================
Channel adapter abstraction (WhatsApp / Messenger / Instagram / Gmail / SMS).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class InboundMessage:
    organization_id: str
    channel_type: str          # whatsapp | gmail | ...
    external_conversation_id: str
    external_message_id: str
    sender_handle: str
    sender_name: Optional[str]
    body: str
    subject: Optional[str] = None


@dataclass
class OutboundResult:
    success: bool
    external_message_id: Optional[str] = None
    error: Optional[str] = None


class ChannelAdapter(ABC):
    """Each channel (WhatsApp, Gmail, Messenger, …) implements this."""

    channel_type: str = "abstract"

    @abstractmethod
    def send_message(
        self,
        to: str,
        body: str,
        organization_id: str,
        conversation_ref: Optional[str] = None,
    ) -> OutboundResult:
        raise NotImplementedError

    @abstractmethod
    def list_conversations(self, organization_id: str) -> list[dict]:
        raise NotImplementedError
