import logging
from fastapi import FastAPI
from fastapi.responses import Response
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from app.core.config import settings
from app.core.metrics import REGISTRY
from app.core.circuit_breaker import circuit_breaker
from app.core.database import init_db
from app.middleware.trace import TraceMiddleware
from app.middleware.prometheus import PrometheusMiddleware
from app.api.proxy import router as proxy_router
from app.api.guardrails import router as guardrail_router
from app.core.policies import register_default_policies

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)

app = FastAPI(title="Sentinel-GW", version="0.1.0")

app.add_middleware(PrometheusMiddleware)
app.add_middleware(TraceMiddleware)
app.include_router(proxy_router)
app.include_router(guardrail_router)


@app.on_event("startup")
async def startup():
    await init_db()
    register_default_policies()


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "env": settings.APP_ENV,
    }


@app.get("/metrics")
async def metrics():
    return Response(
        content=generate_latest(REGISTRY),
        media_type=CONTENT_TYPE_LATEST,
    )


@app.get("/circuit-breaker")
async def circuit_status():
    return circuit_breaker.get_status()
