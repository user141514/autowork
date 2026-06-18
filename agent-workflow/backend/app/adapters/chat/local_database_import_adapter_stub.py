from app.services.errors import PolicyViolationError


class LocalDatabaseImportAdapterStub:
    def import_database(self, path: str, room_id: str | None = None) -> None:
        raise PolicyViolationError(
            "Local WeChat database import is intentionally not implemented. "
            "This project does not bypass encryption or reverse engineer WeChat databases."
        )
