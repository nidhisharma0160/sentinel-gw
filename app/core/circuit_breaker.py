import time
import logging
from enum import Enum
from redis import Redis
from app.core.config import settings

logger = logging.getLogger(__name__)

FAILURE_THRESHOLD = 5
RECOVERY_TIMEOUT = 30
CB_STATE_KEY = "circuit_breaker:state"
CB_FAILURES_KEY = "circuit_breaker:failures"
CB_OPENED_AT_KEY = "circuit_breaker:opened_at"


class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    def __init__(self):
        self._redis = Redis.from_url(settings.REDIS_URL, decode_responses=True)

    def _get_state(self) -> CircuitState:
        state = self._redis.get(CB_STATE_KEY)
        if state is None:
            return CircuitState.CLOSED
        return CircuitState(state)

    def _set_state(self, state: CircuitState):
        self._redis.set(CB_STATE_KEY, state.value)
        logger.info(f"Circuit breaker state changed to: {state.value.upper()}")

    def _get_failures(self) -> int:
        val = self._redis.get(CB_FAILURES_KEY)
        return int(val) if val else 0

    def _increment_failures(self):
        self._redis.incr(CB_FAILURES_KEY)

    def _reset_failures(self):
        self._redis.set(CB_FAILURES_KEY, 0)

    def is_open(self) -> bool:
        state = self._get_state()

        if state == CircuitState.CLOSED:
            return False

        if state == CircuitState.OPEN:
            opened_at = self._redis.get(CB_OPENED_AT_KEY)
            if opened_at and (time.time() - float(opened_at)) > RECOVERY_TIMEOUT:
                self._set_state(CircuitState.HALF_OPEN)
                logger.info("Circuit breaker entering HALF-OPEN, testing recovery")
                return False
            return True

        if state == CircuitState.HALF_OPEN:
            return False

        return False

    def record_success(self):
        state = self._get_state()
        if state == CircuitState.HALF_OPEN:
            logger.info("Circuit breaker: upstream recovered, closing circuit")
        self._set_state(CircuitState.CLOSED)
        self._reset_failures()

    def record_failure(self, trace_id: str):
        state = self._get_state()

        if state == CircuitState.HALF_OPEN:
            logger.warning(f"[{trace_id}] Half-open test failed, reopening circuit")
            self._set_state(CircuitState.OPEN)
            self._redis.set(CB_OPENED_AT_KEY, time.time())
            return

        self._increment_failures()
        failures = self._get_failures()
        logger.warning(f"[{trace_id}] Upstream failure {failures}/{FAILURE_THRESHOLD}")

        if failures >= FAILURE_THRESHOLD:
            logger.error(f"[{trace_id}] Failure threshold reached, opening circuit")
            self._set_state(CircuitState.OPEN)
            self._redis.set(CB_OPENED_AT_KEY, time.time())

    def get_status(self) -> dict:
        state = self._get_state()
        failures = self._get_failures()
        opened_at = self._redis.get(CB_OPENED_AT_KEY)
        return {
            "state": state.value,
            "failures": failures,
            "failure_threshold": FAILURE_THRESHOLD,
            "recovery_timeout_seconds": RECOVERY_TIMEOUT,
            "opened_at": float(opened_at) if opened_at else None,
        }


circuit_breaker = CircuitBreaker()
