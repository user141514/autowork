from pathlib import Path

from app.services.errors import InvalidStateError, NotFoundError
from app.utils.shell import run_command


class GitInspector:
    def ensure_git_repo(self, repo: Path) -> None:
        if not repo.exists():
            raise NotFoundError(f"repo_path does not exist: {repo}")
        result = run_command(["git", "rev-parse", "--is-inside-work-tree"], cwd=repo)
        if result.exit_code != 0 or result.stdout.strip() != "true":
            raise InvalidStateError(f"repo_path is not a git repository: {repo}")

    def changed_files(self, repo: Path) -> list[str]:
        result = run_command(["git", "diff", "--name-only"], cwd=repo)
        staged = run_command(["git", "diff", "--cached", "--name-only"], cwd=repo)
        untracked = run_command(["git", "ls-files", "--others", "--exclude-standard"], cwd=repo)
        names = [
            line.strip()
            for line in f"{result.stdout}\n{staged.stdout}\n{untracked.stdout}".splitlines()
            if line.strip()
        ]
        return sorted(set(names))

    def diff_summary(self, repo: Path) -> str:
        result = run_command(["git", "diff", "--stat"], cwd=repo)
        status = run_command(["git", "status", "--short"], cwd=repo)
        summary_parts = [part.strip() for part in [result.stdout, status.stdout] if part.strip()]
        return "\n".join(summary_parts) if summary_parts else "(no diff summary)"

    def diff_stats(self, repo: Path) -> dict:
        result = run_command(["git", "diff", "--numstat"], cwd=repo)
        total_added = 0
        total_deleted = 0
        file_count = 0
        for line in result.stdout.splitlines():
            parts = line.split("\t")
            if len(parts) < 3:
                continue
            added, deleted = parts[0], parts[1]
            if added.isdigit():
                total_added += int(added)
            if deleted.isdigit():
                total_deleted += int(deleted)
            file_count += 1
        untracked_files = [
            line for line in run_command(["git", "ls-files", "--others", "--exclude-standard"], cwd=repo).stdout.splitlines() if line
        ]
        untracked_count = len(untracked_files)
        untracked_lines = sum(_safe_line_count(repo / file_name) for file_name in untracked_files)
        return {
            "files": file_count + untracked_count,
            "added": total_added + untracked_lines,
            "deleted": total_deleted,
            "untracked": untracked_count,
            "total_lines": total_added + total_deleted + untracked_lines,
        }


def _safe_line_count(path: Path) -> int:
    try:
        return len(path.read_text(encoding="utf-8", errors="replace").splitlines())
    except OSError:
        return 0
