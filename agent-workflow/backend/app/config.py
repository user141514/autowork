import os
from functools import lru_cache

from pydantic import BaseModel, Field


class Settings(BaseModel):
    app_name: str = Field(default="Agent Workflow")
    environment: str = Field(default="local")
    database_url: str = Field(default="sqlite:///./data/agent_workflow.db")
    log_level: str = Field(default="INFO")
    dry_run: bool = Field(default=True)
    allow_claude_cli: bool = Field(default=False)
    allow_gagent_desktop: bool = Field(default=False)
    gagent_desktop_mode: str = Field(default="local_ipc")
    gagent_desktop_endpoint: str | None = Field(default=None)
    default_agent_timeout_seconds: int = Field(default=120)
    protected_branches: tuple[str, ...] = Field(default=("main", "master", "production"))


def _env_bool(name: str, default: bool) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    return raw_value.strip().lower() in {"1", "true", "yes", "on"}


@lru_cache
def get_settings() -> Settings:
    return Settings(
        app_name=os.getenv("AGENT_WORKFLOW_APP_NAME", "Agent Workflow"),
        environment=os.getenv("AGENT_WORKFLOW_ENVIRONMENT", "local"),
        database_url=os.getenv("AGENT_WORKFLOW_DATABASE_URL", "sqlite:///./data/agent_workflow.db"),
        log_level=os.getenv("AGENT_WORKFLOW_LOG_LEVEL", "INFO"),
        dry_run=_env_bool("AGENT_WORKFLOW_DRY_RUN", True),
        allow_claude_cli=_env_bool("AGENT_WORKFLOW_ALLOW_CLAUDE_CLI", False),
        allow_gagent_desktop=_env_bool("AGENT_WORKFLOW_ALLOW_GAGENT_DESKTOP", False),
        gagent_desktop_mode=os.getenv("AGENT_WORKFLOW_GAGENT_DESKTOP_MODE", "local_ipc"),
        gagent_desktop_endpoint=os.getenv("AGENT_WORKFLOW_GAGENT_DESKTOP_ENDPOINT"),
        default_agent_timeout_seconds=int(os.getenv("AGENT_WORKFLOW_DEFAULT_AGENT_TIMEOUT_SECONDS", "120")),
    )
