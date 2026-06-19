# Agent Workflow Backend

FastAPI backend for a group-chat-driven autonomous development workflow. The core contract is WorkDoc:

```text
ChatMessage -> WorkDoc -> Validate -> Approve -> AgentRun -> Git diff -> Commit -> Report
```

The backend does not let an Agent read raw chat logs and modify code directly. Chat messages are evidence; WorkDoc is the execution contract.

## Implemented MVP

- Manual mock chat message import
- SQLite persistence for ChatMessage, WorkDoc, AgentRun, GitOperation
- Rule-based WorkDoc draft generation
- WorkDoc validate / approve state machine
- AgentRunner abstraction
- MockAgentRunner
- ClaudeCliRunner command wrapper, disabled by default
- gagent-desktop audit wrapper, disabled by default
- MockChatAdapter and WeChatAdapter stub
- Git diff detection including untracked files
- Local branch + commit, with dry-run default
- WorkDoc report API
- Minimal dashboard at `/dashboard`
- Phase 8 WorkDoc execution/test/agent/git/review config blocks
- PolicyGate decisions persisted in SQLite
- RepoContextBuilder generating `.agent_workflow_repo_context.md`
- TestRunner and `test_runs` table
- Git diff / branch / commit / push stub / PR stub APIs
- Report 2.0 markdown endpoints
- Phase 9 Personal WeChat intake through Windows WeChat Desktop UIAutomation / wxauto
- Windows-local WeChat polling script for whitelisted groups
- Segment and TaskCandidate pipeline before WorkDoc for personal WeChat messages
- Manual chat export import for `.txt`, `.json`, `.csv`, `.md`
- Local WeChat database import stub that intentionally does not bypass encryption or reverse engineer databases

Not implemented:

- Real WeChat login or long-running polling
- Direct WeChat local database import
- Push, PR, merge, or production Git automation
- Multi-user permission system
- Complex frontend
- Multi-agent planning

## Run

```bash
cd agent-workflow/backend
python -m pip install -e ".[dev]"
uvicorn app.main:app --reload
```

Open:

```text
http://127.0.0.1:8000/dashboard
```

Health check:

```text
GET http://127.0.0.1:8000/health
```

## Test

```bash
cd agent-workflow/backend
python -m pytest
```

## Configuration

Dangerous operations are off by default.

- `AGENT_WORKFLOW_APP_NAME`
- `AGENT_WORKFLOW_ENVIRONMENT`
- `AGENT_WORKFLOW_DATABASE_URL`
- `AGENT_WORKFLOW_LOG_LEVEL`
- `AGENT_WORKFLOW_DRY_RUN=true`
- `AGENT_WORKFLOW_ALLOW_CLAUDE_CLI=false`
- `AGENT_WORKFLOW_ALLOW_GAGENT_DESKTOP=false`
- `AGENT_WORKFLOW_GAGENT_DESKTOP_MODE=local_ipc`
- `AGENT_WORKFLOW_GAGENT_DESKTOP_ENDPOINT=`
- `AGENT_WORKFLOW_DEFAULT_AGENT_TIMEOUT_SECONDS=120`
- `AGENT_WORKFLOW_WORKBOT_MENTION=@WorkBot`
- `AGENT_WORKFLOW_ALLOWED_WECHAT_ROOMS=`
- `AGENT_WORKFLOW_WECHAT_WHITELIST_ROOMS=` (legacy alias)
- `AGENT_WORKFLOW_PERSONAL_WECHAT_ENABLED=false`
- `AGENT_WORKFLOW_WECHAT_SEND_ENABLED=false`
- `AGENT_WORKFLOW_WECHAT_READ_LIMIT=20`
- `AGENT_WORKFLOW_WECHAT_CONTEXT_WINDOW_SIZE=8`

## Minimal API

