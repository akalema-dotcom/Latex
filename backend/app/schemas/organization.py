"""
app/schemas/organization.py
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class OrganizationCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    slug: str = Field(..., min_length=2, max_length=100, pattern=r"^[a-z0-9][a-z0-9-]*[a-z0-9]$")
    description: Optional[str] = None
    country_code: str = Field(default="US", min_length=2, max_length=2)
    base_currency: str = Field(default="USD", min_length=3, max_length=3)
    locale: str = Field(default="en-US", max_length=10)
    timezone: str = Field(default="UTC", max_length=64)
    tax_rate_pct: int = Field(default=0, ge=0, le=100)


class OrganizationUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    country_code: Optional[str] = None
    base_currency: Optional[str] = None
    locale: Optional[str] = None
    timezone: Optional[str] = None
    tax_rate_pct: Optional[int] = Field(default=None, ge=0, le=100)
    is_active: Optional[bool] = None
    plan: Optional[str] = None


class OrganizationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    slug: str
    description: Optional[str]
    country_code: str
    base_currency: str
    locale: str
    timezone: str
    tax_rate_pct: int
    is_active: bool
    plan: str
    created_at: datetime
    updated_at: datetime
