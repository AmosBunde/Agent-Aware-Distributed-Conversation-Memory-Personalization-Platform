# 🧠 Conversation Memory & Personalization Platform

A distributed backend that **stores, retrieves, personalizes, and serves long-term conversational context** for AI agents — with semantic search, per-user profiles, and reliability built in from the first commit.

Five FastAPI microservices behind one gateway, backed by PostgreSQL + pgvector and Redis. Every service ships with unit tests; the golden path is covered by black-box e2e tests that run in CI against the real stack.

---

## Quickstart — one command, zero API keys

```bash
git clone https://github.com/AmosBunde/Agent-Aware-Distributed-Conversation-Memory-Personalization-Platform.git
cd Agent-Aware-Distributed-Conversation-Memory-Personalization-Platform
./scripts/quickstart.sh
```

That's the whole setup. The script checks prerequisites (Docker + Compose v2), writes a working `.env`, builds the five services, waits until everything reports healthy, and prints:

```
▸ All services healthy.
▸ Web console:  http://localhost:8000
▸ API docs:     http://localhost:8000/docs
```

No OpenAI account is needed — the default embedding backend is a deterministic local encoder, so semantic search works offline out of the box. To upgrade retrieval quality later, set `EMBEDDING_BACKEND=openai` and `OPENAI_API_KEY` in `.env`.

Prefer Make? `make dev` does the same bring-up; `make down` stops everything.

## The web console

Open **http://localhost:8000** and you get a dark, terminal-styled console served by the gateway itself (single HTML file, no build step, no CDN):

- **Store memories** and send explicit preference signals from the left rail
- **Context search** shows each retrieved memory with its **similarity / recency / final-score breakdown** as meter bars — the ranking decomposition made visible
- **Context bundle** merges the user profile with top-K memories, exactly what an AI agent would consume before its next turn
- A **live health strip** for all five services and a **request log** with per-call latency at the bottom

---

## Architecture

```
                      ┌──────────────────────────────┐
                      │   AI Agent / your backend    │
                      └──────────────┬───────────────┘
                                     │ REST
                      ┌──────────────▼───────────────┐
                      │      API Gateway :8000       │
                      │  web console · rate limiting │
                      │  circuit breakers · health   │
                      └──┬────────┬────────┬─────┬───┘
                         │        │        │     │
     ┌───────────────────▼──┐ ┌───▼──────┐ ┌▼─────────────┐ ┌▼───────────┐
     │   Memory :8001       │ │ Session  │ │Personalizatn │ │ Embedding  │
     │ store/search/rank    │ │  :8004   │ │    :8002     │ │   :8003    │
     │ pgvector cosine +    │ │ Redis    │ │ profiles ·   │ │ local hash │
     │ recency re-ranking   │ │ TTL      │ │ signals ·    │ │ or OpenAI  │
     │                      │ │ state    │ │ bundles      │ │ vectors    │
     └──────────┬───────────┘ └────┬─────┘ └──────┬───────┘ └────────────┘
                │                  │              │
     ┌──────────▼──────────┐ ┌─────▼────┐ ┌───────▼───────┐
     │ PostgreSQL 16       │ │ Redis 7  │ │ PostgreSQL    │
     │ + pgvector (IVFFlat)│ │ (TTL)    │ │ (signals)     │
     └─────────────────────┘ └──────────┘ └───────────────┘
```

**Request flow for a typical AI turn:**
1. Agent calls `GET /api/v1/personalization/{user}/context-bundle?query=...`
2. Personalization builds the profile (history aggregation + explicit signals) and asks the memory service for top-K relevant memories
3. Memory service embeds the query, runs pgvector cosine search, re-ranks by `0.75·similarity + 0.25·recency`
4. Agent gets one bundle: who this user is + what's relevant right now

**Reliability at the gateway:** per-user token-bucket rate limiting (429 + `Retry-After`), and a circuit breaker per upstream — after N consecutive failures the circuit opens and fails fast (503) instead of piling requests onto a struggling service; a half-open probe closes it again when the upstream recovers. One service melting down never takes the others with it.

---

## Project structure

