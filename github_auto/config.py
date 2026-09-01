from __future__ import annotations

import os
import platform
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional

import yaml


APP_NAME = "github-auto"


def default_config_path() -> Path:
    env = os.getenv("GITHUB_AUTO_CONFIG")
    if env:
        return Path(env).expanduser()

    system = platform.system()
    if system == "Windows":
        base = Path(os.getenv("APPDATA", Path.home() / "AppData/Roaming"))
        return base / APP_NAME / "config.yaml"
    return Path.home() / ".config" / APP_NAME / "config.yaml"


@dataclass
class Account:
    username: str
    email: str
    ssh_key: str
    ssh_host: str
    api_base: str = "https://api.github.com"

    def __post_init__(self):
        # Normalize path to platform-native format when loading/saving
        if self.ssh_key:
            self.ssh_key = str(Path(self.ssh_key).expanduser())


class Config:
    def __init__(self, path: Optional[Path] = None):
        self.path = (path or default_config_path()).expanduser()
        self.data = {"current_account": None, "accounts": {}}
        self.load()

    def load(self) -> None:
        if not self.path.exists():
            return
        with self.path.open("r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
        self.data["current_account"] = raw.get("current_account")
        self.data["accounts"] = raw.get("accounts", {})

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        with tmp.open("w", encoding="utf-8") as f:
            yaml.safe_dump(self.data, f, allow_unicode=True, sort_keys=False)
        tmp.replace(self.path)

    def account_names(self) -> list[str]:
        return sorted(self.data["accounts"].keys())

    def get_account(self, name: str) -> Account:
        raw = self.data["accounts"].get(name)
        if not raw:
            raise KeyError(f"账号不存在: {name}")
        return Account(
            username=raw["username"],
            email=raw["email"],
            ssh_key=raw["ssh_key"],
            ssh_host=raw["ssh_host"],
            api_base=raw.get("api_base", "https://api.github.com"),
        )

    def add_account(self, name: str, account: Account) -> None:
        self.data["accounts"][name] = asdict(account)
        if not self.data["current_account"]:
            self.data["current_account"] = name
        self.save()

    def remove_account(self, name: str) -> None:
        if name not in self.data["accounts"]:
            raise KeyError(f"账号不存在: {name}")
        del self.data["accounts"][name]
        if self.data["current_account"] == name:
            names = self.account_names()
            self.data["current_account"] = names[0] if names else None
        self.save()

    def current_account_name(self) -> str:
        name = self.data.get("current_account")
        if not name:
            raise RuntimeError("尚未设置当前账号，请使用 `account use <name>`")
        return name

    def set_current(self, name: str) -> None:
        self.get_account(name)
        self.data["current_account"] = name
        self.save()
