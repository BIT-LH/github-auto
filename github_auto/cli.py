from __future__ import annotations

import getpass
from pathlib import Path
from typing import Optional

import typer

from . import __version__
from .auth import ensure_expected_user, verify_with_gh
from .config import Account, Config
from .github_api import GitHubAPI
from .git import ensure_ssh_remote, push as git_push
from .repository import create_repository, parse_repo
from .security import delete_token, set_token
from .ssh import setup_ssh
from .utils import require_command

app = typer.Typer(help="多账号 GitHub 自动化管理 CLI")
account_app = typer.Typer(help="GitHub 账号管理")
repo_app = typer.Typer(help="Repository 管理")
auth_app = typer.Typer(help="认证管理")
ssh_app = typer.Typer(help="SSH 管理")
git_app = typer.Typer(help="本地 Git 操作")

app.add_typer(account_app, name="account")
app.add_typer(repo_app, name="repo")
app.add_typer(auth_app, name="auth")
app.add_typer(ssh_app, name="ssh")
app.add_typer(git_app, name="git")


def cfg() -> Config:
    return Config()


def resolve_account(name: Optional[str]) -> tuple[str, Account]:
    c = cfg()
    name = name or c.current_account_name()
    return name, c.get_account(name)


@app.callback()
def root(
    version: bool = typer.Option(False, "--version", help="显示版本"),
):
    if version:
        typer.echo(__version__)
        raise typer.Exit()


@account_app.command("list")
def account_list():
    c = cfg()
    current = c.data.get("current_account")
    if not c.account_names():
        typer.echo("暂无账号")
        return
    for name in c.account_names():
        mark = "*" if name == current else " "
        a = c.get_account(name)
        typer.echo(f"{mark} {name:20} {a.username:25} {a.ssh_host}")


@account_app.command("current")
def account_current():
    name, a = resolve_account(None)
    typer.echo(f"account: {name}")
    typer.echo(f"username: {a.username}")
    typer.echo(f"email: {a.email}")
    typer.echo(f"ssh_host: {a.ssh_host}")
    typer.echo(f"ssh_key: {a.ssh_key}")


@account_app.command("add")
def account_add(
    name: str,
    username: str = typer.Option(..., "--username"),
    email: str = typer.Option(..., "--email"),
    ssh_key: Optional[str] = typer.Option(None, "--ssh-key"),
    ssh_host: Optional[str] = typer.Option(None, "--ssh-host"),
):
    c = cfg()
    if name in c.data["accounts"]:
        raise typer.BadParameter(f"账号已存在: {name}")
    host = ssh_host or f"github-{name.replace('_', '-').lower()}"

    if ssh_key:
        # User provided SSH key path
        ssh_key_path = str(Path(ssh_key).expanduser())
        key_path = Path(ssh_key_path)
        if not key_path.exists():
            raise typer.BadParameter(f"SSH 密钥文件不存在: {ssh_key_path}")
    else:
        # Generate SSH key with default path: ~/.ssh/github-{account_name}
        ssh_key_path = str(Path.home() / ".ssh" / f"github-{name.replace('_', '-').lower()}")

    account = Account(
        username=username,
        email=email,
        ssh_key=ssh_key_path,
        ssh_host=host,
    )
    c.add_account(name, account)
    setup_ssh(name, account, generate_if_missing=True)
    typer.echo(f"已添加账号: {name}")


@account_app.command("remove")
def account_remove(
    name: str,
    yes: bool = typer.Option(False, "--yes"),
):
    c = cfg()
    if not yes and not typer.confirm(f"确认删除本地账号配置 `{name}`？"):
        raise typer.Abort()
    c.remove_account(name)
    delete_token(name)
    typer.echo(f"[*] Deleted: {name}")


@account_app.command("use")
def account_use(name: str):
    c = cfg()
    c.set_current(name)
    typer.echo(f"当前账号: {name}")


@account_app.command("verify")
def account_verify(name: Optional[str] = typer.Argument(None)):
    name, a = resolve_account(name)
    login = verify_with_gh(name)
    if login.lower() != a.username.lower():
        raise typer.BadParameter(
            f"身份不匹配：配置={a.username}, GitHub={login}"
        )
    typer.echo(f"[*] {name} -> GitHub @{login}")


@ssh_app.command("setup")
def ssh_setup(name: Optional[str] = typer.Argument(None)):
    name, a = resolve_account(name)
    path = setup_ssh(name, a)
    typer.echo(f"SSH Config Updated: {path}")


@auth_app.command("token-set")
def auth_token_set(name: str):
    c = cfg()
    c.get_account(name)
    token = getpass.getpass("GitHub Token: ").strip()
    if not token:
        raise typer.BadParameter("Token 不能为空")
    set_token(name, token)
    typer.echo("Token 已安全保存到系统 Credential Manager/keyring")


