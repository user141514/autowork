from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from app.services.llm_settings import LLMSettings, get_llm_settings


class LLMConfigurationError(RuntimeError):
    pass


class LLMRequestError(RuntimeError):
    pass


@dataclass(frozen=True)
class LLMChatResult:
    content: str
    raw: dict[str, Any]


class OpenAICompatibleLLMClient:
    def __init__(self, settings: LLMSettings | None = None):
        self.settings = settings or get_llm_settings()

    def chat_json(self, messages: list[dict[str, str]], *, temperature: float | None = None, max_tokens: int | None = None) -> LLMChatResult:
        if self.settings.provider != "openai_compatible":
            raise LLMConfigurationError(f"unsupported LLM provider: {self.settings.provider}")
        if not self.settings.has_api_key:
            raise LLMConfigurationError("LLM_API_KEY_MISSING: fill app/mykey.py or AGENT_WORKFLOW_LLM_API_KEY")
        url = f"{self.settings.base_url}/chat/completions"
        payload = {
            "model": self.settings.model,
            "messages": messages,
            "temperature": self.settings.temperature if temperature is None else temperature,
            "max_tokens": self.settings.max_tokens if max_tokens is None else max_tokens,
            "response_format": {"type": "json_object"},
        }
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.settings.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.settings.timeout_seconds) as response:
                body = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            raise LLMRequestError(f"LLM_HTTP_{exc.code}: {error_body[:500]}") from exc
        except urllib.error.URLError as exc:
            raise LLMRequestError(f"LLM_CONNECTION_FAILED: {exc}") from exc
        try:
            raw = json.loads(body)
            content = raw["choices"][0]["message"]["content"]
        except Exception as exc:
            raise LLMRequestError(f"LLM_BAD_RESPONSE: {body[:500]}") from exc
        return LLMChatResult(content=str(content), raw=raw)

    def ping(self) -> dict[str, Any]:
        result = self.chat_json(
            [
                {"role": "system", "content": "Return JSON only."},
                {"role": "user", "content": "Return {\"ok\":true,\"message\":\"pong\"}."},
            ],
            temperature=0,
            max_tokens=64,
        )
        try:
            parsed = json.loads(result.content)
        except json.JSONDecodeError:
            parsed = {"ok": False, "raw_content": result.content}
        return {"ok": bool(parsed.get("ok")), "response": parsed, "model": self.settings.model, "base_url": self.settings.base_url}
