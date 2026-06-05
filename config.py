import os
import json
from dataclasses import dataclass
from typing import Dict

DEFAULT_CONFIG_PATH = os.path.expanduser("~/bot-config.json")

@dataclass
class Config:
    telegram_token: str
    user_accounts: Dict[int, str]
    reset_time: str
    azure_devops_org: str
    azure_devops_project: str
    azure_devops_pat: str
    redis_url: str = "redis://localhost:6379"
    backend_repo_path: str = os.path.expanduser("~/repos/Retinote-Backend")
    frontend_repo_path: str = os.path.expanduser("~/repos/Retinote-Next")
    usage_db_path: str = os.path.expanduser("~/usage.db")

def load_config(config_path: str = DEFAULT_CONFIG_PATH) -> Config:
    with open(config_path) as f:
        data = json.load(f)
    return Config(
        telegram_token=os.environ["TELEGRAM_BOT_TOKEN"],
        user_accounts={int(k): v for k, v in data["user_accounts"].items()},
        reset_time=data.get("reset_time", "09:00"),
        azure_devops_org=os.environ["AZURE_DEVOPS_ORG"],
        azure_devops_project=os.environ["AZURE_DEVOPS_PROJECT"],
        azure_devops_pat=os.environ["AZURE_DEVOPS_PAT"],
    )
