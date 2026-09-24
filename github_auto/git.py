from __future__ import annotations

from pathlib import Path

from .config import Account
from .ssh import ssh_remote
from .utils import require_command, run


# Default .gitignore template
DEFAULT_GITIGNORE = """# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# Virtual environments
venv/
ENV/
env/
.venv/

# IDE
.idea/
.vscode/
*.swp
*.swo
*~

# OS
.DS_Store
Thumbs.db

# Logs
*.log

# Node (if used)
node_modules/
npm-debug.log*
yarn-debug.log*
yarn-error.log*

# Testing
.pytest_cache/
.coverage
htmlcov/
"""


def git_init(path: Path) -> None:
    require_command("git")
    if not (path / ".git").exists():
        run(["git", "init"], cwd=path)


def create_gitignore(path: Path, content: str | None = None) -> Path:
    """Create a .gitignore file in the given directory."""
    gitignore_path = path / ".gitignore"
    if gitignore_path.exists():
        return gitignore_path
    gitignore_path.write_text(content or DEFAULT_GITIGNORE, encoding="utf-8")
    return gitignore_path


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
    # Check if target branch exists, if not, handle master->main rename
    result = run(
        ["git", "rev-parse", "--verify", branch],
        cwd=path,
        check=False,
    )
    if result.returncode != 0:
        # Check if master exists and rename it to main
        master_check = run(
            ["git", "rev-parse", "--verify", "master"],
            cwd=path,
            check=False,
        )
        if master_check.returncode == 0:
            run(["git", "branch", "-m", "master", "main"], cwd=path)
        else:
            # Create main branch if neither exists
            run(["git", "checkout", "-b", "main"], cwd=path)

    current = run(
        ["git", "branch", "--show-current"],
        cwd=path,
    ).stdout.strip()
    if current == "master":
        run(["git", "branch", "-m", "master", "main"], cwd=path)

    run(["git", "push", "-u", "origin", "main"], cwd=path)


def ensure_ssh_remote(path: Path, account: Account) -> None:
    """Ensure the remote URL uses SSH format with the account's ssh_host."""
    result = run(["git", "remote", "get-url", "origin"], cwd=path, check=False)
    if result.returncode != 0:
        return

    current_url = result.stdout.strip()

    # Parse owner/repo from both HTTPS and SSH URL formats
    # HTTPS: https://github.com/owner/repo.git
    # SSH:   git@github.com:owner/repo.git
    # SSH with custom host: git@github-solar-flare-888:owner/repo.git
    import re
    https_match = re.match(r"https://github\.com/([^/]+)/([^/]+?)(?:\.git)?$", current_url)
    ssh_match = re.match(r"git@github\.com:([^/]+)/([^/]+?)(?:\.git)?$", current_url)
    ssh_host_match = re.match(rf"git@{re.escape(account.ssh_host)}:([^/]+)/([^/]+?)(?:\.git)?$", current_url)

    if https_match:
        owner, repo = https_match.group(1), https_match.group(2)
    elif ssh_match:
        owner, repo = ssh_match.group(1), ssh_match.group(2)
    elif ssh_host_match:
        # Already using the correct SSH host, no change needed
        return
    else:
        # Unknown format, skip
        return

    set_remote(path, account, owner, repo)
