import time
import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from app.core.metrics import REQUEST_LATENCY, REQUEST_COUNT

logger = logging.getLogger(__name__)


class PrometheusMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start = time.perf_counter()

        try:
            response = await call_next(request)
            status_code = str(response.status_code)
        except Exception as e:
            logger.error(f"Unhandled exception in PrometheusMiddleware: {e}")
            status_code = "500"
            raise
        finally:
            duration = time.perf_counter() - start
            labels = {
                "method": request.method,
                "endpoint": request.url.path,
                "status_code": status_code,
            }
            REQUEST_LATENCY.labels(**labels).observe(duration)
            REQUEST_COUNT.labels(**labels).inc()

        return response
