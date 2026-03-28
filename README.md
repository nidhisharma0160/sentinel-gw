# Sentinel-GW — High-Throughput AI Observability Gateway

A production-grade AI proxy gateway built with FastAPI that intercepts, validates, monitors, and logs every LLM API call. Designed to demonstrate distributed systems patterns used at scale: distributed tracing, Prometheus instrumentation, circuit breaking, and audit logging.

---

## Architecture

```
Client Request
      │
      ▼
┌─────────────────────────────────────────┐
│             FastAPI Gateway             │
│                                         │
│  1. TraceMiddleware  → stamps UUID      │
│  2. PrometheusMiddleware → times req    │
│  3. GuardrailEngine  → validates        │
│  4. CircuitBreaker   → checks state     │
│  5. Proxy            → forwards         │
│  6. SpendLogger      → writes DB row    │
└─────────────────────────────────────────┘
      │              │            │
      ▼              ▼            ▼
 Upstream LLM   PostgreSQL     Redis
 (Anthropic)    (SpendLogs)  (Circuit state)
      │
      ▼
 Prometheus → Grafana Dashboard
```

Every request gets a unique `trace_id` (UUID) that appears in:
- Console logs
- PostgreSQL SpendLogs table
- Prometheus metric labels
- Response headers (`x-trace-id`)

This means you can take any trace ID from anywhere in the system and reconstruct the full lifecycle of that request.

---

## Tech Stack

| Layer | Technology |
|---|---|
| API framework | FastAPI + Uvicorn |
| Observability | Prometheus + Grafana |
| Reliability | Redis circuit breaker |
| Audit logging | PostgreSQL + SQLAlchemy (async) |
| Validation | Pydantic v2 |
| HTTP client | httpx (async) |
| Containerisation | Docker + Docker Compose |

---

## Features

### Distributed Tracing
Every request is stamped with a UUID `trace_id` at the middleware layer before any business logic runs. The same ID propagates to console logs, database rows, and upstream headers — enabling end-to-end request correlation across every layer of the stack.

### Prometheus Instrumentation
Custom middleware tracks request latency using configurable histogram buckets (read from environment variables at startup), request counts, and guardrail violation counts — all labelled by endpoint, HTTP method, and status code. Metrics are exposed at `/metrics` and scraped by Prometheus every 5 seconds.

### Guardrail Engine
A policy registry that validates every incoming LLM request against named rules before forwarding. Ships with three default policies:
- `model_allowlist` — only Claude models are permitted
- `max_token_cap` — token requests capped at 4096
- `no_system_role_only` — at least one user message must be present

All policy exceptions are caught and returned as structured `422` responses. No silent failures.

### Redis Circuit Breaker
A three-state state machine (CLOSED → OPEN → HALF-OPEN) backed by Redis so state survives container restarts. Trips after 5 consecutive upstream failures, rejects requests immediately for 30 seconds, then enters HALF-OPEN to test recovery. Reduces cascading failures during upstream outages.

### PostgreSQL SpendLogs
Every proxied request writes an audit row to Postgres containing the trace ID, model name, token counts, latency, and status code. Enables cost attribution, abuse detection, and historical debugging — query any trace ID to reconstruct the full request lifecycle.

---

## Project Structure

```
sentinel/
├── app/
│   ├── api/
│   │   ├── guardrails.py       # GET/POST /guardrails
│   │   └── proxy.py            # POST /v1/proxy
│   ├── core/
│   │   ├── circuit_breaker.py  # Redis state machine
│   │   ├── config.py           # Pydantic settings
│   │   ├── database.py         # Async SQLAlchemy engine
│   │   ├── guardrails.py       # Policy registry
│   │   ├── metrics.py          # Prometheus definitions
│   │   ├── policies.py         # Default guardrail policies
│   │   ├── spend_logger.py     # Async DB writer
│   │   └── trace.py            # UUID generator
│   ├── middleware/
│   │   ├── prometheus.py       # Latency + count tracking
│   │   └── trace.py            # Trace ID stamping
│   ├── models/
│   │   ├── schemas.py          # Pydantic request schema
│   │   └── spend_log.py        # SQLAlchemy table model
│   └── main.py                 # App factory + routes
├── Dockerfile
├── docker-compose.yml
├── prometheus.yml
├── requirements.txt
└── .env
```

---

## Getting Started

### Prerequisites
- Docker Desktop installed and running
- Git

### Clone and run

```bash
git clone https://github.com/YOUR_USERNAME/sentinel-gw.git
cd sentinel-gw
```

Create your `.env` file:

```bash
cp .env.example .env
```

Boot the full stack (FastAPI + PostgreSQL + Redis + Prometheus + Grafana):

```bash
docker compose up --build
```

