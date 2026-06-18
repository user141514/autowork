from pydantic import BaseModel, Field


class RepoContextRead(BaseModel):
    project_type: str
    package_manager: str | None
    important_files: list[str] = Field(default_factory=list)
    test_commands: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    generated_context_path: str
