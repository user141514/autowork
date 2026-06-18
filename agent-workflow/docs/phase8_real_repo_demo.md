# Phase 8 Real Repo Demo

This demo strengthens the semi-real execution loop without connecting real WeChat.

## 1. Prepare a Local Repo

Create or pick a local Git repo with at least one commit.

```bash
mkdir F:\tmp\phase8-demo-repo
cd F:\tmp\phase8-demo-repo
git init
git checkout -b main
git config user.email "agent-workflow@example.test"
git config user.name "Agent Workflow"
echo "# demo" > README.md
git add README.md
git commit -m "initial commit"
```

## 2. Start Backend

```bash
cd F:\autowork\agent-workflow\backend
python -m pip install -e ".[dev]"
uvicorn app.main:app --reload
```

Dashboard:

```text
http://127.0.0.1:8000/dashboard
```

## 3. Import Mock Chat Message

```bash
curl -X POST http://127.0.0.1:8000/messages/import ^
  -H "Content-Type: application/json" ^
  -d "{\"messages\":[{\"room_id\":\"dev-room\",\"text\":\"首页设置按钮点了没反应，应该跳转到 /settings。先别重构，只修这个按钮。\"}]}"
```

Record the returned message id.

## 4. Create WorkDoc

```bash
curl -X POST http://127.0.0.1:8000/workdocs/from-messages ^
  -H "Content-Type: application/json" ^
  -d "{\"message_ids\":[1],\"repo_path\":\"F:\\\\tmp\\\\phase8-demo-repo\",\"repo_name\":\"phase8-demo\",\"branch_base\":\"main\",\"test\":{\"commands\":[],\"required\":false}}"
```

The new WorkDoc includes:

- `execution.allowed_paths`
- `execution.forbidden_paths`
- `test.commands`
- `test.required`
- `agent.preferred_runner`
- `agent.timeout_seconds`
- `agent.max_diff_lines`
- `git.branch_prefix`
- `git.commit_message_template`
- `git.allow_push`
- `git.allow_pr`
- `review.require_human_approval`
- `review.risk_level`

## 5. Validate And Approve

```bash
curl -X POST http://127.0.0.1:8000/workdocs/1/validate
curl -X POST http://127.0.0.1:8000/workdocs/1/approve
```

Approve transitions the WorkDoc to `APPROVED_FOR_AGENT`.

## 6. Build RepoContext

RepoContext is built automatically when an AgentRun starts. It scans the repo, detects project type, finds important files, detects test commands, and writes:

```text
.agent_workflow_repo_context.md
```

The generated context is also saved into `AgentRun.input_json`.

## 7. Run Claude CLI Or gagent-desktop

Claude CLI dry-run:

```bash
curl -X POST http://127.0.0.1:8000/agent-runs/from-workdoc/1 ^
  -H "Content-Type: application/json" ^
  -d "{\"agent_type\":\"claude_cli\"}"
```

Real Claude CLI execution requires:

```text
AGENT_WORKFLOW_DRY_RUN=false
AGENT_WORKFLOW_ALLOW_CLAUDE_CLI=true
```

gagent-desktop audit dry-run:

```bash
curl -X POST http://127.0.0.1:8000/agent-runs/from-workdoc/1 ^
  -H "Content-Type: application/json" ^
  -d "{\"agent_type\":\"gagent_desktop\"}"
```

gagent-desktop modes are fixed as:

- `cli`
- `http`
- `local_ipc`

Phase 8 keeps gagent-desktop audit-only.

## 8. Detect Diff

```bash
curl -X POST http://127.0.0.1:8000/git/diff/1
```

Diff detection includes tracked and untracked files.

## 9. Run Tests

```bash
curl -X POST http://127.0.0.1:8000/tests/run-for-agent-run/1
```

Possible statuses:

- `TEST_PASSED`
- `TEST_FAILED`
- `TEST_TIMEOUT`
- `TEST_NOT_CONFIGURED`

If `WorkDoc.test.required=true`, commit requires latest status `TEST_PASSED`.

## 10. Policy Check

PolicyGate runs automatically before Agent execution, patch acceptance, commit, push, and PR.

Decisions are stored in `policy_decisions`.

PolicyGate blocks:

- missing acceptance criteria
- unapproved WorkDoc
- forbidden paths
- diff exceeding max lines
- failed or missing required tests
- push / PR when dry-run or disabled

## 11. Commit

Dry-run:

```bash
curl -X POST http://127.0.0.1:8000/git/commit-from-run/1 ^
  -H "Content-Type: application/json" ^
  -d "{\"dry_run\":true}"
```

Real local branch + commit:

```bash
curl -X POST http://127.0.0.1:8000/git/commit-from-run/1 ^
  -H "Content-Type: application/json" ^
  -d "{\"dry_run\":false}"
```

Push and PR are intentionally blocked by default:

```bash
curl -X POST http://127.0.0.1:8000/git/push/1
curl -X POST http://127.0.0.1:8000/git/create-pr/1
```

## 12. Generate Report

WorkDoc report:

```bash
curl http://127.0.0.1:8000/reports/workdoc/1/markdown
```

AgentRun report:

```bash
curl http://127.0.0.1:8000/reports/agent-run/1
```

The report includes:

- WorkDoc summary
- source evidence
- Agent execution logs
- changed files
- diff summary
- test result
- policy decision
- git branch / commit / PR
- final status

