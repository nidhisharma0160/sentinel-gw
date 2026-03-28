from app.core.guardrails import guardrail_engine
from app.models.schemas import LLMRequest


def register_default_policies():
    guardrail_engine.register(
        "no_system_role_only",
        lambda req: any(m.role == "user" for m in req.messages),
    )

    guardrail_engine.register(
        "max_token_cap",
        lambda req: req.max_tokens <= 4096,
    )

    guardrail_engine.register(
        "model_allowlist",
        lambda req: req.model.startswith("claude"),
    )
