import json
from pathlib import Path

from app.models.workdoc import WorkDoc
from app.schemas.repo_context import RepoContextRead


class RepoContextBuilder:
    def build(self, workdoc: WorkDoc, repo_path: str) -> RepoContextRead:
        repo = Path(repo_path).resolve()
        if not repo.exists():
            raise FileNotFoundError(f"repo_path does not exist: {repo}")
        if not repo.is_dir():
            raise NotADirectoryError(f"repo_path is not a directory: {repo}")

        project_type = self._project_type(repo)
        package_manager = self._package_manager(repo)
        important_files = self._important_files(repo)
        test_commands = self._test_commands(repo, workdoc)
        constraints = list(workdoc.constraints or [])
        generated_context_path = repo / ".agent_workflow_repo_context.md"
        generated_context_path.write_text(
            self._render_context(
                repo=repo,
                workdoc=workdoc,
                project_type=project_type,
                package_manager=package_manager,
                important_files=important_files,
                test_commands=test_commands,
                constraints=constraints,
            ),
            encoding="utf-8",
        )

        return RepoContextRead(
            project_type=project_type,
            package_manager=package_manager,
            important_files=important_files,
            test_commands=test_commands,
            constraints=constraints,
            generated_context_path=str(generated_context_path),
        )

    def _project_type(self, repo: Path) -> str:
        if (repo / "package.json").exists():
            return "node"
        if (repo / "pyproject.toml").exists() or (repo / "requirements.txt").exists():
            return "python"
        if (repo / "Cargo.toml").exists():
            return "rust"
        return "unknown"

    def _package_manager(self, repo: Path) -> str | None:
        if (repo / "pnpm-lock.yaml").exists():
            return "pnpm"
        if (repo / "yarn.lock").exists():
            return "yarn"
        if (repo / "package-lock.json").exists() or (repo / "package.json").exists():
            return "npm"
        if (repo / "uv.lock").exists():
            return "uv"
        if (repo / "poetry.lock").exists():
            return "poetry"
        if (repo / "requirements.txt").exists() or (repo / "pyproject.toml").exists():
            return "python"
        if (repo / "Cargo.toml").exists():
            return "cargo"
        return None

    def _important_files(self, repo: Path) -> list[str]:
        candidates = [
            "README.md",
            "pyproject.toml",
            "requirements.txt",
            "package.json",
            "tsconfig.json",
            "vite.config.ts",
            "next.config.js",
            "Cargo.toml",
            ".gitignore",
        ]
        return [candidate for candidate in candidates if (repo / candidate).exists()]

    def _test_commands(self, repo: Path, workdoc: WorkDoc) -> list[str]:
        configured = (workdoc.test or {}).get("commands") or []
        if configured:
            return configured

        package_json = repo / "package.json"
        if package_json.exists():
            try:
                data = json.loads(package_json.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                data = {}
            scripts = data.get("scripts", {})
            if "test" in scripts:
                return ["npm test"]

        if (repo / "pyproject.toml").exists() or (repo / "pytest.ini").exists():
            return ["python -m pytest"]
        if (repo / "Cargo.toml").exists():
            return ["cargo test"]
        return []

    def _render_context(
        self,
        repo: Path,
        workdoc: WorkDoc,
        project_type: str,
        package_manager: str | None,
        important_files: list[str],
        test_commands: list[str],
        constraints: list[str],
    ) -> str:
        lines = [
            f"# Repo Context for WorkDoc {workdoc.id}",
            "",
            f"Repo path: {repo}",
            f"Project type: {project_type}",
            f"Package manager: {package_manager or 'unknown'}",
            "",
            "## Important Files",
            *[f"- {item}" for item in important_files],
            "",
            "## Test Commands",
            *[f"- {item}" for item in test_commands],
            "",
            "## Constraints",
            *[f"- {item}" for item in constraints],
            "",
            "Agents must treat WorkDoc as the task contract and must not infer extra requirements from chat logs.",
        ]
        return "\n".join(lines)
