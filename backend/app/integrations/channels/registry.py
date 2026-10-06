"""
app/integrations/channels/registry.py
=====================================
Channel registry. Concrete adapters (WhatsApp Cloud API, Meta Graph API,
Gmail API, Twilio SMS, …) would be registered here. For now we expose a
registry that can be extended per organization.
"""
from __future__ import annotations

from typing import Dict, Optional, Type

from app.integrations.channels.base import ChannelAdapter


_REGISTRY: Dict[str, Type[ChannelAdapter]] = {}


def register_channel(name: str, adapter_cls: Type[ChannelAdapter]) -> None:
    _REGISTRY[name] = adapter_cls


def get_channel_adapter(name: str) -> Optional[ChannelAdapter]:
    """Instantiate a registered channel adapter. Returns None if missing."""
    cls = _REGISTRY.get(name)
    return cls() if cls else None


def available_channels() -> list[str]:
    return list(_REGISTRY.keys())