- `POST /messages/import`
- `GET /messages`
- `POST /segments/from-messages`
- `POST /segments/from-command/{message_id}`
- `GET /segments`
- `GET /segments/{id}`
- `POST /task-candidates/from-segment`
- `POST /task-candidates/from-segment/{segment_id}`
- `GET /task-candidates`
- `GET /task-candidates/{id}`
- `POST /task-candidates/{id}/update`
- `POST /task-candidates/{id}/convert-to-workdoc`
- `POST /workdocs/from-messages`
- `POST /workdocs/from-task-candidate`
- `GET /workdocs`
- `GET /workdocs/{id}`
- `PATCH /workdocs/{id}`
- `POST /workdocs/{id}/validate`
- `POST /workdocs/{id}/approve`
- `POST /agent-runs/from-workdoc/{id}`
- `GET /agent-runs`
- `GET /agent-runs/{id}`
- `POST /tests/run-for-agent-run/{agent_run_id}`
- `GET /tests/{test_run_id}`
- `GET /git/operations`
- `POST /git/diff/{agent_run_id}`
- `POST /git/branch-from-run/{agent_run_id}`
- `POST /git/commit-from-run/{agent_run_id}`
- `POST /git/push/{git_operation_id}`
- `POST /git/create-pr/{git_operation_id}`
- `GET /policy-decisions`
- `GET /reports/workdoc/{id}`
- `GET /reports/workdoc/{id}/markdown`
- `GET /reports/agent-run/{id}`
- `GET /wechat/health`
- `POST /wechat/poll-room`
- `POST /wechat/poll-once`
- `POST /wechat/wxauto/poll`
- `POST /wechat/wxauto/send`
- `POST /wechat/manual-export/import`
- `POST /wechat/local-db/import`
- `POST /bot/command`
- `POST /bot/process-new-messages`
- `POST /chat-feedback/task-candidate/{id}`
- `POST /chat-feedback/workdoc/{id}`
- `POST /chat-feedback/agent-run/{id}`
- `POST /chat-feedback/report/{workdoc_id}`

## Phase 9 Personal WeChat Intake

Phase 9 uses Windows WeChat Desktop UIAutomation / `wxauto` as the preferred path. It does not use direct local WeChat database reads as the main route.

Rules:

- `AGENT_WORKFLOW_PERSONAL_WECHAT_ENABLED=false` blocks real WeChat health, poll, and send.
- `AGENT_WORKFLOW_WECHAT_SEND_ENABLED=false` blocks real feedback sends.
- Only rooms listed in `AGENT_WORKFLOW_ALLOWED_WECHAT_ROOMS` can be read or sent to.
- `AGENT_WORKFLOW_WECHAT_READ_LIMIT` bounds each poll.
- `AGENT_WORKFLOW_WECHAT_CONTEXT_WINDOW_SIZE` bounds command-to-segment context.
- Private chats are not scanned; the adapter never reads all chats.
- Normal messages do not directly trigger AgentRun.
- Only messages containing `AGENT_WORKFLOW_WORKBOT_MENTION`, default `@WorkBot`, can become TaskCandidates.
- Personal WeChat messages must flow through `ChatMessage -> BotCommand -> Segment -> TaskCandidate -> WorkDoc`.
- `POST /workdocs/from-messages` rejects direct WorkDoc creation from `platform=personal_wechat`.
- `source_message_fingerprint` prevents duplicate imports even when timestamps are missing.

Supported WorkBot commands:

- `@WorkBot 记录为任务`
- `@WorkBot 生成WorkDoc`
- `@WorkBot 状态 WD-1`
- `@WorkBot 确认执行 WD-1`
- `@WorkBot 报告 WD-1`

Install `wxauto` only on a Windows host that already has WeChat Desktop open and logged in:

```bash
python -m pip install wxauto
```

Run the local polling script once in dry-run mode:

```bash
set AGENT_WORKFLOW_PERSONAL_WECHAT_ENABLED=true
set AGENT_WORKFLOW_ALLOWED_WECHAT_ROOMS=dev-group
python scripts\poll_wechat_messages.py --once --dry-run
```

On Windows, you can also double-click `F:\autowork\start_wechat_poller.bat`. It asks for the whitelisted group name, starts monitoring from the current time, prints newly imported messages, and writes prompt drafts under `.agent-work\prompts`. The launcher will try to install `wxauto` automatically if it is missing.

