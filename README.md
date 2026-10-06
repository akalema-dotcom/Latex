# AI Business Workforce

A production-oriented, multi-tenant, multi-currency backend + dashboard for
businesses anywhere in the world.

> **USD is the system default currency — NOT the only currency.**
> Every organization selects its own country, currency, locale, and timezone.

## Repository layout

```
.
├── backend/      FastAPI + SQLAlchemy 2.0 + Alembic + Pydantic v2
├── frontend/     Next.js dashboard shell (Foundation V1)
└── docker-compose.yml
```

## AI Workforce

The platform is built around a workforce of specialized AI agents:

| Agent | Domain | Responsibility |
|---|---|---|
| ATLAS | Manager | Coordinates workflows across the workforce |
| NOVA | Sales | Turns customer inquiries into orders |
| ARIA | Support | Handles customer service across channels |
| STOCK | Inventory | Tracks stock levels and demand |
| MERCURY | Procurement | Manages suppliers and purchase orders |
| LEDGER | Finance | Tracks revenue, expenses, and profit |
| INSIGHT | Reports | Generates monthly and yearly business reports |
| PULSE | Communications | Connects WhatsApp, Messenger, Instagram, Gmail |
| ORBIT | CRM | Customer intelligence |
| SENTINEL | Security | Monitors risk and audit logs |

Every AI action is:
- authenticated and authorized (RBAC)
- scoped to a single organization (multi-tenant isolation)
- audit-logged
- subject to human approval when sensitive (e.g. orders above a threshold)

## Backend (`/backend`)

### Highlights

- **70+ ISO 4217 currencies** seeded from a static catalog (USD, UGX, KES, EUR, GBP, JPY, INR, CNY, AED, …)
- **Decimal-only money handling** — financial calculations NEVER use Python floats
- **Pluggable exchange-rate providers** (mock / manual / Frankfurter / OpenExchangeRates) with stale-rate detection
- **JWT auth** with refresh-token rotation, revocation, and email verification
- **RBAC** with 7 roles (OWNER, ADMIN, MANAGER, EMPLOYEE, ACCOUNTANT, VIEWER, AI_AGENT) and 30+ granular permissions
- **Multi-tenant isolation** enforced at the service layer (not just the frontend)
- **AI agent framework** — agents call tools, tools call services, services touch the DB. Agents never manipulate tables directly.
- **Sensitive AI actions require human approval** via `/api/v1/ai/approvals`
- **Audit logging** for 30+ canonical event types (USER_LOGIN, ORDER_CREATED, AI_ACTION_COMPLETED, …)
- **Alembic migrations** — deployable from a clean installation
- **PostgreSQL-ready** (SQLite for dev)
- **OpenAPI documentation** at `/docs`

### Built-in AI tools

- `create_order_from_inquiry` — auto-create an order from a customer inquiry (requires approval if total > 1000 base currency)
- `trigger_restock_order` — auto-create a draft purchase order when stock drops below the reorder threshold
- `update_inventory` — adjust inventory count + record an immutable movement

### Architecture

```
API (FastAPI routers)
   ↓
Schemas (Pydantic v2)
   ↓
Services (business logic, transactions, audit)
   ↓
Models / Repositories (SQLAlchemy 2.0 ORM)
   ↓
Database (PostgreSQL production / SQLite dev)
```

AI layer never touches the DB directly:

```
AI Agent
   ↓
Tool (backend/app/ai/tools/*)
   ↓
Service
   ↓
Database
```

### Quick start

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Edit .env: set SECRET_KEY and JWT_SECRET_KEY to long random strings

alembic upgrade head                          # Apply DB migrations
uvicorn app.main:app --reload --port 8000     # Start the API

# Open http://localhost:8000/docs for the interactive OpenAPI docs
```

### Tests

```bash
cd backend
python -m pytest tests/                       # 51 pytest tests
python scripts/smoke_test.py                  # 43 end-to-end smoke checks
python scripts/live_demo.py                   # Live demo against a running server
```

### API v1 endpoints

```
# Auth
POST   /api/v1/auth/register
POST   /api/v1/auth/login
POST   /api/v1/auth/refresh
POST   /api/v1/auth/logout
GET    /api/v1/auth/me
POST   /api/v1/auth/verify-email
POST   /api/v1/auth/forgot-password
POST   /api/v1/auth/reset-password
POST   /api/v1/auth/change-password
GET    /api/v1/auth/sessions
DELETE /api/v1/auth/sessions/{session_id}

# Organizations
POST   /api/v1/organizations
GET    /api/v1/organizations/me
PATCH  /api/v1/organizations/me

# Currencies
GET    /api/v1/currencies
GET    /api/v1/currencies/{code}
GET    /api/v1/exchange-rates
GET    /api/v1/exchange-rates/{base}/{quote}
POST   /api/v1/currency/convert

# Finance
GET    /api/v1/finance/reports/profit-loss?year=2026&month=10
GET    /api/v1/finance/reports/monthly/{year}/{month}
GET    /api/v1/finance/reports/yearly/{year}

# AI agents
GET    /api/v1/ai/agents
POST   /api/v1/ai/agents
POST   /api/v1/ai/tasks
GET    /api/v1/ai/tasks/{task_id}
GET    /api/v1/ai/approvals/pending
POST   /api/v1/ai/approvals/{approval_id}/decide

# Audit
GET    /api/v1/audit-logs
```

### Configuration

See `backend/.env.example` for the full list. Key variables:

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./ai_business_workforce.db` | SQLAlchemy URL. Use `postgresql+psycopg2://...` for prod |
| `SECRET_KEY` | (required) | Long random string for general app secrets |
| `JWT_SECRET_KEY` | (required) | Long random string for JWT signing |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | Access token lifetime |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `30` | Refresh token lifetime |
| `EXCHANGE_RATE_PROVIDER` | `mock` | `mock` / `manual` / `frankfurter` / `openexchangerates` |
| `EMAIL_PROVIDER` | `console` | `console` / `smtp` / `noop` |
| `CORS_ORIGINS` | `http://localhost:3000,http://localhost:5173` | Comma-separated allowed origins |

## Frontend (`/frontend`)

Next.js + TypeScript dashboard shell (Foundation V1). Currently displays the
AI workforce roster and a business command center layout. The UI is ready to
be wired to the backend REST API.

## Engineering rules

1. **No fake implementations** — every endpoint performs real work.
2. **No business logic in route handlers** — routes call services.
3. **No floats for money** — `Decimal` everywhere, with a `Money` value object.
4. **No direct DB access from AI agents** — agents use tools → services → DB.
5. **Tenant isolation in the service layer**, not only in the frontend.
6. **Secrets via env vars** — never committed. `.env.example` has placeholders.
7. **Alembic for migrations** — `Base.metadata.create_all()` is dev-only.
8. **PostgreSQL-ready** — dev uses SQLite; prod uses PostgreSQL via `DATABASE_URL`.
9. **Versioned API** — all routes under `/api/v1`. `/api/v2` can be added later.
10. **OpenAPI documentation** — FastAPI auto-generates `/docs` and `/openapi.json`.

## License

Proprietary — © AI Business Workforce. All rights reserved.
