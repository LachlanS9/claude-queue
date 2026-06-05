import pytest
from unittest.mock import patch, MagicMock
from config import Config
from job_queue import make_job


def _cfg(pr_provider="github", repos=None):
    return Config(
        telegram_token="t",
        user_accounts={1: "cq-user"},
        repos=repos or {"api": "/tmp/my-api"},
        pr_provider=pr_provider,
        default_repo="api",
        reset_time="09:00",
        usage_db_path="/tmp/usage.db",
    )


def _job():
    return make_job("add-feature", "Add the feature.", "api", "claude-sonnet-4-6", "none", "main", submitted_by=1)


def test_create_pr_dispatches_github(monkeypatch):
    from pr import create_pr
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_test")
    monkeypatch.setenv("GITHUB_REPO", "owner/repo")

    with patch("pr.github.requests.post") as mock_post:
        mock_post.return_value.json.return_value = {"html_url": "https://github.com/owner/repo/pull/1"}
        mock_post.return_value.raise_for_status = MagicMock()
        url = create_pr(_cfg("github"), _job(), "queue/123-add-feature")

    assert url == "https://github.com/owner/repo/pull/1"
    call_json = mock_post.call_args[1]["json"]
    assert call_json["head"] == "queue/123-add-feature"
    assert call_json["base"] == "main"


def test_create_pr_dispatches_azuredevops(monkeypatch):
    from pr import create_pr
    monkeypatch.setenv("AZURE_DEVOPS_ORG", "my-org")
    monkeypatch.setenv("AZURE_DEVOPS_PROJECT", "my-proj")
    monkeypatch.setenv("AZURE_DEVOPS_PAT", "my-pat")

    with patch("pr.azuredevops.requests.post") as mock_post:
        mock_post.return_value.json.return_value = {"pullRequestId": 42}
        mock_post.return_value.raise_for_status = MagicMock()
        url = create_pr(_cfg("azuredevops"), _job(), "queue/123-add-feature")

    assert "42" in url
    assert "my-org" in url


def test_create_pr_raises_for_unknown_provider():
    from pr import create_pr
    with pytest.raises(ValueError, match="Unknown pr_provider"):
        create_pr(_cfg("gitlab"), _job(), "branch")


def test_github_pr_uses_correct_fields(monkeypatch):
    from pr.github import create_pr as github_create_pr
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_test")
    monkeypatch.setenv("GITHUB_REPO", "owner/repo")
    job = make_job("add-feature", "Do this thing.", "api", "claude-sonnet-4-6", "none", "main", submitted_by=1)

    with patch("pr.github.requests.post") as mock_post:
        mock_post.return_value.json.return_value = {"html_url": "https://github.com/owner/repo/pull/1"}
        mock_post.return_value.raise_for_status = MagicMock()
        github_create_pr(job, "queue/branch")

    body = mock_post.call_args[1]["json"]
    assert body["title"] == "Add Feature"
    assert body["head"] == "queue/branch"
    assert body["base"] == "main"
    assert "Do this thing" in body["body"]


def test_azuredevops_derives_repo_name_from_path(monkeypatch):
    from pr.azuredevops import create_pr as azdo_create_pr
    monkeypatch.setenv("AZURE_DEVOPS_ORG", "org")
    monkeypatch.setenv("AZURE_DEVOPS_PROJECT", "proj")
    monkeypatch.setenv("AZURE_DEVOPS_PAT", "pat")

    cfg = _cfg("azuredevops", repos={"api": "/home/user/repos/my-backend"})
    job = make_job("fix", "content", "api", "claude-sonnet-4-6", "none", "main", submitted_by=1)

    with patch("pr.azuredevops.requests.post") as mock_post:
        mock_post.return_value.json.return_value = {"pullRequestId": 1}
        mock_post.return_value.raise_for_status = MagicMock()
        azdo_create_pr(cfg, job, "branch")

    assert "my-backend" in mock_post.call_args[0][0]
