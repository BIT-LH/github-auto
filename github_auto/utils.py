from __future__ import annotations

import shlex
import shutil
import subprocess
from pathlib import Path
from typing import Iterable


def require_command(name: str) -> None:
    if not shutil.which(name):
        raise RuntimeError(f"未找到命令 `{name}`，请先安装并加入 PATH")


def run(
    args: Iterable[str],
    cwd: Path | None = None,
    env: dict | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess:
    args = [str(x) for x in args]
    result = subprocess.run(
        args,
        cwd=str(cwd) if cwd else None,
        env=env,
        text=True,
        capture_output=True,
    )
    if check and result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise RuntimeError(
            f"命令执行失败: {shlex.join(args)}\n{detail}"
        )
    return result
