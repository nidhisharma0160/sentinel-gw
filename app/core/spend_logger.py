import logging
from app.core.database import AsyncSessionLocal
from app.models.spend_log import SpendLog

logger = logging.getLogger(__name__)


async def log_spend(
    trace_id: str,
    model: str,
    tokens_in: int,
    tokens_out: int,
    latency_ms: float,
    status_code: int,
    endpoint: str,
):
    try:
        async with AsyncSessionLocal() as session:
            async with session.begin():
                entry = SpendLog(
                    trace_id=trace_id,
                    model=model,
                    tokens_in=tokens_in,
                    tokens_out=tokens_out,
                    latency_ms=latency_ms,
                    status_code=status_code,
                    endpoint=endpoint,
                )
                session.add(entry)
        logger.info(f"[{trace_id}] SpendLog written — model={model} status={status_code} latency={latency_ms:.1f}ms")
    except Exception as e:
        logger.error(f"[{trace_id}] Failed to write SpendLog: {e}")
