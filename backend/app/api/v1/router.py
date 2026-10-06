"""
app/api/v1/router.py
====================
Aggregates every v1 endpoint router under the /api/v1 prefix.
"""
from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.endpoints import auth, currencies, organizations, finance, ai_agents, audit_logs

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(currencies.router)
api_router.include_router(organizations.router)
api_router.include_router(finance.router)
api_router.include_router(ai_agents.router)
api_router.include_router(audit_logs.router)
