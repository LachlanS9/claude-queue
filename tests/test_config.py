import json
import pytest
from config import load_config


def test_load_config_reads_user_accounts(tmp_path, monkeypatch):
    config_file = tmp_path / "bot-config.json"
    config_file.write_text(json.dumps({
        "user_accounts": {"111": "cq-alice", "222": "cq-bob"},
        "reset_time": "08:30"
    }))
    for k, v in [("TELEGRAM_BOT_TOKEN", "tg-token"), ("AZURE_DEVOPS_ORG", "my-org"),
                 ("AZURE_DEVOPS_PROJECT", "my-proj"), ("AZURE_DEVOPS_PAT", "my-pat")]:
        monkeypatch.setenv(k, v)

    cfg = load_config(config_path=str(config_file))

    assert cfg.telegram_token == "tg-token"
    assert cfg.user_accounts == {111: "cq-alice", 222: "cq-bob"}
    assert cfg.reset_time == "08:30"
    assert cfg.azure_devops_org == "my-org"


def test_load_config_defaults_reset_time(tmp_path, monkeypatch):
    config_file = tmp_path / "bot-config.json"
    config_file.write_text(json.dumps({"user_accounts": {"1": "cq-user"}}))
    for k, v in [("TELEGRAM_BOT_TOKEN", "t"), ("AZURE_DEVOPS_ORG", "o"),
                 ("AZURE_DEVOPS_PROJECT", "p"), ("AZURE_DEVOPS_PAT", "x")]:
        monkeypatch.setenv(k, v)

    cfg = load_config(config_path=str(config_file))
    assert cfg.reset_time == "09:00"
