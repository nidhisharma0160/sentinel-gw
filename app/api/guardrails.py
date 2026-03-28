import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.core.guardrails import guardrail_engine

logger = logging.getLogger(__name__)
router = APIRouter()


class GuardrailInfo(BaseModel):
    name: str
    description: str = ""


@router.post("/guardrails")
async def register_guardrail(info: GuardrailInfo):
    try:
        guardrail_engine.register(
            info.name,
            lambda req: True
        )
        return {
            "registered": info.name,
            "status": "ok"
        }
    except Exception as e:
        logger.error(f"Guardrail registration failed: {e}")
        raise HTTPException(
            status_code=422,
            detail=f"Failed to register guardrail: {str(e)}"
        )


@router.get("/guardrails")
async def list_guardrails():
    return {
        "policies": list(guardrail_engine._policies.keys())
    }
