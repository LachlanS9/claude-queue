import json
import os
import pytest
from config import load_config


def test_load_config_reads_repos_and_provider(tmp_path, monkeypatch):
    config_file = tmp_path / "bot-config.json"
    config_file.write_text(json.dumps({
        "user_accounts": {"111": "cq-alice"},
        "repos": {"api": "~/repos/my-api", "web": "~/repos/my-web"},
        "pr_provider": "github",
        "default_repo": "api",
        "reset_time": "08:30"
    }))
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tg-token")

    cfg = load_config(config_path=str(config_file))

    assert cfg.telegram_token == "tg-token"
    assert cfg.user_accounts == {111: "cq-alice"}
    assert cfg.repos == {
        "api": os.path.expanduser("~/repos/my-api"),
        "web": os.path.expanduser("~/repos/my-web"),
    }
    assert cfg.pr_provider == "github"
    assert cfg.default_repo == "api"
    assert cfg.reset_time == "08:30"


def test_load_config_defaults_reset_time_and_default_repo(tmp_path, monkeypatch):
    config_file = tmp_path / "bot-config.json"
    config_file.write_text(json.dumps({
        "user_accounts": {"1": "cq-user"},
        "repos": {"api": "~/repos/api"},
        "pr_provider": "github",
    }))
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "t")

    cfg = load_config(config_path=str(config_file))

    assert cfg.reset_time == "09:00"
    assert cfg.default_repo == "api"


def test_load_config_expands_repo_paths(tmp_path, monkeypatch):
    config_file = tmp_path / "bot-config.json"
    config_file.write_text(json.dumps({
        "user_accounts": {"1": "cq-user"},
        "repos": {"api": "~/repos/api"},
        "pr_provider": "azuredevops",
    }))
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "t")

    cfg = load_config(config_path=str(config_file))

    assert not cfg.repos["api"].startswith("~")
    assert cfg.repos["api"] == os.path.expanduser("~/repos/api")
