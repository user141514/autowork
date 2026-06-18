from fastapi.testclient import TestClient

from app.database import Base, engine
from app.main import create_app


def test_health_check() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with TestClient(create_app()) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "Agent Workflow",
        "environment": "local",
        "dry_run": True,
    }
