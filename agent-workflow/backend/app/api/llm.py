from fastapi import APIRouter, HTTPException

from app.services.llm_client import LLMConfigurationError, LLMRequestError, OpenAICompatibleLLMClient
from app.services.llm_settings import get_llm_settings


router = APIRouter(prefix="/llm", tags=["llm"])


@router.get("/config")
def llm_config():
    return get_llm_settings().redacted()


@router.post("/ping")
def llm_ping():
    try:
        return OpenAICompatibleLLMClient().ping()
    except LLMConfigurationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except LLMRequestError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
