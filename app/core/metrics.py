from prometheus_client import Histogram, Counter, CollectorRegistry
from app.core.config import settings

REGISTRY = CollectorRegistry()

REQUEST_LATENCY = Histogram(
    "sentinel_request_latency_seconds",
    "Request latency in seconds",
    ["method", "endpoint", "status_code"],
    buckets=settings.get_latency_buckets(),
    registry=REGISTRY,
)

REQUEST_COUNT = Counter(
    "sentinel_request_total",
    "Total number of requests",
    ["method", "endpoint", "status_code"],
    registry=REGISTRY,
)

GUARDRAIL_VIOLATIONS = Counter(
    "sentinel_guardrail_violations_total",
    "Total guardrail policy violations",
    ["policy_name"],
    registry=REGISTRY,
)
