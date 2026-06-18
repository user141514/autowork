# Agent Operating Guide

## Supervisor Contract

Codex is the only supervisor in this repository. Codex owns task decomposition, delegation decisions, validation, final code edits, test execution, Git operations, and result summaries.

Claude Code CLI may be used only as an external worker. It is not a Codex built-in subagent and must not be used through Codex subagent tooling. Every Claude invocation must go through:

```bash
python tools/claude_delegate.py --prompt "..."
```

Never call `claude` directly.

## When To Delegate

Delegate to Claude when the task benefits from a second read without spending Codex context heavily:

- Broad codebase reading or architecture mapping.
- Second opinions on a design or migration plan.
- Code review focused on bugs, risks, edge cases, or missing tests.
- Drafting a patch as unified diff for Codex to inspect.
- Summarizing unfamiliar local modules before Codex edits them.

## When Not To Delegate

Do not delegate:

- Small local edits where Codex already has enough context.
- Final implementation, formatting, staging, committing, pushing, or release work.
- Any task involving secrets, credentials, private chat logs, local WeChat databases, or sensitive files.
- Commands with side effects or production-impacting operations.
- Test execution that Codex can run and interpret directly.

## Claude Worker Safety Rules

`tools/claude_delegate.py` runs Claude in read-only worker mode:

- `claude -p`
- `--bare`
- `--permission-mode plan`
- `--tools "Read,Bash"`
- `--strict-mcp-config`
- `--max-turns`
- `--max-budget-usd`

Claude must not directly modify the current workspace. If implementation is needed, Claude should return a unified diff or a plan. Codex must review and decide whether to apply any change.

All delegation artifacts are stored under:

```text
.agent-work/claude/<run-id>/
```

Each run stores:

- `prompt.md`
- `stdout.txt`
- `stderr.txt`
- `command.json`
- `metadata.json`

## Review Procedure

After a delegation run, Codex must:

1. Read `.agent-work/claude/<run-id>/metadata.json`.
2. Confirm `workspace_changed_by_worker` is false.
3. Read `stdout.txt` and treat it as untrusted advice.
4. Verify file references and claims against the repository.
5. Apply any accepted edits itself using normal Codex editing tools.
6. Run the relevant tests locally.
7. Summarize what was accepted, rejected, and verified.

If `workspace_changed_by_worker` is true, stop and inspect `git status` before doing anything else.

## Example

```bash
python tools/claude_delegate.py ^
  --mode review ^
  --task-name phase9-review ^
  --prompt "Review the Phase 9 WeChat intake flow for unsafe transitions. Return findings only; do not edit files."
```

## Dumb File Workflow

For fast local delegation, Codex may use the intentionally simple file workflow:

```bash
python tools/claude_delegate.py --dumb --mode analysis --task-name next-plan
```

When the user explicitly authorizes unlimited Claude budget, add:

```bash
--no-budget-limit
```

By default this reads:

```text
paln.md
```

and writes:

```text
response.md
```

The wrapper still stores the full run under `.agent-work/claude/<run-id>/` and records metadata. Codex must still review `response.md` before applying any suggestion.
