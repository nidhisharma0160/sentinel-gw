import logging
from typing import Callable, Dict
from app.models.schemas import LLMRequest

logger = logging.getLogger(__name__)


class GuardrailEngine:
    def __init__(self):
        self._policies: Dict[str, Callable[[LLMRequest], bool]] = {}

    def register(self, name: str, policy_fn: Callable[[LLMRequest], bool]):
        try:
            if not callable(policy_fn):
                raise ValueError(f"Policy '{name}' must be a callable function")
            self._policies[name] = policy_fn
            logger.info(f"Guardrail registered: {name}")
        except Exception as e:
            logger.error(f"Failed to register guardrail '{name}': {e}")
            raise

    def run(self, request: LLMRequest, trace_id: str) -> list[str]:
        violations = []
        for name, policy_fn in self._policies.items():
            try:
                passed = policy_fn(request)
                if not passed:
                    logger.warning(f"[{trace_id}] Guardrail failed: {name}")
                    violations.append(name)
            except Exception as e:
                logger.error(f"[{trace_id}] Guardrail '{name}' threw an error: {e}")
                violations.append(f"{name} (error: {str(e)})")
        return violations


guardrail_engine = GuardrailEngine()
