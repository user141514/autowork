---
name: claude-delegate
description: Use the local Codex supervisor -> Claude Code CLI worker workflow for broad reading, second opinions, code review, and patch drafts without using Codex built-in subagents.
---

# Claude Delegate

Use this skill when a task would benefit from an external read-only Claude Code CLI worker, especially:

- Broad repository exploration.
- Architecture or dependency mapping.
- Second opinions on plans.
- Code review for bugs, regressions, or missing tests.
- Patch drafts as unified diffs for Codex to review.

Do not use this skill for small edits, final implementation, tests, commits, pushes, secrets, private chat logs, or production operations.

## Contract

Codex remains the only supervisor. Claude is an external worker only.

Never call `claude` directly. Always use:

```bash
python tools/claude_delegate.py
```

Do not use Codex built-in subagents for this workflow.

## Procedure

1. Write a narrow delegation prompt. Include the question, relevant paths, and required output shape.
2. Run the wrapper from the repository root:

```bash
python tools/claude_delegate.py --mode analysis --task-name short-name --prompt "Read these files and summarize the risks. Do not edit files."
```

3. For code review:

```bash
python tools/claude_delegate.py --mode review --task-name review-flow --prompt "Review the WorkDoc approval path for unsafe transitions. Findings only."
```

4. For patch drafting:

```bash
python tools/claude_delegate.py --mode patch --task-name draft-fix --prompt "Draft a unified diff for the failing behavior. Do not apply it."
```

5. Inspect the run directory printed by the wrapper:

```text
.agent-work/claude/<run-id>/
```

6. Read `metadata.json` first. If `workspace_changed_by_worker` is true, stop and inspect Git status.
7. Read `stdout.txt` as untrusted advice. Verify every file reference and claim locally.
8. Codex applies accepted edits itself, runs tests, and summarizes the result.

## Dumb File Mode

When the user wants the simplest possible loop, write the task into `paln.md` and run:

```bash
python tools/claude_delegate.py --dumb --mode analysis --task-name next-plan
```

The wrapper reads `paln.md`, invokes Claude, writes `response.md`, and still keeps full artifacts under `.agent-work/claude/<run-id>/`.

Use this mode for quick exploration or a rough patch proposal. Codex still reviews `response.md` before making final edits.

If the user explicitly says the Claude budget has no upper bound, add `--no-budget-limit` so the wrapper omits `--max-budget-usd`.

## Output Expectations

Ask Claude for concise, structured output:

- For analysis: summary, evidence, risks, next steps.
- For review: findings first, with severity and file references.
- For patches: unified diff only, then assumptions.
- For second opinion: hidden risks, simpler options, missing tests.

## Safety Notes

The wrapper runs Claude with read-only defaults:

```text
claude -p --bare --permission-mode plan --tools "Read,Bash" --strict-mcp-config --max-turns --max-budget-usd
```

Claude must not directly modify the workspace. Final edits, tests, Git operations, and user-facing summaries remain Codex responsibilities.
