"""
app/models/channel.py
=====================
Conversations & messages across channels (WhatsApp, Messenger, Instagram,
Gmail, SMS, web chat). The actual channel adapters live under
app/integrations/channels/.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import String, ForeignKey, DateTime, Text, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models._mixins import UUIDPkMixin, TimestampMixin, OrganizationFkMixin


CHANNEL_TYPES = ("whatsapp", "messenger", "instagram", "gmail", "sms", "web", "telegram", "twitter")


class Channel(Base, UUIDPkMixin, TimestampMixin, OrganizationFkMixin):
    """A configured channel connection for an organization."""

    __tablename__ = "channels"
    __table_args__ = (Index("ix_channels_org_type", "organization_id", "type"),)

    name: Mapped[str] = mapped_column(String(64), nullable=False)
    type: Mapped[str] = mapped_column(String(16), nullable=False)
    # Encrypted credentials placeholder — never store plaintext in DB
    credentials_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    # Optional AI agent bound to answer messages on this channel
    ai_agent_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("ai_agents.id"), nullable=True)

    conversations = relationship("Conversation", back_populates="channel")


class Conversation(Base, UUIDPkMixin, TimestampMixin, OrganizationFkMixin):
    __tablename__ = "conversations"
    __table_args__ = (Index("ix_conversations_org_channel", "organization_id", "channel_id"),)

    channel_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("channels.id", ondelete="CASCADE"), index=True, nullable=False,
    )
    external_id: Mapped[str] = mapped_column(String(255), nullable=False)
    customer_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("customers.id"), nullable=True)
    customer_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    customer_handle: Mapped[str | None] = mapped_column(String(255), nullable=True)
    subject: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_handled_by_ai: Mapped[bool] = mapped_column(default=False, nullable=False)

    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    channel = relationship("Channel", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")


class Message(Base, UUIDPkMixin, TimestampMixin, OrganizationFkMixin):
    __tablename__ = "messages"
    __table_args__ = (Index("ix_messages_org_conv", "organization_id", "conversation_id"),)

    conversation_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("conversations.id", ondelete="CASCADE"), index=True, nullable=False,
    )
    direction: Mapped[str] = mapped_column(String(4), nullable=False)  # IN | OUT
    sender: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    external_message_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sent_by_user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    sent_by_agent_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("ai_agents.id"), nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    conversation = relationship("Conversation", back_populates="messages")
