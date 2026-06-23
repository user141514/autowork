from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class LLMSettings:
    provider: str
    base_url: str
    api_key: str
    model: str
    timeout_seconds: int
    temperature: float
    max_tokens: int
    extract_max_messages: int
    extract_max_chars_per_message: int
    extract_max_candidates: int

    @property
    def has_api_key(self) -> bool:
        return bool(self.api_key and self.api_key != "PASTE_YOUR_KEY_HERE")

    def redacted(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "base_url": self.base_url,
            "model": self.model,
            "timeout_seconds": self.timeout_seconds,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "extract_max_messages": self.extract_max_messages,
            "extract_max_chars_per_message": self.extract_max_chars_per_message,
            "extract_max_candidates": self.extract_max_candidates,
            "api_key_present": self.has_api_key,
        }


def _int_clamp(value: object, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(minimum, min(parsed, maximum))


def _float_clamp(value: object, default: float, minimum: float, maximum: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        parsed = default
    return max(minimum, min(parsed, maximum))


def get_llm_settings() -> LLMSettings:
    raw = _load_local_mykey_settings()
    provider = os.getenv("AGENT_WORKFLOW_LLM_PROVIDER", str(raw.get("provider", "openai_compatible")))
    base_url = os.getenv("AGENT_WORKFLOW_LLM_BASE_URL", str(raw.get("base_url", "https://api.deepseek.com"))).rstrip("/")
    api_key = os.getenv("AGENT_WORKFLOW_LLM_API_KEY", str(raw.get("api_key", ""))).strip()
    model = os.getenv("AGENT_WORKFLOW_LLM_MODEL", str(raw.get("model", "deepseek-chat")))
    timeout_seconds = _int_clamp(os.getenv("AGENT_WORKFLOW_LLM_TIMEOUT_SECONDS", raw.get("timeout_seconds", 60)), 60, 5, 180)
    temperature = _float_clamp(os.getenv("AGENT_WORKFLOW_LLM_TEMPERATURE", raw.get("temperature", 0.1)), 0.1, 0.0, 2.0)
    max_tokens = _int_clamp(os.getenv("AGENT_WORKFLOW_LLM_MAX_TOKENS", raw.get("max_tokens", 2048)), 2048, 256, 8192)
    extract_max_messages = _int_clamp(os.getenv("AGENT_WORKFLOW_LLM_EXTRACT_MAX_MESSAGES", raw.get("extract_max_messages", 60)), 60, 1, 200)
    extract_max_chars_per_message = _int_clamp(os.getenv("AGENT_WORKFLOW_LLM_EXTRACT_MAX_CHARS_PER_MESSAGE", raw.get("extract_max_chars_per_message", 360)), 360, 80, 2000)
    extract_max_candidates = _int_clamp(os.getenv("AGENT_WORKFLOW_LLM_EXTRACT_MAX_CANDIDATES", raw.get("extract_max_candidates", 6)), 6, 1, 20)
    return LLMSettings(
        provider=provider,
        base_url=base_url,
        api_key=api_key,
        model=model,
        timeout_seconds=timeout_seconds,
        temperature=temperature,
        max_tokens=max_tokens,
        extract_max_messages=extract_max_messages,
        extract_max_chars_per_message=extract_max_chars_per_message,
        extract_max_candidates=extract_max_candidates,
    )


def _load_local_mykey_settings() -> dict[str, Any]:
    try:
        from app.mykey import LLM_SETTINGS  # type: ignore
    except Exception:
        return {}
    return dict(LLM_SETTINGS or {})
