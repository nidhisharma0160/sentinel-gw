import time
import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from app.core.trace import generate_trace_id

logger = logging.getLogger(__name__)


class TraceMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        trace_id = generate_trace_id()
        request.state.trace_id = trace_id

        logger.info(f"[{trace_id}] --> {request.method} {request.url.path}")

        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = round((time.perf_counter() - start) * 1000)

        logger.info(f"[{trace_id}] <-- {response.status_code} ({duration_ms}ms)")

        response.headers["X-Trace-ID"] = trace_id
        return response
