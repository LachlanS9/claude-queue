import json
import time
import pytest
from unittest.mock import patch, MagicMock
from job_queue import make_job
from worker import run_job, _slug, _model_alias, RateLimitError, NoChangesError


@pytest.fixture(autouse=True)
def mock_pwd(monkeypatch):
    fake_pw = MagicMock()
    fake_pw.pw_uid = 1000
    fake_pw.pw_gid = 1000
    fake_pw.pw_dir = "/home/cq-lachlan"
    import worker
    monkeypatch.setattr(worker.pwd, "getpwnam", lambda name: fake_pw)


@pytest.fixture
def job():
    return make_job(
        prompt_name="auth-refactor",
        content="Refactor the auth controller.",
        repo="backend",
        model="claude-sonnet-4-6",
        thinking="none",
        base_branch="main",
        submitted_by=111,
    )


@pytest.fixture
def config(tmp_path):
    from config import Config
    return Config(
        telegram_token="t",
        user_accounts={111: "cq-lachlan", 222: "cq-cofounder"},
        reset_time="09:00",
        azure_devops_org="my-org",
        azure_devops_project="my-proj",
        azure_devops_pat="my-pat",
        backend_repo_path=str(tmp_path / "Retinote-Backend"),
        frontend_repo_path=str(tmp_path / "Retinote-Next"),
        usage_db_path=str(tmp_path / "usage.db"),
    )


def _mock_claude_output(input_tokens=1000, output_tokens=200):
    return json.dumps({
        "result": "Done.",
        "usage": {"input_tokens": input_tokens, "output_tokens": output_tokens}
    })


def test_run_job_happy_path(job, config, tmp_path):
    (tmp_path / "Retinote-Backend").mkdir()
    mock_process = MagicMock()
    mock_process.poll.side_effect = [None, None, 0]
    mock_process.returncode = 0
    mock_process.communicate.return_value = (_mock_claude_output(), "")

    with patch("worker.subprocess.run") as mock_run, \
         patch("worker.subprocess.Popen", return_value=mock_process), \
         patch("worker.requests.post") as mock_post, \
         patch("worker.time.sleep"), \
         patch("worker._auto_commit"), \
         patch("worker._has_changes_to_push", return_value=True):

        mock_run.return_value = MagicMock(returncode=0)
        mock_post.return_value.json.return_value = {"pullRequestId": 42}
        mock_post.return_value.raise_for_status = MagicMock()

        result = run_job(job, config)

    assert result["input_tokens"] == 1000
    assert result["output_tokens"] == 200
    assert "42" in result["pr_url"]


def test_run_job_raises_no_changes_error(job, config, tmp_path):
    (tmp_path / "Retinote-Backend").mkdir()
    mock_process = MagicMock()
    mock_process.poll.return_value = 0
    mock_process.returncode = 0
    mock_process.communicate.return_value = (_mock_claude_output(), "")

    with patch("worker.subprocess.run") as mock_run, \
         patch("worker.subprocess.Popen", return_value=mock_process), \
         patch("worker.time.sleep"), \
         patch("worker._auto_commit"), \
         patch("worker._has_changes_to_push", return_value=False):
        mock_run.return_value = MagicMock(returncode=0)
        with pytest.raises(NoChangesError):
            run_job(job, config)


def test_run_job_raises_rate_limit_error(job, config, tmp_path):
    (tmp_path / "Retinote-Backend").mkdir()
    mock_process = MagicMock()
    mock_process.poll.return_value = 1
    mock_process.returncode = 1
    mock_process.communicate.return_value = ("", "rate limit exceeded")

    with patch("worker.subprocess.run") as mock_run, \
         patch("worker.subprocess.Popen", return_value=mock_process):
        mock_run.return_value = MagicMock(returncode=0)
        with pytest.raises(RateLimitError):
            run_job(job, config)


def test_run_job_raises_for_unmapped_user(job, config, tmp_path):
    (tmp_path / "Retinote-Backend").mkdir()
    job.submitted_by = 0
    with pytest.raises(RuntimeError, match="No system account"):
        run_job(job, config)


def test_slug_replaces_special_chars():
    assert _slug("auth-refactor") == "auth-refactor"
    assert _slug("Auth Refactor!") == "auth-refactor-"
    assert len(_slug("a" * 100)) == 40


def test_model_alias():
    assert _model_alias("claude-sonnet-4-6") == "sonnet"
    assert _model_alias("claude-opus-4-7") == "opus"
    assert _model_alias("claude-haiku-4-5-20251001") == "haiku"
    assert _model_alias("unknown-model") == "unknown-model"
