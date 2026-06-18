import shutil
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


def test_workdoc_state_machine_and_mock_agent(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)

    with TestClient(create_app()) as client:
        imported = client.post(
            "/messages/import",
            json={
                "messages": [
                    {
                        "room_id": "dev-room",
                        "sender_hash": "u1",
                        "sender_display_name": "Alice",
                        "text": "首页设置按钮点了没反应，应该跳转到 /settings。先别重构，只修这个按钮。",
                    }
                ]
            },
        )
        assert imported.status_code == 200
        message_id = imported.json()[0]["id"]

        created = client.post(
            "/workdocs/from-messages",
            json={"message_ids": [message_id], "repo_path": str(repo), "repo_name": "fixture", "branch_base": "main"},
        )
        assert created.status_code == 200
        workdoc = created.json()
        assert workdoc["status"] == "WORKDOC_DRAFTED"
        assert workdoc["acceptance_criteria"]

        blocked_run = client.post(f"/agent-runs/from-workdoc/{workdoc['id']}", json={"agent_type": "mock"})
        assert blocked_run.status_code == 409

        validated = client.post(f"/workdocs/{workdoc['id']}/validate")
        assert validated.status_code == 200
        assert validated.json()["valid"] is True
        assert validated.json()["workdoc"]["status"] == "WORKDOC_VALIDATED"

        approved = client.post(f"/workdocs/{workdoc['id']}/approve")
        assert approved.status_code == 200
        assert approved.json()["status"] == "APPROVED_FOR_AGENT"

        agent_run = client.post(f"/agent-runs/from-workdoc/{workdoc['id']}", json={"agent_type": "mock"})
        assert agent_run.status_code == 200
        run_payload = agent_run.json()
        assert run_payload["status"] == "PATCH_CREATED"
        assert "mock-agent" in run_payload["command"]

        dry_run = client.post(f"/git/commit-from-run/{run_payload['id']}", json={"dry_run": True})
        assert dry_run.status_code == 200
        assert dry_run.json()["commit_hash"] is None
        assert dry_run.json()["status"] == "APPROVED_FOR_COMMIT"

        real_commit = client.post(f"/git/commit-from-run/{run_payload['id']}", json={"dry_run": False})
        assert real_commit.status_code == 200
        commit_payload = real_commit.json()
        assert commit_payload["status"] == "GIT_COMMITTED"
        assert commit_payload["commit_hash"]
        assert commit_payload["branch_name"] == f"agent-workflow/workdoc-{workdoc['id']}"

        report = client.get(f"/reports/workdoc/{workdoc['id']}")
        assert report.status_code == 200
        assert "No TestRun recorded" in report.json()["report"]
        assert commit_payload["commit_hash"] in report.json()["report"]
        assert "Policy Decisions" in report.json()["report"]


def test_test_runner_and_required_test_policy(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)

    with TestClient(create_app()) as client:
        imported = client.post("/messages/import", json={"messages": [{"text": "设置按钮应该跳转到 /settings。"}]})
        message_id = imported.json()[0]["id"]
        workdoc = client.post(
            "/workdocs/from-messages",
            json={
                "message_ids": [message_id],
                "repo_path": str(repo),
                "test": {"commands": ["python -c \"print('ok')\""], "required": True},
            },
        ).json()
        client.post(f"/workdocs/{workdoc['id']}/validate")
        client.post(f"/workdocs/{workdoc['id']}/approve")
        agent_run = client.post(f"/agent-runs/from-workdoc/{workdoc['id']}", json={"agent_type": "mock"}).json()

        blocked_commit = client.post(f"/git/commit-from-run/{agent_run['id']}", json={"dry_run": True})
        assert blocked_commit.status_code == 403
        assert "TEST_PASSED" in blocked_commit.json()["detail"]

        test_run = client.post(f"/tests/run-for-agent-run/{agent_run['id']}")
        assert test_run.status_code == 200
        assert test_run.json()["status"] == "TEST_PASSED"

        dry_run = client.post(f"/git/commit-from-run/{agent_run['id']}", json={"dry_run": True})
        assert dry_run.status_code == 200
        assert dry_run.json()["status"] == "APPROVED_FOR_COMMIT"


def test_git_diff_api_and_remote_publish_are_blocked_by_default(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)

    with TestClient(create_app()) as client:
        workdoc_id = _approved_workdoc(client, repo)
        agent_run = client.post(f"/agent-runs/from-workdoc/{workdoc_id}", json={"agent_type": "mock"}).json()

        diff = client.post(f"/git/diff/{agent_run['id']}")
        assert diff.status_code == 200
        assert "agent_workflow_mock_patch.txt" in diff.json()["changed_files"]

        branch = client.post(f"/git/branch-from-run/{agent_run['id']}", json={"dry_run": True})
        assert branch.status_code == 200
        operation_id = branch.json()["id"]

        push = client.post(f"/git/push/{operation_id}")
        assert push.status_code == 403
        pr = client.post(f"/git/create-pr/{operation_id}")
        assert pr.status_code == 403


def test_validate_requires_acceptance_criteria() -> None:
    with TestClient(create_app()) as client:
        imported = client.post("/messages/import", json={"messages": [{"text": "随便看看这个页面。"}]})
        message_id = imported.json()[0]["id"]
        workdoc = client.post("/workdocs/from-messages", json={"message_ids": [message_id]}).json()

        validated = client.post(f"/workdocs/{workdoc['id']}/validate")
        assert validated.status_code == 200
        payload = validated.json()
        assert payload["valid"] is False
        assert payload["workdoc"]["status"] == "HUMAN_REVIEW_REQUIRED"
        assert "acceptance_criteria is required" in payload["reasons"]


def test_claude_cli_default_is_command_plan(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    with TestClient(create_app()) as client:
        workdoc_id = _approved_workdoc(client, repo)
        agent_run = client.post(f"/agent-runs/from-workdoc/{workdoc_id}", json={"agent_type": "claude_cli"})

    assert agent_run.status_code == 200
    payload = agent_run.json()
    assert payload["status"] == "PATCH_CREATED"
    assert "Claude CLI command planned" in payload["result_summary"]


def test_gagent_desktop_default_is_audit_plan(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    with TestClient(create_app()) as client:
        workdoc_id = _approved_workdoc(client, repo)
        agent_run = client.post(f"/agent-runs/from-workdoc/{workdoc_id}", json={"agent_type": "gagent_desktop"})

    assert agent_run.status_code == 200
    payload = agent_run.json()
    assert "gagent-desktop audit planned" in payload["result_summary"]


def _approved_workdoc(client: TestClient, repo: Path) -> int:
    imported = client.post(
        "/messages/import",
        json={"messages": [{"text": "设置按钮应该跳转到 /settings。"}]},
    )
    message_id = imported.json()[0]["id"]
    workdoc = client.post("/workdocs/from-messages", json={"message_ids": [message_id], "repo_path": str(repo)}).json()
    client.post(f"/workdocs/{workdoc['id']}/validate")
    client.post(f"/workdocs/{workdoc['id']}/approve")
    return workdoc["id"]


def _init_repo(tmp_path: Path) -> Path:
    if shutil.which("git") is None:
        pytest.skip("git is not installed")

    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "checkout", "-b", "main")
    _git(repo, "config", "user.email", "agent-workflow@example.test")
    _git(repo, "config", "user.name", "Agent Workflow")
    (repo / "README.md").write_text("# fixture\n", encoding="utf-8")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-m", "initial commit")
    return repo


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
