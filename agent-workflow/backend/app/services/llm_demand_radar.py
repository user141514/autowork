from __future__ import annotations

import hashlib
import json
from typing import Any

from app.schemas.demand_radar import (
    CandidateFact,
    CandidateInference,
    CandidateRequirement,
    DemandMessage,
    EvidenceMessage,
    SignalSummary,
)
from app.services.llm_client import OpenAICompatibleLLMClient


_ALLOWED_TYPES = {"bug", "feature", "document", "data", "config", "uncertain"}
_ALLOWED_STATUS = {"pending_review", "suspect", "expired"}
_ALLOWED_CONFIDENCE = {"low", "medium", "high"}
_LLM_EXTRACT_CACHE: dict[str, list[CandidateRequirement]] = {}
_MAX_CACHE_ITEMS = 128


class LLMDemandRadar:
    def __init__(self, client: OpenAICompatibleLLMClient | None = None):
        self.client = client or OpenAICompatibleLLMClient()

    def extract(self, messages: list[DemandMessage]) -> list[CandidateRequirement]:
        if not messages:
            return []
        prepared_messages = _prepare_messages(
            messages,
            max_messages=self.client.settings.extract_max_messages,
            max_chars=self.client.settings.extract_max_chars_per_message,
        )
        prompt = _build_prompt(prepared_messages, max_candidates=self.client.settings.extract_max_candidates)
        cache_key = _cache_key(
            prompt=prompt,
            model=self.client.settings.model,
            base_url=self.client.settings.base_url,
            max_tokens=min(self.client.settings.max_tokens, 1800),
        )
        cached = _LLM_EXTRACT_CACHE.get(cache_key)
        if cached is not None:
            return [candidate.model_copy(deep=True) for candidate in cached]
        result = self.client.chat_json(
            [
                {"role": "system", "content": _system_prompt()},
                {"role": "user", "content": prompt},
            ],
            temperature=0,
            max_tokens=min(self.client.settings.max_tokens, 1800),
        )
        payload = _parse_json_object(result.content)
        candidates = _normalize_candidates(payload, messages, max_candidates=self.client.settings.extract_max_candidates)
        _store_cache(cache_key, candidates)
        return candidates


def _system_prompt() -> str:
    return """
You are a requirement-intake analyzer for noisy group chat.
Return JSON only. Do not execute tasks. Do not invent evidence.
Your job is to extract reviewable requirement candidates, not WorkDocs.
Each candidate must be grounded in message IDs from the input.
""".strip()


def _prepare_messages(messages: list[DemandMessage], max_messages: int, max_chars: int) -> list[DemandMessage]:
    selected = messages[-max(1, max_messages) :]
    prepared: list[DemandMessage] = []
    for message in selected:
        text = message.text if len(message.text) <= max_chars else message.text[: max(0, max_chars - 3)] + "..."
        prepared.append(message.model_copy(update={"text": text}))
    return prepared


