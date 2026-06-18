from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


def _ensure_sqlite_parent(database_url: str) -> None:
    prefix = "sqlite:///"
    if not database_url.startswith(prefix):
        return

    db_path = database_url.removeprefix(prefix)
    if db_path in {"", ":memory:"}:
        return

    Path(db_path).parent.mkdir(parents=True, exist_ok=True)


settings = get_settings()
_ensure_sqlite_parent(settings.database_url)

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if settings.database_url.startswith("sqlite") else {},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db() -> None:
    from app import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _ensure_sqlite_compat_columns()


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _ensure_sqlite_compat_columns() -> None:
    if not settings.database_url.startswith("sqlite"):
        return

    table_columns = {
        "workdocs": {
            "execution": "JSON DEFAULT '{}'",
            "test": "JSON DEFAULT '{}'",
            "agent": "JSON DEFAULT '{}'",
            "git": "JSON DEFAULT '{}'",
            "review": "JSON DEFAULT '{}'",
        },
        "agent_runs": {
            "input_json": "JSON DEFAULT '{}'",
            "diff_summary": "TEXT DEFAULT ''",
            "changed_files": "JSON DEFAULT '[]'",
        },
        "git_operations": {
            "pr_url": "VARCHAR(1024)",
            "changed_files": "JSON DEFAULT '[]'",
            "diff_stats": "JSON DEFAULT '{}'",
        },
    }

    with engine.begin() as connection:
        for table_name, columns in table_columns.items():
            existing = {
                row[1]
                for row in connection.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
            }
            if not existing:
                continue
            for column_name, column_type in columns.items():
                if column_name not in existing:
                    connection.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}"))
