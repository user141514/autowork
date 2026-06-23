from app.schemas.context_confidence import ContextAssessment, ContextConfidenceResult, DirectAnswerDraft
from app.schemas.demand_radar import DemandMessage


OBJECT_TERMS = (
    "页面",
    "首页",
    "设置",
    "工作台",
    "看板",
    "报表",
    "权限",
    "按钮",
    "接口",
    "数据库",
    "脚本",
    "仓库",
    "文件",
    "日志",
    "路由",
    "api",
    "字段",
    "组件",
    "depends",
    "fastapi",
    "pathlib.path",
)

ACTION_TERMS = ("修", "改", "加", "处理", "优化", "支持", "帮我", "需要", "能不能")
PROBLEM_TERMS = ("报错", "失败", "不行", "没反应", "异常", "500", "403", "一直转圈", "错位")
EXPECTED_TERMS = ("期望", "验收", "应该", "预期", "成功后", "显示", "提示")
QUESTION_TERMS = ("？", "?", "是什么", "怎么", "如何", "为什么", "啥意思", "做什么用", "解释")
REMOTE_REFERENCE_TERMS = ("刚才", "上面", "前面", "上次", "之前", "那个", "还是按", "如上", "老问题")
VAGUE_REFERENCE_TERMS = ("这个", "那个", "这块", "这里", "它")


class ContextConfidenceAnalyzer:
    def analyze(self, messages: list[DemandMessage]) -> ContextConfidenceResult:
        ordered = sorted(messages, key=lambda item: item.timestamp)
        text = _norm(" ".join(message.text for message in ordered))
        evidence_ids = [message.id for message in ordered]

        has_question = _contains(text, QUESTION_TERMS)
        has_object = _contains(text, OBJECT_TERMS)
        has_action = _contains(text, ACTION_TERMS)
        has_problem = _contains(text, PROBLEM_TERMS)
        has_expected = _contains(text, EXPECTED_TERMS)
        has_remote_reference = _contains(text, REMOTE_REFERENCE_TERMS)
        has_vague_reference = _contains(text, VAGUE_REFERENCE_TERMS)
        has_local_density = len([message for message in ordered if message.text.strip()]) >= 2

        if has_remote_reference and not (has_problem and has_expected and has_object):
            return ContextConfidenceResult(
                assessment=ContextAssessment(
                    resolution="needs_more_history",
                    suggested_action="keep_scanning",
                    confidence_score=0.78,
                    confidence="high",
                    reasons=_reasons(
                        remote_context_reference=True,
                        has_explicit_object=has_object,
                        has_actionable_intent=has_action,
                    ),
                    missing_fields=["previous_context"],
                    evidence_message_ids=evidence_ids,
                    suggested_lookback_messages=80,
                )
            )

        if has_question and not has_problem and not _looks_like_code_change_request(text):
            question = _best_question(ordered)
            return ContextConfidenceResult(
                assessment=ContextAssessment(
                    resolution="self_contained",
                    suggested_action="direct_answer_ready",
                    confidence_score=0.86 if has_object else 0.68,
                    confidence="high" if has_object else "medium",
                    reasons=_reasons(
                        self_contained_question=True,
                        has_explicit_object=has_object,
                    ),
                    missing_fields=[],
                    evidence_message_ids=evidence_ids,
                ),
                direct_answer_draft=DirectAnswerDraft(
                    question=question,
                    answer_strategy="Draft a concise answer from the visible question only; do not create WorkDoc or AgentRun.",
                    evidence_message_ids=evidence_ids,
                ),
            )

        missing_fields = _missing_fields(has_object, has_expected, has_action or has_problem)
        if has_object and (has_problem or has_action) and (has_expected or has_local_density):
            score = 0.82 if has_expected else 0.66
            return ContextConfidenceResult(
                assessment=ContextAssessment(
                    resolution="local_context_enough",
                    suggested_action="candidate_ready",
                    confidence_score=score,
                    confidence="high" if score >= 0.75 else "medium",
                    reasons=_reasons(
                        has_explicit_object=has_object,
                        has_actionable_intent=has_action or has_problem,
                        has_expected_behavior=has_expected,
                        nearby_context_density=has_local_density,
                    ),
                    missing_fields=missing_fields,
                    evidence_message_ids=evidence_ids,
                )
            )

        if has_action or has_problem or has_vague_reference:
            return ContextConfidenceResult(
                assessment=ContextAssessment(
                    resolution="needs_user_input",
                    suggested_action="ask_user",
                    confidence_score=0.62,
                    confidence="medium",
                    reasons=_reasons(
                        vague_reference=has_vague_reference,
                        has_actionable_intent=has_action or has_problem,
                    ),
                    missing_fields=missing_fields,
                    evidence_message_ids=evidence_ids,
                )
            )

        return ContextConfidenceResult(
            assessment=ContextAssessment(
                resolution="needs_user_input",
                suggested_action="ignore",
                confidence_score=0.3,
                confidence="low",
                reasons=["low_signal"],
                missing_fields=["actionable_intent"],
                evidence_message_ids=evidence_ids,
            )
        )


def _norm(text: str) -> str:
    return text.strip().lower()


def _contains(text: str, terms: tuple[str, ...]) -> bool:
    return any(term in text for term in terms)


def _looks_like_code_change_request(text: str) -> bool:
    return _contains(text, ACTION_TERMS) and _contains(text, OBJECT_TERMS)


def _best_question(messages: list[DemandMessage]) -> str:
    for message in messages:
        if _contains(_norm(message.text), QUESTION_TERMS):
            return message.text
    return messages[-1].text if messages else ""


def _missing_fields(has_object: bool, has_expected: bool, has_intent: bool) -> list[str]:
    missing: list[str] = []
    if not has_object:
        missing.append("target_object")
    if not has_expected and has_intent:
        missing.append("expected_behavior")
    return missing


def _reasons(**flags: bool) -> list[str]:
    return [name for name, enabled in flags.items() if enabled]
