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
from .utils import require_command, random_sleep

app = typer.Typer(help="多账号 GitHub 自动化管理 CLI")
account_app = typer.Typer(help="GitHub 账号管理")
repo_app = typer.Typer(help="Repository 管理")
auth_app = typer.Typer(help="认证管理")
ssh_app = typer.Typer(help="SSH 管理")
git_app = typer.Typer(help="本地 Git 操作")
user_app = typer.Typer(help="GitHub 用户管理")

app.add_typer(account_app, name="account")
app.add_typer(repo_app, name="repo")
app.add_typer(auth_app, name="auth")
app.add_typer(ssh_app, name="ssh")
app.add_typer(git_app, name="git")
app.add_typer(user_app, name="user")


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
    random_sleep(2, 8)
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
    random_sleep(2, 8)
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
    random_sleep(2, 8)
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
    random_sleep(5, 60)
    api = GitHubAPI(name, a.api_base)
    try:
        api.delete_repo(owner, repo_name)
    finally:
        api.close()
    typer.echo(f"[*] Deleted {owner}/{repo_name}")


@repo_app.command("star")
def repo_star(
    repo: str,
    account: Optional[str] = typer.Option(None, "--account"),
    unstar: bool = typer.Option(False, "--unstar"),
):
    name, a = resolve_account(account)
    owner, repo_name = parse_repo(repo, a.username)
    typer.echo(f"[*] Waiting before star operation...")
    random_sleep(5, 60)
    api = GitHubAPI(name, a.api_base)
    try:
        if unstar:
            api.unstar_repo(owner, repo_name)
            typer.echo(f"[*] Unstarred {owner}/{repo_name}")
        else:
            api.star_repo(owner, repo_name)
            typer.echo(f"[*] Starred {owner}/{repo_name}")
    finally:
        api.close()


@repo_app.command("search")
def repo_search(
    query: str = typer.Argument(...),
    account: Optional[str] = typer.Option(None, "--account"),
    limit: int = typer.Option(10, "--limit", min=1, max=100),
):
    """Search GitHub repositories."""
    name, a = resolve_account(account)
    random_sleep(2, 8)
    api = GitHubAPI(name, a.api_base)
    try:
        results = api.search_repos(query, per_page=limit)
        if not results:
            typer.echo("No results found.")
            return
        for r in results:
            stars = r.get("stargazers_count", 0)
            visibility = "private" if r.get("private") else "public"
            typer.echo(f"{r['full_name']:45} ⭐{stars:>6}  {visibility}")
            typer.echo(f"  {r.get('description', 'N/A')}")
            typer.echo()
    finally:
        api.close()


@repo_app.command("browse")
def repo_browse(
    repo: str,
    path: str = typer.Argument(""),
    account: Optional[str] = typer.Option(None, "--account"),
):
    """Browse repository contents (files and folders)."""
    name, a = resolve_account(account)
    owner, repo_name = parse_repo(repo, a.username)
    random_sleep(2, 8)
    api = GitHubAPI(name, a.api_base)
    try:
        contents = api.list_contents(owner, repo_name, path)
        if isinstance(contents, dict):
            # Single file - show its content info
            typer.echo(f"File: {contents.get('name')}")
            typer.echo(f"Size: {contents.get('size', 0)} bytes")
            typer.echo(f"Type: {contents.get('type')}")
            if contents.get("download_url"):
                typer.echo(f"Download: {contents.get('download_url')}")
            return

        # Directory listing
        if path:
            typer.echo(f"Path: {path}/")
        typer.echo()
        for item in contents:
            icon = "📁" if item["type"] == "dir" else "📄"
            size = f"{item.get('size', 0):>8}" if item["type"] == "file" else ""
            typer.echo(f"{icon} {item['name']:<30} {size}")
    finally:
        api.close()


@repo_app.command("download")
def repo_download(
    repo: str,
    account: Optional[str] = typer.Option(None, "--account"),
    branch: str = typer.Option("main", "--branch", "-b"),
    output: Optional[Path] = typer.Option(None, "--output", "-o"),
):
    """Download repository as zip archive."""
    import urllib.request

    name, a = resolve_account(account)
    owner, repo_name = parse_repo(repo, a.username)
    random_sleep(2, 8)
    api = GitHubAPI(name, a.api_base)
    try:
        download_url = api.get_archive_url(owner, repo_name, branch)
        if not download_url:
            raise RuntimeError(f"Failed to get download URL for {owner}/{repo_name}")

        # Download the zip
        typer.echo(f"Downloading {owner}/{repo_name}@{branch}...")
        with urllib.request.urlopen(download_url) as response:
            zip_data = response.read()

        # Determine output path
        if output:
            output_path = output.expanduser()
        else:
            output_path = Path.cwd() / f"{repo_name}-{branch}.zip"

        # Save zip file
        with open(output_path, "wb") as f:
            f.write(zip_data)

        typer.echo(f"[*] Saved to {output_path}")
    finally:
        api.close()