For WeChat groups that use default member names as the chat title, the wxauto adapter supports simple substring matching against the current session list. For example, entering `Bob` can match `Alice, Bob, Carol`. The Windows launcher prompts you to choose when multiple sessions match; direct API/script calls still reject ambiguous matches as a safety fallback.

Run the local polling script continuously:

```bash
set AGENT_WORKFLOW_PERSONAL_WECHAT_ENABLED=true
set AGENT_WORKFLOW_ALLOWED_WECHAT_ROOMS=dev-group
set AGENT_WORKFLOW_WECHAT_READ_LIMIT=50
python scripts\poll_wechat_messages.py --interval 30 --show-new
```

The poller reads only whitelisted groups, saves messages as `ChatMessage`, deduplicates through `MessageStore`, and records new `@WorkBot` commands as `BotCommandLog`. It does not create WorkDocs, run agents, or touch Git.

Start monitoring from a specific time and write prompt drafts for newly imported `@WorkBot` messages:

```bash
python scripts\poll_wechat_messages.py ^
  --interval 30 ^
  --since "2026-06-19 10:30" ^
  --show-new ^
  --write-agent-prompts .agent-work\prompts
```

Prompt drafts are local markdown files for review. They are not executed automatically and do not bypass the WorkDoc approval chain.
When `--since` is active, messages without timestamps are skipped because the poller cannot prove they are inside the requested window. Command processing is scoped to messages newly imported in the current poll cycle, so old unprocessed backlog is not mixed into the current run summary.

Poll a whitelisted group:

```bash
curl -X POST http://127.0.0.1:8000/wechat/poll-room ^
  -H "Content-Type: application/json" ^
  -d "{\"room_id\":\"你的白名单群名\",\"limit\":20}"
```

Send feedback to a whitelisted group:

```bash
curl -X POST http://127.0.0.1:8000/wechat/wxauto/send ^
  -H "Content-Type: application/json" ^
  -d "{\"room_id\":\"你的白名单群名\",\"text\":\"WorkDoc 已创建，请审核。\"}"
```

Manual export import:

```bash
curl -X POST http://127.0.0.1:8000/wechat/manual-export/import ^
  -H "Content-Type: application/json" ^
  -d "{\"file_path\":\"F:\\\\tmp\\\\chat.txt\",\"room_id\":\"dev-group\"}"
```

Database import is intentionally a stub:

```bash
curl -X POST http://127.0.0.1:8000/wechat/local-db/import ^
  -H "Content-Type: application/json" ^
  -d "{\"path\":\"F:\\\\WeChat Files\"}"
```

That endpoint returns a policy error instead of attempting decryption or database reverse engineering.

Create a WorkDoc from a WorkBot command:

```bash
curl -X POST http://127.0.0.1:8000/bot/process-new-messages
curl -X POST http://127.0.0.1:8000/segments/from-command/1 ^
  -H "Content-Type: application/json" ^
  -d "{\"context_window_size\":8}"
curl -X POST http://127.0.0.1:8000/task-candidates/from-segment/1
curl -X POST http://127.0.0.1:8000/task-candidates/1/update ^
  -H "Content-Type: application/json" ^
  -d "{\"repo_path\":\"F:\\\\tmp\\\\repo\",\"acceptance_criteria\":[\"设置按钮跳转到 /settings\"]}"
curl -X POST http://127.0.0.1:8000/task-candidates/1/convert-to-workdoc
```

Spike notes and scripts:

- `docs/personal_wechat_spike.md`
- `scripts/spike_wxauto_read_group.py`
- `scripts/spike_wxauto_send_message.py`

## Phase 8 WorkDoc Config

New WorkDocs include these config blocks while remaining compatible with old rows:

```json
{
  "execution": {
    "allowed_paths": ["**/*"],
    "forbidden_paths": [".env", "secrets.*", "*.pem", "*.key"]
  },
  "test": {
    "commands": [],
    "required": false
  },
  "agent": {
    "preferred_runner": "mock",
    "timeout_seconds": 120,
    "max_diff_lines": 1000
  },
  "git": {
    "branch_prefix": "agent-workflow",
    "commit_message_template": "WorkDoc {workdoc_id}: {title}",
    "allow_push": false,
    "allow_pr": false
  },
  "review": {
    "require_human_approval": true,
    "risk_level": "low"
  }
}
```

