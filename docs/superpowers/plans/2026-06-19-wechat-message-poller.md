# WeChat Message Poller Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Windows-local wxauto polling script that automatically imports whitelisted group chat messages into SQLite and records `@WorkBot` commands without creating WorkDocs, running agents, or touching Git.

**Architecture:** Add one script-level orchestration module under `agent-workflow/backend/scripts/`. It reuses `PersonalWeChatAdapter`, `MessageStore`, `BotCommandService`, `SessionLocal`, and `init_db`; it owns polling cadence, CLI parsing, logging, dry-run behavior, and graceful shutdown.

**Tech Stack:** Python 3.12, existing FastAPI backend service layer, SQLAlchemy SQLite session, wxauto through existing adapter only.

## Global Constraints

- Use Windows WeChat Desktop UIAutomation / wxauto as the primary chat source.
- Do not read or reverse engineer local WeChat databases.
- Only read configured whitelist groups.
- Do not process private chats.
- Do not let ordinary messages trigger `AgentRun`.
- Only `@WorkBot` commands enter the command flow.
- Save all messages as `ChatMessage` before command processing.
- The script stops at `BotCommandLog`; it does not create `Segment`, `TaskCandidate`, `WorkDoc`, `AgentRun`, or Git operations.

---

### Task 1: Add Poller Tests

**Files:**
- Modify: `agent-workflow/backend/tests/test_phase9_wechat_adapters.py`
- Create later: `agent-workflow/backend/scripts/poll_wechat_messages.py`

**Interfaces:**
- Consumes: future functions `poll_once(adapter, settings, db, limit, dry_run)` and `parse_args(argv)`.
- Produces: test coverage for import, command processing, dry-run, and CLI parsing.

- [ ] **Step 1: Write failing tests**

Add tests that dynamically import `scripts/poll_wechat_messages.py`, inject a fake adapter, and assert:

```python
def test_wechat_poller_imports_messages_and_processes_workbot_commands():
    stats = module.poll_once(fake_adapter, settings, db, limit=20, dry_run=False)
    assert stats.imported_count == 2
    assert stats.command_count == 1
```

```python
def test_wechat_poller_dry_run_does_not_write_database():
    stats = module.poll_once(fake_adapter, settings, db, limit=20, dry_run=True)
    assert stats.fetched_count == 1
    assert stats.imported_count == 0
```

```python
def test_wechat_poller_parse_args_once_sets_interval_zero():
    args = module.parse_args(["--once", "--dry-run", "--rooms", "dev-group,ops-group"])
    assert args.interval == 0
    assert args.dry_run is True
    assert args.rooms == ["dev-group", "ops-group"]
```

- [ ] **Step 2: Run red tests**

Run:

```bash
cd agent-workflow/backend
python -m pytest tests/test_phase9_wechat_adapters.py -q
```

Expected: fail because `scripts/poll_wechat_messages.py` does not exist.

---

### Task 2: Implement Poller Script

**Files:**
- Create: `agent-workflow/backend/scripts/poll_wechat_messages.py`

**Interfaces:**
- Produces:
  - `PollStats` dataclass with fields `room_count`, `fetched_count`, `imported_count`, `command_count`, `errors`.
  - `parse_args(argv: list[str] | None = None) -> argparse.Namespace`
  - `poll_once(adapter: PersonalWeChatAdapter, settings: Settings, db: Session, limit: int, dry_run: bool, rooms: list[str] | None = None) -> PollStats`
  - `main(argv: list[str] | None = None) -> int`

- [ ] **Step 1: Implement minimal script**

Implement:

```python
@dataclass
class PollStats:
    room_count: int = 0
    fetched_count: int = 0
    imported_count: int = 0
    command_count: int = 0
    errors: list[str] = field(default_factory=list)
```

`poll_once()` loops over selected rooms, fetches messages, optionally imports with `MessageStore`, then calls `BotCommandService.process_new_messages()`.

- [ ] **Step 2: Run targeted tests**

Run:

```bash
cd agent-workflow/backend
python -m pytest tests/test_phase9_wechat_adapters.py -q
```

Expected: pass.

---

### Task 3: Document Usage

**Files:**
- Modify: `agent-workflow/backend/README.md`

**Interfaces:**
- Consumes: script CLI from Task 2.
- Produces: operator instructions.

- [ ] **Step 1: Add README section**

Document:

```bash
set AGENT_WORKFLOW_PERSONAL_WECHAT_ENABLED=true
set AGENT_WORKFLOW_ALLOWED_WECHAT_ROOMS=dev-group
python scripts\poll_wechat_messages.py --once --dry-run
python scripts\poll_wechat_messages.py --interval 30
```

Clarify that it imports messages and records `@WorkBot` command logs only.

- [ ] **Step 2: Run all tests**

Run:

```bash
cd agent-workflow/backend
python -m pytest
```

Expected: all tests pass.
