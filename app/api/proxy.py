import time
import logging
import httpx
from fastapi import APIRouter, Request, HTTPException
from app.core.config import settings
from app.core.guardrails import guardrail_engine
from app.core.metrics import GUARDRAIL_VIOLATIONS
from app.core.circuit_breaker import circuit_breaker
from app.core.spend_logger import log_spend
from app.models.schemas import LLMRequest
from pydantic import ValidationError

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/v1/proxy")
async def proxy(request: Request):
    trace_id = request.state.trace_id
    start = time.perf_counter()
    body = await request.json()

    logger.info(f"[{trace_id}] Validating request payload")

    try:
        llm_request = LLMRequest(**body)
    except ValidationError as e:
        logger.warning(f"[{trace_id}] Payload validation failed: {e}")
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.warning(f"[{trace_id}] Bad request body: {e}")
        raise HTTPException(status_code=422, detail=str(e))

    violations = guardrail_engine.run(llm_request, trace_id)
    if violations:
        logger.warning(f"[{trace_id}] Guardrail violations: {violations}")
        for v in violations:
            GUARDRAIL_VIOLATIONS.labels(policy_name=v).inc()
        raise HTTPException(
            status_code=422,
            detail={"guardrail_violations": violations}
        )

    if circuit_breaker.is_open():
        logger.warning(f"[{trace_id}] Circuit is OPEN, rejecting request fast")
        raise HTTPException(
            status_code=503,
            detail={
                "error": "circuit_open",
                "message": "Upstream LLM is unavailable, try again later",
                "status": circuit_breaker.get_status(),
            }
        )

    logger.info(f"[{trace_id}] Forwarding request to upstream LLM")

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{settings.UPSTREAM_LLM_URL}/v1/messages",
                json=body,
                headers={
                    "Content-Type": "application/json",
                    "x-trace-id": trace_id,
                },
            )

        latency_ms = (time.perf_counter() - start) * 1000

        if response.status_code >= 500:
            circuit_breaker.record_failure(trace_id)
        else:
            circuit_breaker.record_success()

        response_data = response.json()
        tokens_in = response_data.get("usage", {}).get("input_tokens", 0)
        tokens_out = response_data.get("usage", {}).get("output_tokens", 0)

        await log_spend(
            trace_id=trace_id,
            model=llm_request.model,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            latency_ms=round(latency_ms, 2),
            status_code=response.status_code,
            endpoint="/v1/proxy",
        )

        logger.info(f"[{trace_id}] Upstream responded with {response.status_code}")
        return response_data

    except httpx.TimeoutException:
        latency_ms = (time.perf_counter() - start) * 1000
        circuit_breaker.record_failure(trace_id)
        await log_spend(
            trace_id=trace_id,
            model=llm_request.model,
            tokens_in=0,
            tokens_out=0,
            latency_ms=round(latency_ms, 2),
            status_code=504,
            endpoint="/v1/proxy",
        )
        logger.error(f"[{trace_id}] Upstream request timed out")
        raise HTTPException(status_code=504, detail="Upstream LLM timed out")

    except Exception as e:
        latency_ms = (time.perf_counter() - start) * 1000
        circuit_breaker.record_failure(trace_id)
        await log_spend(
            trace_id=trace_id,
            model=llm_request.model,
            tokens_in=0,
            tokens_out=0,
            latency_ms=round(latency_ms, 2),
            status_code=502,
            endpoint="/v1/proxy",
        )
        logger.error(f"[{trace_id}] Upstream request failed: {e}")
        raise HTTPException(status_code=502, detail="Upstream LLM unavailable")