```
├── services/
│   ├── gateway/          # Public entrypoint: routing, rate limit, circuit breaker, web console
│   ├── memory/           # pgvector storage, semantic search, recency-aware ranking
│   ├── personalization/  # Profiles, preference signals, context bundles
│   ├── session/          # Redis-backed short-term state with TTL
│   └── embedding/        # Text → 384-dim vectors (local zero-key backend or OpenAI)
│       └── <service>/
│           ├── app/          # config.py, main.py (app factory), domain modules
│           ├── tests/        # unit tests, no infrastructure needed
│           ├── Dockerfile
│           └── requirements.txt
├── shared/               # convmem-shared: settings, wire schemas, HTTP client, health router
├── tests/
│   ├── integration/      # cross-service tests against the running stack
│   └── e2e/              # black-box golden path through the gateway only
├── scripts/              # quickstart.sh, initdb.sql (pgvector schema + indexes)
├── .github/workflows/    # CI: lint → unit → compose e2e smoke
├── docker-compose.yml
└── Makefile
```

Every service follows the same pattern: a `create_app()` factory with injected dependencies (repository/store/gateway protocols), a production implementation (Postgres/Redis/HTTP) and an in-memory implementation for tests. The shared package keeps wire schemas single-sourced so services can't drift.

---

## API reference

All endpoints are served through the gateway on port 8000. Write operations take the user from the `X-User-ID` header.

### Memories

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/v1/memories` | Store a conversation turn (content is embedded automatically) |
| `GET` | `/api/v1/memories/{user_id}` | Paginated history, newest first (`limit`, `offset`) |
| `GET` | `/api/v1/memories/{user_id}/context?query=&top_k=` | Semantic search with similarity/recency/score breakdown |
| `PATCH` | `/api/v1/memories/{user_id}/{memory_id}` | Merge metadata into a memory |
| `DELETE` | `/api/v1/memories/{user_id}/{memory_id}` | Delete a memory |
| `DELETE` | `/api/v1/memories/{user_id}` | **Wipe every memory for a user** (right to be forgotten) |

### Personalization

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/v1/personalization/{user_id}/profile` | Preferences, top intents, activity stats |
| `POST` | `/api/v1/personalization/{user_id}/signal` | Upsert an explicit preference (`{"key":"tone","value":"concise"}`) |
| `GET` | `/api/v1/personalization/{user_id}/context-bundle?query=` | Profile + top-K relevant memories in one payload |
| `DELETE` | `/api/v1/personalization/{user_id}/signals` | Clear all explicit preference signals for a user |

### Sessions

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/v1/sessions` | Create a session (default TTL 30 min) |
| `GET` | `/api/v1/sessions/{session_id}` | Get session state; refreshes the TTL |
| `PATCH` | `/api/v1/sessions/{session_id}` | Merge state keys |
| `DELETE` | `/api/v1/sessions/{session_id}` | End session; flushes final state to long-term memory (best-effort, reported as `flushed`) |

### Embeddings & health

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/v1/embed` | Batch text → unit vectors (`{"texts": ["..."]}`) |
| `GET` | `/healthz` | Aggregate health of all services + circuit states |

Example — store a memory and retrieve context:

```bash
curl -X POST http://localhost:8000/api/v1/memories \
  -H "Content-Type: application/json" -H "X-User-ID: user-123" \
  -d '{"session_id":"sess-abc","role":"user",
       "content":"I prefer concise answers. I am a senior Python engineer.",
       "metadata":{"intent":"preference_setting"}}'

curl "http://localhost:8000/api/v1/memories/user-123/context?query=python+help&top_k=5"
```

---

## Configuration

Everything is environment-driven (see `.env.example`, which works as-is):