def _build_prompt(messages: list[DemandMessage], max_candidates: int) -> str:
    rows = [
        {
            "id": message.id,
            "sender": message.sender,
            "time": message.timestamp.isoformat(),
            "type": message.msg_type,
            "text": message.text,
        }
        for message in messages
    ]
    return json.dumps(
        {
            "task": "Extract work-relevant requirement candidates from chat. Return compact JSON only.",
            "limits": {"maxCandidates": max_candidates, "evidenceMustUseInputIds": True},
            "schema": {
                "candidates": [
                    {
                        "title": "short title",
                        "requirementType": "bug|feature|document|data|config|uncertain",
                        "status": "pending_review|suspect|expired",
                        "confidence": "low|medium|high",
                        "confidenceScore": 0.0,
                        "hypothesis": "one sentence",
                        "evidenceMessageIds": ["input id"],
                        "missingFields": ["project_or_repo", "acceptance_criteria", "expected_behavior"],
                        "facts": [{"text": "short fact", "messageId": "input id"}],
                        "inferences": [{"text": "short inference", "basisMessageIds": ["input id"]}],
                    }
                ]
            },
            "messages": rows,
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )


def _cache_key(prompt: str, model: str, base_url: str, max_tokens: int) -> str:
    raw = json.dumps(
        {"prompt": prompt, "model": model, "base_url": base_url, "max_tokens": max_tokens},
        ensure_ascii=False,
        sort_keys=True,
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _store_cache(cache_key: str, candidates: list[CandidateRequirement]) -> None:
    if len(_LLM_EXTRACT_CACHE) >= _MAX_CACHE_ITEMS:
        oldest_key = next(iter(_LLM_EXTRACT_CACHE))
        _LLM_EXTRACT_CACHE.pop(oldest_key, None)
    _LLM_EXTRACT_CACHE[cache_key] = [candidate.model_copy(deep=True) for candidate in candidates]


def clear_llm_demand_cache() -> None:
    _LLM_EXTRACT_CACHE.clear()


def _parse_json_object(content: str) -> dict[str, Any]:
    try:
        payload = json.loads(content)
    except json.JSONDecodeError:
        start = content.find("{")
        end = content.rfind("}")
        if start < 0 or end < start:
            raise
        payload = json.loads(content[start : end + 1])
    if not isinstance(payload, dict):
        raise ValueError("LLM response must be a JSON object")
    return payload


def _normalize_candidates(payload: dict[str, Any], messages: list[DemandMessage], max_candidates: int) -> list[CandidateRequirement]:
    by_id = {message.id: message for message in messages}
    raw_candidates = payload.get("candidates") or []
    if not isinstance(raw_candidates, list):
        raw_candidates = []
    normalized: list[CandidateRequirement] = []
    for raw in raw_candidates[:max(1, max_candidates)]:
        if not isinstance(raw, dict):
            continue
        evidence_ids = [str(item) for item in raw.get("evidenceMessageIds") or raw.get("evidence_message_ids") or []]
        evidence_ids = [message_id for message_id in evidence_ids if message_id in by_id][:12]
        if not evidence_ids:
            continue
        evidence = [
            EvidenceMessage(
                messageId=message.id,
                sender=message.sender,
                timestamp=message.timestamp,
                text=message.text,
                role="evidence",
            )
            for message_id in evidence_ids
            for message in [by_id[message_id]]
        ]
        title = _safe_text(raw.get("title")) or _title_from_evidence(evidence)
        requirement_type = _one_of(_safe_text(raw.get("requirementType") or raw.get("requirement_type")), _ALLOWED_TYPES, "uncertain")
        status = _one_of(_safe_text(raw.get("status")), _ALLOWED_STATUS, "pending_review")
        confidence = _one_of(_safe_text(raw.get("confidence")), _ALLOWED_CONFIDENCE, "medium")
        confidence_score = _safe_float(raw.get("confidenceScore") or raw.get("confidence_score"), default={"low": 0.3, "medium": 0.6, "high": 0.85}[confidence])
        confidence_score = max(0.0, min(1.0, confidence_score))
        hypothesis = _safe_text(raw.get("hypothesis")) or title
        missing_fields = [str(item) for item in raw.get("missingFields") or raw.get("missing_fields") or []][:12]
        facts = _facts(raw.get("facts"), evidence)
        inferences = _inferences(raw.get("inferences"), hypothesis, evidence_ids)
        normalized.append(
            CandidateRequirement(
                id=_safe_text(raw.get("id")) or _candidate_id(evidence_ids, hypothesis),
                chatId=by_id[evidence_ids[0]].chat_id,
                chatName=by_id[evidence_ids[0]].chat_name,
                title=title,
                requirementType=requirement_type,
                status=status,
                confidence=confidence,
                confidenceScore=confidence_score,
                hypothesis=hypothesis,
                evidenceMessageIds=evidence_ids,
                evidence=evidence,
                facts=facts,
                inferences=inferences,
                missingFields=missing_fields,
                signalSummary=SignalSummary(),
                noiseRatio=0.0,
                contextAssessment=None,
            )
        )
    return normalized


def _facts(raw_facts: Any, evidence: list[EvidenceMessage]) -> list[CandidateFact]:
    facts: list[CandidateFact] = []
    if isinstance(raw_facts, list):
        for item in raw_facts:
            if not isinstance(item, dict):
                continue
            text = _safe_text(item.get("text"))
            message_id = _safe_text(item.get("messageId") or item.get("message_id"))
            if text and message_id:
                facts.append(CandidateFact(text=text, messageId=message_id))
    if facts:
        return facts
    return [CandidateFact(text=f"{item.sender or '未知'}: {item.text[:120]}", messageId=item.message_id) for item in evidence]


def _inferences(raw_inferences: Any, hypothesis: str, evidence_ids: list[str]) -> list[CandidateInference]:
    if isinstance(raw_inferences, list):
        result: list[CandidateInference] = []
        for item in raw_inferences:
            if not isinstance(item, dict):
                continue
            text = _safe_text(item.get("text"))
            basis = [str(value) for value in item.get("basisMessageIds") or item.get("basis_message_ids") or evidence_ids]
            if text and basis:
                result.append(CandidateInference(text=text, basisMessageIds=basis))
        if result:
            return result
    return [CandidateInference(text=hypothesis, basisMessageIds=evidence_ids)]


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _safe_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _one_of(value: str, allowed: set[str], default: str) -> str:
    return value if value in allowed else default


def _title_from_evidence(evidence: list[EvidenceMessage]) -> str:
    text = evidence[0].text if evidence else "候选需求"
    return text[:48] or "候选需求"


def _candidate_id(evidence_ids: list[str], hypothesis: str) -> str:
    raw = "|".join(evidence_ids + [hypothesis])
    return "llm_" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
