import json
from pathlib import Path

from app.schemas.requirement_promotion import RequirementPromotionResult


class AgentInboxWriter:
    def __init__(self, root_dir: Path | str = "agent_inbox"):
        self.root_dir = Path(root_dir)

    def write(self, result: RequirementPromotionResult) -> Path:
        inbox_dir = self.root_dir / result.agent_input_pack.pack_id
        inbox_dir.mkdir(parents=True, exist_ok=True)
        self._write_json(inbox_dir / "agent_input.json", result.agent_input_pack)
        self._write_json(inbox_dir / "workdoc_draft.json", result.workdoc_draft)
        self._write_json(inbox_dir / "evidence.json", result.agent_input_pack.evidence)
        (inbox_dir / "agent_brief.md").write_text(result.agent_brief_markdown, encoding="utf-8")
        return inbox_dir

    def _write_json(self, path: Path, value) -> None:
        path.write_text(
            json.dumps(_dump(value), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


def _dump(value):
    if isinstance(value, list):
        return [_dump(item) for item in value]
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json", by_alias=True)
    return value