Wait for:
```
app-1 | Guardrail registered: no_system_role_only
app-1 | Guardrail registered: max_token_cap
app-1 | Guardrail registered: model_allowlist
app-1 | Application startup complete.
```

---

## API Reference

### Health check
```
GET /health
```
```json
{"status": "ok", "env": "development"}
```

### Proxy an LLM request
```
POST /v1/proxy
Content-Type: application/json

{
  "model": "claude-3-haiku-20240307",
  "max_tokens": 100,
  "messages": [{"role": "user", "content": "Hello"}]
}
```

Every response includes an `x-trace-id` header with the UUID for this request.

### List registered guardrail policies
```
GET /guardrails
```
```json
{"policies": ["no_system_role_only", "max_token_cap", "model_allowlist"]}
```

### Register a new guardrail policy
```
POST /guardrails
Content-Type: application/json

{"name": "my_custom_policy", "description": "blocks specific patterns"}
```

### Circuit breaker status
```
GET /circuit-breaker
```
```json
{
  "state": "closed",
  "failures": 0,
  "failure_threshold": 5,
  "recovery_timeout_seconds": 30,
  "opened_at": null
}
```

### Prometheus metrics
```
GET /metrics
```
Returns raw Prometheus text format with:
- `sentinel_request_latency_seconds` — histogram with configurable buckets
- `sentinel_request_total` — counter by endpoint/method/status
- `sentinel_guardrail_violations_total` — counter by policy name

---

## Observability

### Grafana Dashboard
Open `http://localhost:3000` (admin / admin) and add Prometheus as a data source at `http://prometheus:9090`.

Useful queries:
```promql
# Request rate per minute by endpoint
rate(sentinel_request_total[1m])

# 95th percentile latency
histogram_quantile(0.95, rate(sentinel_request_latency_seconds_bucket[5m]))

# Guardrail violations over time
rate(sentinel_guardrail_violations_total[5m])
```

### SpendLogs query
```bash
# View recent requests
docker compose exec db psql -U sentinel -d sentinel_db \
  -c "SELECT trace_id, model, status_code, latency_ms, timestamp FROM spend_logs ORDER BY timestamp DESC LIMIT 10;"

# Look up a specific trace
docker compose exec db psql -U sentinel -d sentinel_db \
  -c "SELECT * FROM spend_logs WHERE trace_id = 'your-trace-id-here';"
```

---

## Configuration

All settings are read from `.env` at startup via Pydantic Settings:

| Variable | Description | Default |
|---|---|---|
| `DATABASE_URL` | PostgreSQL async connection string | — |
| `REDIS_URL` | Redis connection string | — |
| `UPSTREAM_LLM_URL` | Base URL of the upstream LLM API | — |
| `LATENCY_BUCKETS` | Comma-separated histogram bucket thresholds | `0.05,0.1,0.25,0.5,1.0,2.5` |
| `APP_ENV` | Environment label shown in health check | `development` |

The `LATENCY_BUCKETS` variable is the key design choice — bucket thresholds are not hardcoded, they are parsed at startup via `settings.get_latency_buckets()`. This means you can tune observability granularity per environment without a code change.

---

## Testing the Circuit Breaker

Point the gateway at an unreachable host to simulate upstream failure:

```bash
# Break the upstream
echo "UPSTREAM_LLM_URL=http://doesnotexist.invalid" >> .env
docker compose restart app

# Send 6 requests — watch the circuit trip on request 6
for i in {1..6}; do
  curl -s -X POST http://localhost:8000/v1/proxy \
    -H "Content-Type: application/json" \
    -d '{"model": "claude-3-haiku-20240307", "max_tokens": 10, "messages": [{"role": "user", "content": "hi"}]}'
  echo ""
done

# Check state — should be OPEN
curl http://localhost:8000/circuit-breaker

# Wait 30 seconds — state transitions to HALF-OPEN automatically on next request
```

---

## Resume Bullet Points

```
Sentinel-GW: High-Throughput AI Observability Gateway
Python · FastAPI · Prometheus · Redis · PostgreSQL · Docker

• Architected a high-performance AI proxy using FastAPI to intercept and audit
  LLM API calls, ensuring 100% logging traceability into PostgreSQL SpendLogs
  via UUID trace IDs that propagate across console logs, DB rows, and metrics.

• Engineered custom Prometheus instrumentation with configurable latency
  histogram buckets loaded from environment variables at startup, enabling
  granular performance monitoring without code changes across environments.

• Developed a robust guardrail engine with structured error middleware that
  eliminates silent failures — all policy enforcement exceptions are caught
  and surfaced as typed 422 API responses with full trace context.

• Integrated a Redis-backed circuit breaker implementing the CLOSED/OPEN/
  HALF-OPEN state machine, maintaining system stability during upstream
  provider outages and persisting state across container restarts.
```

---

## License

MIT
