from __future__ import annotations

import os

from .config import Account
from .security import get_token
from .utils import require_command, run


def gh_env(account_name: str) -> dict:
    env = os.environ.copy()
    token = get_token(account_name)
    if token:
        env["GH_TOKEN"] = token
    return env


def verify_with_gh(account_name: str) -> str:
    require_command("gh")
    result = run(
        ["gh", "api", "user", "--jq", ".login"],
        env=gh_env(account_name),
    )
    return result.stdout.strip()


def ensure_expected_user(account_name: str, account: Account) -> str:
    login = verify_with_gh(account_name)
    if login.lower() != account.username.lower():
        raise RuntimeError(
            f"GitHub 身份不匹配：配置账号={account.username}，"
            f"实际认证账号={login}"
        )
    return login
