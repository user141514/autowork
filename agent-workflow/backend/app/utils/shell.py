import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CommandResult:
    command: str
    exit_code: int
    stdout: str
    stderr: str


def run_command(command: list[str], cwd: str | Path | None = None, timeout_seconds: int = 120) -> CommandResult:
    try:
        process = subprocess.run(
            command,
            cwd=str(cwd) if cwd is not None else None,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        return CommandResult(
            command=" ".join(command),
            exit_code=124,
            stdout=(exc.stdout or "") if isinstance(exc.stdout, str) else "",
            stderr=f"Command timed out after {timeout_seconds}s",
        )
    return CommandResult(
        command=" ".join(command),
        exit_code=process.returncode,
        stdout=process.stdout,
        stderr=process.stderr,
    )


def run_shell_command(command: str, cwd: str | Path | None = None, timeout_seconds: int = 120) -> CommandResult:
    try:
        process = subprocess.run(
            command,
            cwd=str(cwd) if cwd is not None else None,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
            check=False,
            shell=True,
        )
    except subprocess.TimeoutExpired as exc:
        return CommandResult(
            command=command,
            exit_code=124,
            stdout=(exc.stdout or "") if isinstance(exc.stdout, str) else "",
            stderr=f"Command timed out after {timeout_seconds}s",
        )
    return CommandResult(
        command=command,
        exit_code=process.returncode,
        stdout=process.stdout,
        stderr=process.stderr,
    )
