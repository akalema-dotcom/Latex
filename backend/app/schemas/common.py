"""
app/schemas/common.py
"""
from __future__ import annotations

from typing import Generic, TypeVar, Optional, List
from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class MessageOut(ORMModel):
    message: str


class ErrorOut(ORMModel):
    detail: str
    code: Optional[str] = None


class PaginatedOut(ORMModel, Generic[T]):
    items: List[T]
    total: int
    page: int = 1
    page_size: int = 50
