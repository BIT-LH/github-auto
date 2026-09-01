from __future__ import annotations

import os
import re
import keyring


SERVICE = "github-auto"


def env_token_name(account: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9]", "_", account).upper()
    return f"GH_TOKEN_{safe}"


def set_token(account: str, token: str) -> None:
    keyring.set_password(SERVICE, account, token)


def get_token(account: str) -> str | None:
    env = os.getenv(env_token_name(account))
    if env:
        return env
    return keyring.get_password(SERVICE, account)


def delete_token(account: str) -> None:
    try:
        keyring.delete_password(SERVICE, account)
    except keyring.errors.PasswordDeleteError:
        pass