@auth_app.command("token-delete")
def auth_token_delete(name: str):
    cfg().get_account(name)
    delete_token(name)
    typer.echo("[*] Token Deleted")


@repo_app.command("create")
def repo_create(
    repo: str,
    account: Optional[str] = typer.Option(None, "--account"),
    public: bool = typer.Option(False, "--public"),
    private: bool = typer.Option(False, "--private"),
    readme: bool = typer.Option(False, "--readme"),
    push: bool = typer.Option(False, "--push"),
    path: Path = typer.Option(Path("."), "--path"),
    description: str = typer.Option("", "--description"),
    message: str = typer.Option("Initial commit", "--message"),
):
    if public and private:
        raise typer.BadParameter("--public 与 --private 不能同时使用")
    name, a = resolve_account(account)
    is_private = private
    data = create_repository(
        account_name=name,
        account=a,
        repo_name=repo,
        path=path.expanduser().resolve(),
        private=is_private,
        readme=readme,
        description=description,
        do_push=push,
        message=message,
    )
    typer.echo(f"[*] Repository: {data['html_url']}")
    if push:
        typer.echo("[*] Push Done")


@repo_app.command("list")
def repo_list(
    account: Optional[str] = typer.Option(None, "--account"),
):
    name, a = resolve_account(account)
    api = GitHubAPI(name, a.api_base)
    try:
        repos = api.list_repos()
    finally:
        api.close()
    for r in repos:
        visibility = "private" if r["private"] else "public"
        typer.echo(f"{r['full_name']:45} {visibility}")


@repo_app.command("info")
def repo_info(
    repo: str,
    account: Optional[str] = typer.Option(None, "--account"),
):
    name, a = resolve_account(account)
    owner, repo_name = parse_repo(repo, a.username)
    api = GitHubAPI(name, a.api_base)
    try:
        data = api.repo(owner, repo_name)
    finally:
        api.close()
    typer.echo(f"name: {data['full_name']}")
    typer.echo(f"url: {data['html_url']}")
    typer.echo(f"visibility: {'private' if data['private'] else 'public'}")
    typer.echo(f"default_branch: {data.get('default_branch')}")
    typer.echo(f"description: {data.get('description') or '(none)'}")


@repo_app.command("edit")
def repo_edit(
    repo: str,
    account: Optional[str] = typer.Option(None, "--account"),
    description: str | None = typer.Option(None, "--description"),
    private: bool | None = typer.Option(None, "--private"),
):
    name, a = resolve_account(account)
    owner, repo_name = parse_repo(repo, a.username)
    if description is None and private is None:
        raise typer.BadParameter("至少需要指定 --description 或 --private")
    api = GitHubAPI(name, a.api_base)
    try:
        data = api.update_repo(owner, repo_name, description=description, private=private)
    finally:
        api.close()
    typer.echo(f"[*] Updated: {data['html_url']}")


@repo_app.command("clone")
def repo_clone(
    repo: str,
    account: Optional[str] = typer.Option(None, "--account"),
    destination: Optional[Path] = typer.Option(None, "--destination"),
):
    require_command("git")
    name, a = resolve_account(account)
    owner, repo_name = parse_repo(repo, a.username)
    setup_ssh(name, a)
    url = f"git@{a.ssh_host}:{owner}/{repo_name}.git"
    import subprocess
    target = destination.expanduser() if destination else Path(repo_name)
    subprocess.run(["git", "clone", url, str(target)], check=True)
    typer.echo(f"[*] Cloned to {target}")


@repo_app.command("delete")
def repo_delete(
    repo: str,
    account: Optional[str] = typer.Option(None, "--account"),
    yes: bool = typer.Option(False, "--yes"),
):
    name, a = resolve_account(account)
    owner, repo_name = parse_repo(repo, a.username)
    if not yes:
        typer.echo(f"即将删除: {owner}/{repo_name}")
        if not typer.confirm("此操作不可逆，继续？"):
            raise typer.Abort()
    ensure_expected_user(name, a)
    api = GitHubAPI(name, a.api_base)
    try:
        api.delete_repo(owner, repo_name)
    finally:
        api.close()
    typer.echo(f"[*] Deleted {owner}/{repo_name}")


@git_app.command("push")
def git_push_command(
    account: Optional[str] = typer.Option(None, "--account"),
    path: Path = typer.Option(Path("."), "--path"),
):
    name, a = resolve_account(account)
    ensure_expected_user(name, a)
    setup_ssh(name, a)
    path = path.expanduser().resolve()
    ensure_ssh_remote(path, a)
    git_push(path)
    typer.echo("[*] Push Done")


if __name__ == "__main__":
    app()