@repo_app.command("fork")
def repo_fork(
    repo: str,
    account: Optional[str] = typer.Option(None, "--account"),
    organization: Optional[str] = typer.Option(None, "--org", "-o"),
):
    """Fork a repository."""
    name, a = resolve_account(account)
    owner, repo_name = parse_repo(repo, a.username)
    typer.echo(f"[*] Waiting before fork operation...")
    random_sleep(5, 60)
    api = GitHubAPI(name, a.api_base)
    try:
        payload = {}
        if organization:
            payload["organization"] = organization
        result = api.fork_repo(owner, repo_name)
        typer.echo(f"[*] Forked {owner}/{repo_name}")
        typer.echo(f"    -> {result.get('full_name')}")
    finally:
        api.close()


@repo_app.command("watch")
def repo_watch(
    repo: str,
    account: Optional[str] = typer.Option(None, "--account"),
    unwatch: bool = typer.Option(False, "--unwatch"),
):
    """Watch/unwatch a repository for notifications."""
    name, a = resolve_account(account)
    owner, repo_name = parse_repo(repo, a.username)
    typer.echo(f"[*] Waiting before watch operation...")
    random_sleep(5, 60)
    api = GitHubAPI(name, a.api_base)
    try:
        if unwatch:
            api.unwatch_repo(owner, repo_name)
            typer.echo(f"[*] Unwatched {owner}/{repo_name}")
        else:
            api.watch_repo(owner, repo_name)
            typer.echo(f"[*] Watching {owner}/{repo_name}")
    finally:
        api.close()


# --- User Commands ---

@user_app.command("info")
def user_info(
    username: str = typer.Argument(...),
    account: Optional[str] = typer.Option(None, "--account"),
):
    """Get user profile information."""
    name, a = resolve_account(account)
    random_sleep(2, 8)
    api = GitHubAPI(name, a.api_base)
    try:
        user = api.get_user(username)
        typer.echo(f"Username: {user.get('login')}")
        typer.echo(f"Name: {user.get('name') or 'N/A'}")
        typer.echo(f"Bio: {user.get('bio') or 'N/A'}")
        typer.echo(f"Location: {user.get('location') or 'N/A'}")
        typer.echo(f"Followers: {user.get('followers', 0)}")
        typer.echo(f"Following: {user.get('following', 0)}")
        typer.echo(f"Public Repos: {user.get('public_repos', 0)}")
        typer.echo(f"Profile: {user.get('html_url')}")
    finally:
        api.close()


@user_app.command("follow")
def user_follow(
    username: str = typer.Argument(...),
    account: Optional[str] = typer.Option(None, "--account"),
    unfollow: bool = typer.Option(False, "--unfollow"),
):
    """Follow/unfollow a user."""
    name, a = resolve_account(account)
    typer.echo(f"[*] Waiting before follow operation...")
    random_sleep(5, 60)
    api = GitHubAPI(name, a.api_base)
    try:
        if unfollow:
            api.unfollow_user(username)
            typer.echo(f"[*] Unfollowed @{username}")
        else:
            api.follow_user(username)
            typer.echo(f"[*] Followed @{username}")
    finally:
        api.close()


@user_app.command("followers")
def user_followers(
    username: str = typer.Argument(...),
    account: Optional[str] = typer.Option(None, "--account"),
):
    """List a user's followers."""
    name, a = resolve_account(account)
    random_sleep(2, 8)
    api = GitHubAPI(name, a.api_base)
    try:
        followers = api.list_followers(username)
        if not followers:
            typer.echo(f"@{username} has no followers yet.")
            return
        typer.echo(f"Followers of @{username}:")
        for f in followers:
            typer.echo(f"  - {f.get('login')} ({f.get('html_url')})")
    finally:
        api.close()


@user_app.command("following")
def user_following(
    username: str = typer.Argument(...),
    account: Optional[str] = typer.Option(None, "--account"),
):
    """List users that a person follows."""
    name, a = resolve_account(account)
    random_sleep(2, 8)
    api = GitHubAPI(name, a.api_base)
    try:
        following = api.list_following(username)
        if not following:
            typer.echo(f"@{username} is not following anyone.")
            return
        typer.echo(f"@{username} is following:")
        for f in following:
            typer.echo(f"  - {f.get('login')} ({f.get('html_url')})")
    finally:
        api.close()


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
