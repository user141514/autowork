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

Not implemented:

- Real WeChat login or long-running polling
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

## Minimal API

- `POST /messages/import`
- `GET /messages`
- `POST /workdocs/from-messages`
- `GET /workdocs`
- `GET /workdocs/{id}`
- `POST /workdocs/{id}/validate`
- `POST /workdocs/{id}/approve`
- `POST /agent-runs/from-workdoc/{id}`
- `GET /agent-runs/{id}`
- `POST /tests/run-for-agent-run/{agent_run_id}`
- `GET /tests/{test_run_id}`
- `POST /git/diff/{agent_run_id}`
- `POST /git/branch-from-run/{agent_run_id}`
- `POST /git/commit-from-run/{agent_run_id}`
- `POST /git/push/{git_operation_id}`
- `POST /git/create-pr/{git_operation_id}`
- `GET /reports/workdoc/{id}`
- `GET /reports/workdoc/{id}/markdown`
- `GET /reports/agent-run/{id}`

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
