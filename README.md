<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11+-3776AB?style=flat&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/FastAPI-0.115-009688?style=flat&logo=fastapi&logoColor=white" alt="FastAPI">
  <img src="https://img.shields.io/badge/license-MIT-green?style=flat" alt="License">
</p>

##  What is Token Relay?

Token Relay is a **production-grade API gateway** that lets you resell Chinese LLM APIs (Qwen, DeepSeek, Zhipu) to global customers. It exposes an **OpenAI-compatible endpoint** so your users can plug in their existing SDKs with zero code changes.

Built for the Southeast Asian B2B SaaS market — deploy on an Alibaba Cloud HK instance and start monetizing Chinese AI models.

##  Architecture

```
User SDK (OpenAI client)
        │
        ▼
   Token Relay API (/v1)
        │
   ┌────┴────┐
   │  Auth    │  Cookie + JWT (dashboard) / API Key (proxy)
   ├─────────┤
   │  Billing │  Pre-auth credit hold → stream → refund delta
   ├─────────┤
   │  Adapter │  OpenAI-compatible → Qwen / DeepSeek / Zhipu
   ├─────────┤
   │  Logging │  Metadata-only (no conversation content stored)
   └────┬────┘
        │
        ▼
   Upstream LLM Provider
```

##  Features

- **OpenAI-compatible** `/v1/chat/completions`, `/v1/models`, `/v1/embeddings`
- **Streaming support** with accurate per-token billing
- **Pre-auth billing** — estimates cost upfront, refunds the delta after streaming completes
- **Multi-provider key rotation** — same provider, multiple keys, priority-based failover
- **Configurable pricing** — global markup ratio + per-model price overrides
- **User portal** — dashboard, API key management, usage analytics, billing history
- **Admin console** — user management, model CRUD, provider key management, system settings
- **Dual auth** — JWT (web dashboard) + API Key (proxy endpoints), Cookie pass-through
- **SQLite dev / PostgreSQL prod** — switch via `DATABASE_URL`
- **Docker** — single-command deploy with PostgreSQL + Redis

##  Quick Start

### Prerequisites
- Python 3.11+
- [uv](https://docs.astral.sh/uv/) or pip

### 1. Clone & Configure

```bash
git clone https://github.com/functionkiller/token-relay.git
cd token-relay
cp .env.example .env
# Edit .env — set SECRET_KEY and ENCRYPTION_KEY
```

### 2. Install & Run

```bash
pip install -r requirements.txt
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 3. Open

| Interface | URL |
|-----------|-----|
| User Portal | http://localhost:8000/login |
| Admin Console | http://localhost:8000/admin/login |
| API Docs (Swagger) | http://localhost:8000/docs |
| Health Check | http://localhost:8000/health |

**Default admin:** `admin@tokenrelay.com` / `admin123456`

### 4. Make Your First API Call

```bash
# 1. Register via the portal or API
curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"dev@example.com","password":"mypassword"}'

# 2. Login to get a cookie
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"dev@example.com","password":"mypassword"}'

# 3. Create an API key (or use the portal UI)
curl -X POST http://localhost:8000/api/users/me/keys \
  -H "Content-Type: application/json" \
  -b "token=<jwt>" \
  -d '{"name":"my-app"}'

# 4. Call the proxy with your API key
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer tsk-your-key-here" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen-turbo",
    "messages": [{"role": "user", "content": "Hello!"}]
  }'
```

### Python SDK

```python
from openai import OpenAI

client = OpenAI(
    api_key="tsk-your-key-here",
    base_url="http://localhost:8000/v1"
)