| Variable | Default | Purpose |
|---|---|---|
| `EMBEDDING_BACKEND` | `local` | `local` (deterministic, zero keys) or `openai` |
| `GATEWAY_API_KEY` | _empty_ | When set, every API request must send it as `X-API-Key` (the console has a key field) |
| `JWT_SECRET` / `JWT_JWKS_URL` | _empty_ | Per-user auth: require `Authorization: Bearer`; the token's `sub` claim becomes the user id upstream (overrides any client-sent `X-User-ID`). HS256 secret or OIDC JWKS. Optional `JWT_ISSUER`/`JWT_AUDIENCE` checks |
| `OPENAI_API_KEY` | _empty_ | Only needed for the OpenAI backend |
| `SESSION_TTL_SECONDS` | `1800` | Session lifetime; reads slide the window |
| `RATE_LIMIT_RPS` / `RATE_LIMIT_BURST` | `20` / `40` | Per-user gateway rate limit |
| `CIRCUIT_FAILURE_THRESHOLD` | `5` | Consecutive failures before a circuit opens |
| `CIRCUIT_RESET_SECONDS` | `30` | Cooldown before a half-open probe |
| `*_HOST_PORT` | `8000`–`8004`, `5432`, `6379` | Remap host ports if another project uses them |

---

## Testing

```bash
make test-unit          # 70 unit tests, no infrastructure, ~2s
make test-integration   # cross-service tests   (requires: make dev)
make test-e2e           # golden path via gateway (requires: make dev)
make lint               # ruff
make coverage           # HTML coverage report
```

CI runs lint + unit on every PR, then boots the full compose stack and runs the integration/e2e suites against it.

---

## Deployment

Ranked easiest-first:

### 1. Docker Compose (recommended start)
What the quickstart does. Suitable for development, demos, and small single-host deployments:

```bash
./scripts/quickstart.sh        # or: make dev
```

### 2. Single VM
The same compose file runs unchanged on any VM with Docker (EC2, Droplet, Compute Engine, Hetzner):

```bash
ssh your-vm 'git clone <repo> && cd <repo> && ./scripts/quickstart.sh'
```

Then put a TLS reverse proxy (Caddy or nginx) in front of port 8000 — it's the only port you expose; databases and internal services stay on the compose network, and host-published dev ports bind to loopback only. Set a real `POSTGRES_PASSWORD` and a `GATEWAY_API_KEY` in `.env`.

### 3. Kubernetes / managed cloud
The services are stateless 12-factor containers (config via env, health endpoints, one process per container), so they map directly onto any k8s platform: build the five Dockerfiles, point the `*_SERVICE_URL` env vars at cluster DNS, and use managed Postgres (with pgvector) + Redis. Helm charts and Terraform modules are tracked as future work in the issues.

---

## Observability

Every service exposes Prometheus metrics at `/metrics` (request rate, latency histograms, and error counts, labelled by route template). To get the full stack — Prometheus, a provisioned Grafana dashboard, and Jaeger tracing:

```bash
# in .env: OTEL_EXPORTER_OTLP_ENDPOINT=http://jaeger:4318
docker compose --profile observability up -d
```

| Tool | URL | What you get |
|---|---|---|
| Grafana | http://localhost:3001 (admin/admin) | Request rate, p95 latency, 5xx rate, top endpoints — per service |
| Prometheus | http://localhost:9090 | Raw metrics from all five services |
| Jaeger | http://localhost:16686 | Distributed traces across gateway → service → dependency |

## Events

Services publish `memory.stored`, `memory.wiped`, and `session.ended` to `convmem.events.<topic>`. Publishing is best-effort and never fails the triggering request. Two transports, selected by `EVENT_BUS`:

- **`redis`** (default) — Redis Streams, zero extra infrastructure; consume with `XREAD`/consumer groups; capped at ~10k entries per topic
- **`kafka`** — `docker compose --profile kafka up -d` starts a single-node KRaft broker; set `EVENT_BUS=kafka`. Same topics, standard Kafka consumers.

## Schema migrations

Numbered SQL files in `scripts/migrations/` are the single source of truth for the database schema. The memory service applies pending migrations on startup (transactional, advisory-locked, recorded in `schema_migrations`), so schema changes reach existing databases — not just fresh volumes.

## Roadmap

Deliberately not in this codebase yet — each lands with tests when it lands:

- Helm chart and Terraform modules for AWS/GCP/Azure
- Sentence-transformers embedding backend (the `EmbeddingBackend` protocol is ready for it)

## Development workflow

Work is organized as GitHub issues (#1–#8), one branch and one PR per issue, stacked in order. Each PR describes what it does, why it's shaped that way, and how it was verified. Unit tests use in-memory implementations of every storage protocol, so `pytest` is fast and infrastructure-free; the compose stack is only needed for integration/e2e.
