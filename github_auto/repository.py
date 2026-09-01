from __future__ import annotations

from pathlib import Path

from .auth import ensure_expected_user
from .config import Account
from .github_api import GitHubAPI
from .git import commit, configure_identity, git_init, push, set_remote
from .ssh import setup_ssh


def parse_repo(value: str, default_owner: str) -> tuple[str, str]:
    value = value.strip()
    if "/" in value:
        owner, repo = value.split("/", 1)
        return owner, repo.removesuffix(".git")
    return default_owner, value.removesuffix(".git")


def create_repository(
    account_name: str,
    account: Account,
    repo_name: str,
    path: Path,
    private: bool,
    readme: bool,
    description: str,
    do_push: bool,
    message: str = "Initial commit",
) -> dict:
    owner = account.username
    setup_ssh(account_name, account)
    ensure_expected_user(account_name, account)

    api = GitHubAPI(account_name, account.api_base)
    try:
        data = api.create_repo(
            name=repo_name,
            private=private,
            description=description,
            auto_init=False,
        )
    finally:
        api.close()

    path.mkdir(parents=True, exist_ok=True)
    git_init(path)
    configure_identity(path, account)

    if readme:
        readme_path = path / "README.md"
        if not readme_path.exists():
            readme_path.write_text(
                f"# {repo_name}\n\n"
                f"GitHub repository managed by github-auto.\n",
                encoding="utf-8",
            )

    set_remote(path, account, owner, repo_name)
    commit(path, message)

    if do_push:
        push(path)

    return data
