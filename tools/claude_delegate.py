from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_MAX_TURNS = 3
DEFAULT_MAX_BUDGET_USD = "0.25"
DEFAULT_TIMEOUT_SECONDS = 900


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    repo_root = resolve_repo_root(Path(args.repo_root or os.getcwd()))
    claude_path = shutil.which("claude")
    unsupported_flags = unsupported_required_flags(claude_path) if claude_path else []

    if args.self_check:
        claude_help = read_claude_help(claude_path) if claude_path else ""
        payload = {
            "repo_root": str(repo_root),
            "claude_available": claude_path is not None,
            "claude_path": claude_path,
            "required_flags": {
                "-p": "-p" in claude_help or "--print" in claude_help,
                "--bare": "--bare" in claude_help,
                "--permission-mode": "--permission-mode" in claude_help,
                "--tools": "--tools" in claude_help,
                "--strict-mcp-config": "--strict-mcp-config" in claude_help,
                "--max-turns": "--max-turns" in claude_help,
                "--max-budget-usd": "--max-budget-usd" in claude_help,
            },
            "artifact_root": str(repo_root / ".agent-work" / "claude"),
        }
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0

    prompt = read_prompt(args, repo_root)
    run_id = args.run_id or make_run_id(args.task_name, args.mode)
    run_dir = repo_root / ".agent-work" / "claude" / run_id
    run_dir.mkdir(parents=True, exist_ok=False)

    guarded_prompt = build_guarded_prompt(prompt, args.mode, repo_root)
    prompt_path = run_dir / "prompt.md"
    stdout_path = run_dir / "stdout.txt"
    stderr_path = run_dir / "stderr.txt"
    metadata_path = run_dir / "metadata.json"
    command_path = run_dir / "command.json"
    response_path = resolve_response_path(args, repo_root) if args.dumb else None

    prompt_path.write_text(guarded_prompt, encoding="utf-8")

    command = build_claude_command(
        claude_path or "claude",
        max_turns=args.max_turns,
        max_budget_usd=None if args.no_budget_limit else args.max_budget_usd,
        unsupported_flags=unsupported_flags,
    )
    command_path.write_text(json.dumps(command, indent=2, ensure_ascii=False), encoding="utf-8")

    started_at = now_iso()
    before_status = git_status(repo_root)
    metadata: dict[str, object] = {
        "run_id": run_id,
        "mode": args.mode,
        "task_name": args.task_name,
        "repo_root": str(repo_root),
        "run_dir": str(run_dir),
        "prompt_path": str(prompt_path),
        "stdout_path": str(stdout_path),
        "stderr_path": str(stderr_path),
        "command_path": str(command_path),
        "response_path": str(response_path) if response_path else None,
        "claude_available": claude_path is not None,
        "claude_path": claude_path,
        "command": command,
        "max_turns": args.max_turns,
        "max_budget_usd": None if args.no_budget_limit else args.max_budget_usd,
        "no_budget_limit": args.no_budget_limit,
        "timeout_seconds": args.timeout_seconds,
        "dry_run": args.dry_run,
        "started_at": started_at,
        "git_status_before": before_status,
    }

    if claude_path is None:
        message = "claude executable not found in PATH. Install Claude Code CLI or update PATH."
        stdout_path.write_text("", encoding="utf-8")
        stderr_path.write_text(message + "\n", encoding="utf-8")
        metadata.update(
            {
                "status": "missing_claude",
                "returncode": 127,
                "finished_at": now_iso(),
                "elapsed_seconds": 0,
                "git_status_after": git_status(repo_root),
                "workspace_changed_by_worker": False,
            }
        )
        metadata_path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")
        write_dumb_response(response_path, metadata, stdout_path, stderr_path)
        print(f"[claude_delegate] {message}", file=sys.stderr)
        print(f"[claude_delegate] artifacts: {run_dir}", file=sys.stderr)
        return 127

    metadata["unsupported_required_flags"] = unsupported_flags

    if args.dry_run:
        stdout_path.write_text("", encoding="utf-8")
        stderr_path.write_text("dry run: Claude was not invoked\n", encoding="utf-8")
        metadata.update(
            {
                "status": "dry_run",
                "returncode": 0,
                "finished_at": now_iso(),
                "elapsed_seconds": 0,
                "git_status_after": git_status(repo_root),
                "workspace_changed_by_worker": False,
            }
        )
        metadata_path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")
        write_dumb_response(response_path, metadata, stdout_path, stderr_path)
        print(json.dumps({"run_id": run_id, "run_dir": str(run_dir), "status": "dry_run"}, ensure_ascii=False))
        return 0

    start_monotonic = time.monotonic()
    status = "completed"
    returncode = 0
    try:
        result = subprocess.run(
            command,
            input=guarded_prompt,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=repo_root,
            capture_output=True,
            timeout=args.timeout_seconds,
            check=False,
        )
        stdout_path.write_text(result.stdout, encoding="utf-8")
        stderr_path.write_text(result.stderr, encoding="utf-8")
        returncode = result.returncode
        if result.returncode != 0:
            status = "failed"
    except subprocess.TimeoutExpired as exc:
        status = "timeout"
        returncode = 124
        stdout_path.write_text(exc.stdout or "", encoding="utf-8")
        stderr_path.write_text((exc.stderr or "") + f"\nTimed out after {args.timeout_seconds} seconds.\n", encoding="utf-8")

    after_status = git_status(repo_root)
    workspace_changed = before_status != after_status
    if workspace_changed:
        status = "workspace_changed_by_worker"
        if returncode == 0:
            returncode = 4

    metadata.update(
        {
            "status": status,
            "returncode": returncode,
            "finished_at": now_iso(),
            "elapsed_seconds": round(time.monotonic() - start_monotonic, 3),
            "git_status_after": after_status,
            "workspace_changed_by_worker": workspace_changed,
        }
    )
    metadata_path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")
    write_dumb_response(response_path, metadata, stdout_path, stderr_path)

    print(json.dumps({"run_id": run_id, "run_dir": str(run_dir), "status": status}, ensure_ascii=False))
    return returncode


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Read-only Claude Code CLI delegation wrapper for the Codex supervisor."
    )
    parser.add_argument("--prompt", help="Task prompt to delegate. If omitted, stdin is used when available.")
    parser.add_argument("--prompt-file", help="Read the delegated task prompt from a UTF-8 file.")
    parser.add_argument("--mode", choices=["analysis", "review", "patch", "second-opinion"], default="analysis")
    parser.add_argument("--task-name", default="delegate", help="Short human-readable task label for the run id.")
    parser.add_argument("--repo-root", help="Repository root. Defaults to git root or current directory.")
    parser.add_argument("--run-id", help="Optional explicit run id.")
    parser.add_argument("--max-turns", type=int, default=DEFAULT_MAX_TURNS)
    budget_group = parser.add_mutually_exclusive_group()
    budget_group.add_argument("--max-budget-usd", default=DEFAULT_MAX_BUDGET_USD)
    budget_group.add_argument("--no-budget-limit", action="store_true", help="Do not pass --max-budget-usd to Claude.")
    parser.add_argument("--timeout-seconds", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--dry-run", action="store_true", help="Create artifacts and command plan without invoking Claude.")
    parser.add_argument("--self-check", action="store_true", help="Report wrapper readiness without invoking Claude.")
    parser.add_argument(
        "--dumb",
        action="store_true",
        help="Read paln.md and write response.md in the repo root, while still storing full artifacts.",
    )
    parser.add_argument("--plan-file", default="paln.md", help="Plan file for --dumb mode. Defaults to paln.md.")
    parser.add_argument("--response-file", default="response.md", help="Response file for --dumb mode.")
    return parser


def read_prompt(args: argparse.Namespace, repo_root: Path) -> str:
    if args.prompt and args.prompt_file:
        raise SystemExit("Use only one of --prompt or --prompt-file.")
    if args.dumb and not args.prompt and not args.prompt_file:
        plan_path = resolve_plan_path(args, repo_root)
        if not plan_path.exists():
            raise SystemExit(f"Dumb mode plan file not found: {plan_path}")
        return ensure_nonempty_prompt(plan_path.read_text(encoding="utf-8"))
    if args.prompt_file:
        return ensure_nonempty_prompt(Path(args.prompt_file).read_text(encoding="utf-8"))
    if args.prompt:
        return ensure_nonempty_prompt(args.prompt)
    if not sys.stdin.isatty():
        return ensure_nonempty_prompt(sys.stdin.read())
    raise SystemExit("No prompt provided. Use --prompt, --prompt-file, or stdin.")


def resolve_plan_path(args: argparse.Namespace, repo_root: Path) -> Path:
    path = Path(args.plan_file)
    if not path.is_absolute():
        path = repo_root / path
    return path.resolve()


def resolve_response_path(args: argparse.Namespace, repo_root: Path) -> Path:
    path = Path(args.response_file)
    if not path.is_absolute():
        path = repo_root / path
    return path.resolve()


def ensure_nonempty_prompt(prompt: str) -> str:
    if not prompt.strip():
        raise SystemExit("Prompt is empty.")
    return prompt


def resolve_repo_root(start: Path) -> Path:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=start,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            check=True,
        )
        return Path(result.stdout.strip()).resolve()
    except Exception:
        return start.resolve()