Approve now transitions a validated WorkDoc to `APPROVED_FOR_AGENT`. Commit dry-runs return `APPROVED_FOR_COMMIT`.

`PATCH /workdocs/{id}` lets a human repair a draft or blocked WorkDoc before re-validation. It is allowed only for `WORKDOC_DRAFTED`, `HUMAN_REVIEW_REQUIRED`, and `POLICY_BLOCKED`; successful updates reset the WorkDoc to `WORKDOC_DRAFTED`.

## Phase 8 PolicyGate

PolicyGate only decides. It does not run Git or execute shell commands.

It records decisions to `policy_decisions` for:

- WorkDoc validation
- Agent execution
- Patch review
- Commit
- Push / PR stubs

Commit is blocked when:

- acceptance criteria are missing
- WorkDoc is not approved for agent execution
- changed files match `execution.forbidden_paths`
- changed files are outside `execution.allowed_paths`
- diff line count exceeds `agent.max_diff_lines`
- `test.required=true` and no latest `TEST_PASSED` exists
- latest test status is `TEST_FAILED` or `TEST_TIMEOUT`

## Phase 8 Runner Notes

`ClaudeCliRunner` writes both:

- `.agent_workflow_workdoc.md`
- `.agent_workflow_repo_context.md`

Real Claude execution requires both:

```text
AGENT_WORKFLOW_DRY_RUN=false
AGENT_WORKFLOW_ALLOW_CLAUDE_CLI=true
```

`gagent-desktop` uses a stable request/result protocol:

- `AgentRunRequest`
- `AgentRunResult`

Supported future modes:

- `cli`
- `http`
- `local_ipc`

It remains audit-only in Phase 8 and does not modify code.

## Mock End-to-End Demo

Create or choose a local Git repo first. The demo below assumes `F:\tmp\demo-repo` exists and is already initialized with at least one commit.

1. Import a mock message:

```bash
curl -X POST http://127.0.0.1:8000/messages/import ^
  -H "Content-Type: application/json" ^
  -d "{\"messages\":[{\"room_id\":\"dev-room\",\"text\":\"首页设置按钮点了没反应，应该跳转到 /settings。先别重构，只修这个按钮。\"}]}"
```

2. Create a WorkDoc from the returned message id:

```bash
curl -X POST http://127.0.0.1:8000/workdocs/from-messages ^
  -H "Content-Type: application/json" ^
  -d "{\"message_ids\":[1],\"repo_path\":\"F:\\\\tmp\\\\demo-repo\",\"repo_name\":\"demo-repo\",\"branch_base\":\"main\"}"
```

3. Validate and approve:

```bash
curl -X POST http://127.0.0.1:8000/workdocs/1/validate
curl -X POST http://127.0.0.1:8000/workdocs/1/approve
```

4. Run the mock agent:

```bash
curl -X POST http://127.0.0.1:8000/agent-runs/from-workdoc/1 ^
  -H "Content-Type: application/json" ^
  -d "{\"agent_type\":\"mock\"}"
```

5. Run tests when configured:

```bash
curl -X POST http://127.0.0.1:8000/tests/run-for-agent-run/1
```

6. Inspect diff:

```bash
curl -X POST http://127.0.0.1:8000/git/diff/1
```

7. Preview Git commit in dry-run mode:

```bash
curl -X POST http://127.0.0.1:8000/git/commit-from-run/1 ^
  -H "Content-Type: application/json" ^
  -d "{\"dry_run\":true}"
```

8. Create a real local branch + commit:

```bash
curl -X POST http://127.0.0.1:8000/git/commit-from-run/1 ^
  -H "Content-Type: application/json" ^
  -d "{\"dry_run\":false}"
```

9. Read the report:

```bash
curl http://127.0.0.1:8000/reports/workdoc/1/markdown
```

## Runner Behavior

- `mock`: writes `agent_workflow_mock_patch.txt` inside the repo and records logs.
- `claude_cli`: writes `.agent_workflow_workdoc.md`; by default returns a command plan without invoking Claude.
- `gagent_desktop`: audit-only wrapper; by default returns a dry-run audit plan.
