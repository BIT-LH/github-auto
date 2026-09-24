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

    def star_repo(self, owner: str, repo: str) -> None:
        r = self.client.put(f"/user/starred/{owner}/{repo}")
        r.raise_for_status()

    def unstar_repo(self, owner: str, repo: str) -> None:
        r = self.client.delete(f"/user/starred/{owner}/{repo}")
        r.raise_for_status()

    def is_starred(self, owner: str, repo: str) -> bool:
        r = self.client.get(f"/user/starred/{owner}/{repo}")
        return r.status_code == 204

    def search_repos(self, query: str, per_page: int = 30) -> list[dict[str, Any]]:
        r = self.client.get(
            "/search/repositories",
            params={"q": query, "per_page": per_page},
        )
        r.raise_for_status()
        return r.json().get("items", [])

    def list_contents(self, owner: str, repo: str, path: str = "") -> list[dict[str, Any]]:
        r = self.client.get(f"/repos/{owner}/{repo}/contents/{path}")
        r.raise_for_status()
        return r.json()

    def get_content(self, owner: str, repo: str, path: str) -> dict[str, Any]:
        r = self.client.get(f"/repos/{owner}/{repo}/contents/{path}")
        r.raise_for_status()
        return r.json()

    def get_archive_url(self, owner: str, repo: str, ref: str = "main") -> str:
        """Get repository archive download URL."""
        r = self.client.get(f"/repos/{owner}/{repo}/zipball/{ref}")
        r.raise_for_status()
        return r.json().get("url", "")

    def get_download_url(self, owner: str, repo: str, ref: str = "main") -> str:
        """Get the archive download URL for a repository."""
        r = self.client.get(f"/repos/{owner}/{repo}/zipball/{ref}")
        r.raise_for_status()
        return r.json().get("url", "")

    # --- Fork ---

    def fork_repo(self, owner: str, repo: str) -> dict[str, Any]:
        r = self.client.post(f"/repos/{owner}/{repo}/forks")
        r.raise_for_status()
        return r.json()

    # --- Watch (Notifications) ---

    def watch_repo(self, owner: str, repo: str) -> None:
        r = self.client.put(
            f"/repos/{owner}/{repo}/subscription",
            json={"subscribed": True, "ignored": False},
        )
        r.raise_for_status()

    def unwatch_repo(self, owner: str, repo: str) -> None:
        r = self.client.delete(f"/repos/{owner}/{repo}/subscription")
        if r.status_code not in (204,):
            r.raise_for_status()

    def is_watching(self, owner: str, repo: str) -> bool:
        r = self.client.get(f"/repos/{owner}/{repo}/subscription")
        return r.status_code == 200

    # --- Follow Users ---

    def follow_user(self, username: str) -> None:
        r = self.client.put(f"/user/following/{username}")
        r.raise_for_status()

    def unfollow_user(self, username: str) -> None:
        r = self.client.delete(f"/user/following/{username}")
        if r.status_code not in (204,):
            r.raise_for_status()

    def is_following(self, username: str) -> bool:
        r = self.client.get(f"/user/following/{username}")
        return r.status_code == 204

    def list_followers(self, username: str) -> list[dict[str, Any]]:
        r = self.client.get(f"/users/{username}/followers")
        r.raise_for_status()
        return r.json()

    def list_following(self, username: str) -> list[dict[str, Any]]:
        r = self.client.get(f"/users/{username}/following")
        r.raise_for_status()
        return r.json()

    def get_user(self, username: str) -> dict[str, Any]:
        r = self.client.get(f"/users/{username}")
        r.raise_for_status()
        return r.json()