response = client.chat.completions.create(
    model="qwen-turbo",
    messages=[{"role": "user", "content": "你好，世界"}]
)
print(response.choices[0].message.content)
```

##  Docker

```bash
# Set .env first, then:
docker compose up -d
```

This starts:
- **app** — FastAPI on `:8000`
- **db** — PostgreSQL 16
- **redis** — Redis 7 (rate limiting)

For dev with SQLite:

```bash
docker build -t token-relay .
docker run -p 8000:8000 --env-file .env token-relay
```

##  Supported Models

| Provider | Models |
|----------|--------|
| **Qwen** (通义千问) | qwen-turbo, qwen-plus, qwen-max, qwen-vl-plus |
| **DeepSeek** | deepseek-chat, deepseek-reasoner |
| **Zhipu** (智谱) | glm-4-flash, glm-4, glm-4v |

Add more via the Admin Console → Models or via `POST /api/admin/models`.

##  Pricing Model

1. Each model has a **cost price** (defaults in `proxy_service.py`) and an optional **sell price** (set in Model Config)
2. If sell price is not set, the system applies `markup_percent` (default 15%) on top of cost
3. Billing is **pre-auth**: the system estimates the max cost before calling upstream, holds that amount, then refunds the difference after the actual token count comes back
4. All amounts are stored in **cents** (integers) — no floating point precision issues

##  Billing Flow

```
Request → Estimate (max_tokens × output_price)
       → Atomic balance check + hold
       → Call upstream provider
       → Parse actual token usage
       → Refund delta (estimate - actual)
       → Log transaction + usage
```

If the user's balance is insufficient, the API returns **HTTP 402 Payment Required** *before* any upstream call.

##  Project Structure

```
app/
├── main.py                  # FastAPI entry, lifecycle, middleware
├── config.py                # Pydantic Settings from .env
├── database.py              # SQLAlchemy 2.0 async engine + session
├── api/
│   ├── deps.py              # Auth dependencies (JWT + API Key)
│   ├── auth.py              # Register, login, refresh
│   ├── users.py             # User profile + API key CRUD
│   ├── admin.py             # Admin: users, models, keys, settings, logs
│   ├── billing.py           # Balance + transactions
│   ├── logs.py              # User-scoped usage logs + stats
│   ├── dashboard_router.py  # User portal page routes
│   ├── templates_router.py  # Admin console page routes
│   └── v1/                  # OpenAI-compatible proxy endpoints
│       ├── chat.py          # POST /v1/chat/completions
│       ├── models.py        # GET /v1/models
│       ├── embeddings.py    # POST /v1/embeddings
│       └── router.py        # v1 aggregator
├── models/                  # SQLAlchemy ORM models (7 tables)
├── schemas/                 # Pydantic request/response schemas
├── services/                # Business logic
│   ├── proxy_service.py     # Core billing pipeline + upstream relay
│   ├── auth_service.py      # Registration + login
│   ├── user_service.py      # Profile + API key management
│   ├── admin_service.py     # Admin CRUD operations
│   ├── billing_service.py   # Balance + transaction queries
│   └── analytics_service.py # Stats + usage analytics
├── adapters/                # LLM provider adapters
│   ├── base.py              # Adapter interface
│   ├── openai_adapter.py    # OpenAI-compatible (covers all 3 providers)
│   └── registry.py          # Adapter + key registry
├── security/                # JWT, encryption, API key hashing, rate limiter
├── templates/               # Jinja2 templates
│   ├── admin/               # Dark theme admin console
│   └── user/                # Light theme user portal
└── static/                  # CSS + JS
    ├── base.css             # Design system (both themes)
    ├── user.js              # User portal interactivity
    └── admin.js             # Admin console interactivity
```

##  Database

7 tables: `users`, `api_keys`, `provider_keys`, `model_configs`, `system_settings`, `usage_logs`, `credit_transactions`

- **Dev:** SQLite via `aiosqlite` (zero config)
- **Prod:** PostgreSQL via `asyncpg` (set `DATABASE_URL` in `.env`)

##  Configuration

All via `.env` — see `.env.example` for all options.

| Key | Description |
|-----|-------------|
| `SECRET_KEY` | JWT signing secret (min 32 chars) |
| `ENCRYPTION_KEY` | Fernet key for stored API keys |
| `DATABASE_URL` | SQLite (default) or PostgreSQL |
| `REGISTRATION_OPEN` | `true` / `false` |
| `RATE_LIMIT_PER_USER_PER_MINUTE` | Per-user RPM cap |
| `RATE_LIMIT_GLOBAL_PER_MINUTE` | Global RPM cap |

##  Roadmap

- [ ] Stripe / payment gateway integration
- [ ] Multi-language user portal (EN, ZH, TH, VI)
- [ ] Webhook notifications for balance threshold
- [ ] Per-user rate limiting via admin
- [ ] Model playground (interactive chat tester)
- [ ] Prometheus metrics endpoint
- [ ] RBAC roles beyond user/admin
- [ ] Team / organization accounts

##  License

MIT — see [LICENSE](LICENSE).
