from __future__ import annotations

import os
import platform
import subprocess
from pathlib import Path

from .config import Account


BEGIN_PREFIX = "# BEGIN github-auto "
END_PREFIX = "# END github-auto "


def ssh_config_path() -> Path:
    return Path.home() / ".ssh" / "config"


def get_ssh_dir() -> Path:
    return Path.home() / ".ssh"


def generate_ssh_key(account_name: str, email: str, key_path: Path) -> Path:
    """Generate SSH key using ssh-keygen."""
    key_path = Path(key_path).expanduser()
    key_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        "ssh-keygen",
        "-t", "rsa",
        "-f", str(key_path),
        "-C", email,
        "-N", "",  # No passphrase
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ssh-keygen failed: {result.stderr}")

    # Set proper permissions
    system = platform.system()
    if system != "Windows":
        os.chmod(str(key_path), 0o600)
        os.chmod(str(key_path.with_suffix(".pub")), 0o644)

    return key_path


def setup_ssh(account_name: str, account: Account, generate_if_missing: bool = False) -> Path:
    path = ssh_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    identity = Path(account.ssh_key).expanduser()

    # Generate SSH key if it doesn't exist and generation is requested
    if generate_if_missing and not identity.exists():
        identity = generate_ssh_key(account_name, account.email, identity)

    identity = str(identity).replace("\\", "/")
    block = (
        f"{BEGIN_PREFIX}{account_name}\n"
        f"Host {account.ssh_host}\n"
        f"    HostName github.com\n"
        f"    User git\n"
        f"    IdentityFile {identity}\n"
        f"    IdentitiesOnly yes\n"
        f"    StrictHostKeyChecking no\n"
        f"{END_PREFIX}{account_name}\n"
    )

    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    start_marker = f"{BEGIN_PREFIX}{account_name}"
    end_marker = f"{END_PREFIX}{account_name}"

    start = existing.find(start_marker)
    if start >= 0:
        end = existing.find(end_marker, start)
        if end >= 0:
            end += len(end_marker)
            if end < len(existing) and existing[end] == "\n":
                end += 1
            existing = existing[:start] + existing[end:]
    if existing and not existing.endswith("\n"):
        existing += "\n"
    existing += block

    path.write_text(existing, encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return path


def ssh_remote(account: Account, owner: str, repo: str) -> str:
    return f"git@{account.ssh_host}:{owner}/{repo}.git"
