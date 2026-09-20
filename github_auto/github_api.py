from __future__ import annotations

from typing import Any
import httpx

from .security import get_token


def headers(token: str) -> dict[str, str]:
    return {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
    }


class GitHubAPI:
    def __init__(self, account_name: str, base_url: str = "https://api.github.com"):
        token = get_token(account_name)
        if not token:
            raise RuntimeError(
                f"账号 `{account_name}` 没有可用 Token。"
                "请运行 `github-auto auth token-set <account>`"
            )
        self.client = httpx.Client(
            base_url=base_url.rstrip("/"),
            headers=headers(token),
            timeout=30,
        )

    def close(self):
        self.client.close()

    def user(self) -> dict[str, Any]:
        r = self.client.get("/user")
        r.raise_for_status()
        return r.json()

    def create_repo(
        self,
        name: str,
        private: bool = False,
        description: str = "",
        auto_init: bool = False,
    ) -> dict[str, Any]:
        r = self.client.post(
            "/user/repos",
            json={
                "name": name,
                "private": private,
                "description": description,
                "auto_init": auto_init,
            },
        )
        r.raise_for_status()
        return r.json()

    def list_repos(self, per_page: int = 100) -> list[dict[str, Any]]:
        r = self.client.get("/user/repos", params={"per_page": per_page})
        r.raise_for_status()
        return r.json()

    def repo(self, owner: str, repo: str) -> dict[str, Any]:
        r = self.client.get(f"/repos/{owner}/{repo}")
        r.raise_for_status()
        return r.json()

    def delete_repo(self, owner: str, repo: str) -> None:
        r = self.client.delete(f"/repos/{owner}/{repo}")
        if r.status_code not in (204,):
            r.raise_for_status()

    def update_repo(
        self,
        owner: str,
        repo: str,
        description: str | None = None,
        private: bool | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        if description is not None:
            payload["description"] = description
        if private is not None:
            payload["private"] = private
        r = self.client.patch(f"/repos/{owner}/{repo}", json=payload)
        r.raise_for_status()
        return r.json()
