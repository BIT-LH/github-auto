from __future__ import annotations

from pathlib import Path

from .config import Account
from .ssh import ssh_remote
from .utils import require_command, run


def git_init(path: Path) -> None:
    require_command("git")
    if not (path / ".git").exists():
        run(["git", "init"], cwd=path)


def configure_identity(path: Path, account: Account) -> None:
    run(["git", "config", "user.name", account.username], cwd=path)
    run(["git", "config", "user.email", account.email], cwd=path)


def set_remote(path: Path, account: Account, owner: str, repo: str) -> None:
    remote = ssh_remote(account, owner, repo)
    existing = run(["git", "remote", "get-url", "origin"], cwd=path, check=False)
    if existing.returncode == 0:
        run(["git", "remote", "set-url", "origin", remote], cwd=path)
    else:
        run(["git", "remote", "add", "origin", remote], cwd=path)


def has_changes(path: Path) -> bool:
    result = run(["git", "status", "--porcelain"], cwd=path)
    return bool(result.stdout.strip())


def commit(path: Path, message: str) -> bool:
    if not has_changes(path):
        return False
    run(["git", "add", "-A"], cwd=path)
    run(["git", "commit", "-m", message], cwd=path)
    return True


def push(path: Path, branch: str = "main") -> None:
    result = run(
        ["git", "rev-parse", "--verify", branch],
        cwd=path,
        check=False,
    )
    if result.returncode != 0:
        current = run(
            ["git", "branch", "--show-current"],
            cwd=path,
        ).stdout.strip()
        branch = current or "main"
    run(["git", "push", "-u", "origin", branch], cwd=path)
