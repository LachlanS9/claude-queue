import os
import json
from dataclasses import dataclass
from typing import Dict

DEFAULT_CONFIG_PATH = os.path.expanduser("~/bot-config.json")


@dataclass
class Config:
    telegram_token: str
    user_accounts: Dict[int, str]
    repos: Dict[str, str]
    pr_provider: str
    default_repo: str
    reset_time: str
    redis_url: str = "redis://localhost:6379"
    usage_db_path: str = os.path.expanduser("~/usage.db")
    prompts_path: str = os.path.expanduser("~/claude-queue-prompts")


def load_config(config_path: str = DEFAULT_CONFIG_PATH) -> Config:
    with open(config_path) as f:
        data = json.load(f)
    repos = {k: os.path.expanduser(v) for k, v in data["repos"].items()}
    return Config(
        telegram_token=os.environ["TELEGRAM_BOT_TOKEN"],
        user_accounts={int(k): v for k, v in data["user_accounts"].items()},
        repos=repos,
        pr_provider=data["pr_provider"],
        default_repo=data.get("default_repo", next(iter(repos))),
        reset_time=data.get("reset_time", "09:00"),
        prompts_path=os.path.expanduser(data.get("prompts_path", "~/claude-queue-prompts")),
    )
