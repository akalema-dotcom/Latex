"""
app/ai/tools/registry.py
========================
Tool registry — maps tool names to instances.
"""
from __future__ import annotations

from typing import Dict, Optional

from app.ai.tools.base import AITool
from app.ai.tools.inventory_tools import (
    CreateOrderFromInquiryTool, TriggerRestockOrderTool, UpdateInventoryTool,
)


_REGISTRY: Dict[str, AITool] = {}


def _register(tool: AITool) -> AITool:
    _REGISTRY[tool.name] = tool
    return tool


# Eagerly register built-in tools.
_register(CreateOrderFromInquiryTool())
_register(TriggerRestockOrderTool())
_register(UpdateInventoryTool())


def get_tool(name: str) -> Optional[AITool]:
    return _REGISTRY.get(name)


def list_tools() -> list[str]:
    return sorted(_REGISTRY.keys())