def make_run_id(task_name: str, mode: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    safe_task = "".join(ch if ch.isalnum() else "-" for ch in task_name.lower()).strip("-") or "delegate"
    safe_task = "-".join(part for part in safe_task.split("-") if part)[:48]
    return f"{stamp}-{mode}-{safe_task}-{uuid.uuid4().hex[:8]}"


def build_claude_command(
    claude_path: str,
    max_turns: int,
    max_budget_usd: str | None,
    unsupported_flags: list[str] | None = None,
) -> list[str]:
    unsupported = set(unsupported_flags or [])
    command = [
        claude_path,
        "-p",
        "--bare",
        "--permission-mode",
        "plan",
        "--tools",
        "Read,Bash",
        "--strict-mcp-config",
    ]
    if "--max-turns" not in unsupported:
        command.extend(["--max-turns", str(max_turns)])
    if max_budget_usd is not None and "--max-budget-usd" not in unsupported:
        command.extend(["--max-budget-usd", str(max_budget_usd)])
    return command


def build_guarded_prompt(prompt: str, mode: str, repo_root: Path) -> str:
    mode_instruction = {
        "analysis": "Return concise findings with file references, evidence, risks, and recommended next steps.",
        "review": "Act as a reviewer. Put bug/risk findings first, with severity and file references. Do not apply fixes.",
        "patch": "Draft a unified diff only when implementation is requested. Do not apply it. Include assumptions after the diff.",
        "second-opinion": "Give a second opinion on the proposed approach. Focus on hidden risks, missing tests, and simpler options.",
    }[mode]
    return f"""# Claude Delegation Request

You are Claude Code CLI acting only as an external read-only worker for a Codex supervisor.

Hard rules:
- Codex is the only supervisor and the only actor allowed to make final code edits.
- Do not edit, create, delete, move, format, or stage files in the current workspace.
- Do not run commands with side effects. Use Bash only for read-only inspection commands.
- Do not run tests unless explicitly asked and only if the command is read-only with respect to source files.
- If implementation is requested, output a proposed unified diff or a plan; do not apply it.
- Treat secrets, credentials, local databases, and private chat logs as out of scope.
- Report uncertainty instead of guessing.

Repository root: {repo_root}
Delegation mode: {mode}
Expected output: {mode_instruction}

## Task

{prompt.strip()}
"""


def git_status(repo_root: Path) -> dict[str, object]:
    if not (repo_root / ".git").exists():
        return {"available": False, "reason": "not a git repository"}
    return {
        "available": True,
        "head": run_text(["git", "rev-parse", "HEAD"], repo_root),
        "branch": run_text(["git", "branch", "--show-current"], repo_root),
        "short": run_text(["git", "status", "--short"], repo_root),
    }


def run_text(command: list[str], cwd: Path) -> str:
    try:
        result = subprocess.run(
            command,
            cwd=cwd,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            check=False,
        )
        return result.stdout.strip()
    except Exception as exc:
        return f"ERROR: {exc}"


def write_dumb_response(
    response_path: Path | None,
    metadata: dict[str, object],
    stdout_path: Path,
    stderr_path: Path,
) -> None:
    if response_path is None:
        return
    stdout_text = stdout_path.read_text(encoding="utf-8", errors="replace") if stdout_path.exists() else ""
    stderr_text = stderr_path.read_text(encoding="utf-8", errors="replace") if stderr_path.exists() else ""
    response_path.parent.mkdir(parents=True, exist_ok=True)
    response_path.write_text(
        "\n".join(
            [
                "# Claude Worker Response",
                "",
                "## Metadata",
                "",
                f"- run_id: `{metadata.get('run_id')}`",
                f"- status: `{metadata.get('status')}`",
                f"- returncode: `{metadata.get('returncode')}`",
                f"- run_dir: `{metadata.get('run_dir')}`",
                f"- workspace_changed_by_worker: `{metadata.get('workspace_changed_by_worker')}`",
                f"- unsupported_required_flags: `{metadata.get('unsupported_required_flags')}`",
                "",
                "## Stdout",
                "",
                "```text",
                stdout_text.rstrip(),
                "```",
                "",
                "## Stderr",
                "",
                "```text",
                stderr_text.rstrip(),
                "```",
                "",
            ]
        ),
        encoding="utf-8",
    )


def read_claude_help(claude_path: str) -> str:
    try:
        result = subprocess.run(
            [claude_path, "--help"],
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            check=False,
        )
        return f"{result.stdout}\n{result.stderr}"
    except Exception:
        return ""


def unsupported_required_flags(claude_path: str) -> list[str]:
    help_text = read_claude_help(claude_path)
    required = {
        "-p": ["-p", "--print"],
        "--bare": ["--bare"],
        "--permission-mode": ["--permission-mode"],
        "--tools": ["--tools"],
        "--strict-mcp-config": ["--strict-mcp-config"],
        "--max-turns": ["--max-turns"],
        "--max-budget-usd": ["--max-budget-usd"],
    }
    missing: list[str] = []
    for flag, alternatives in required.items():
        if not any(alternative in help_text for alternative in alternatives):
            missing.append(flag)
    return missing


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


if __name__ == "__main__":
    raise SystemExit(main())
