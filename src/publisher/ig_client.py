"""Instagram Graph API wrapper for carousel publishing.

Provides `IGClient` (real Graph API calls via requests) and `MockIGClient`
(in-memory, no network/token needed) behind the same interface, so the
scheduler can run and be tested without real Instagram credentials.
Phase 1 only implements the feed-carousel publish flow; story posting is
Phase 4 scope.
"""
from __future__ import annotations

import os
from typing import Optional, Sequence

import requests
from dotenv import load_dotenv

load_dotenv()

GRAPH_API_VERSION = "v21.0"
GRAPH_API_BASE = "https://graph.facebook.com"
MAX_POSTS_PER_24H = 25
MAX_CAROUSEL_ITEMS = 10


class IGAPIError(RuntimeError):
    """Raised when the Graph API returns an error response."""


class RateLimitExceededError(IGAPIError):
    """Raised when the 24h content-publishing limit has been reached."""


class IGClient:
    """Thin wrapper around the Instagram Graph API content publishing flow."""

    def __init__(
        self,
        ig_user_id: str,
        access_token: str,
        api_version: str = GRAPH_API_VERSION,
        session: Optional[requests.Session] = None,
    ):
        if not ig_user_id or not access_token:
            raise ValueError("ig_user_id and access_token are required for IGClient")
        self.ig_user_id = ig_user_id
        self.access_token = access_token
        self.base_url = f"{GRAPH_API_BASE}/{api_version}"
        self.session = session or requests.Session()

    def _get(self, path: str, params: Optional[dict] = None) -> dict:
        params = dict(params or {})
        params["access_token"] = self.access_token
        resp = self.session.get(f"{self.base_url}/{path}", params=params, timeout=30)
        return self._handle_response(resp)

    def _post(self, path: str, data: Optional[dict] = None) -> dict:
        data = dict(data or {})
        data["access_token"] = self.access_token
        resp = self.session.post(f"{self.base_url}/{path}", data=data, timeout=30)
        return self._handle_response(resp)

    @staticmethod
    def _handle_response(resp: requests.Response) -> dict:
        try:
            payload = resp.json()
        except ValueError as exc:
            raise IGAPIError(f"Non-JSON response from Graph API: {resp.text[:200]}") from exc
        if resp.status_code >= 400 or "error" in payload:
            message = payload.get("error", {}).get("message", resp.text)
            raise IGAPIError(f"Graph API error ({resp.status_code}): {message}")
        return payload

    def get_rate_limit_remaining(self) -> int:
        payload = self._get(f"{self.ig_user_id}/content_publishing_limit", {"fields": "quota_usage"})
        data = payload.get("data") or []
        usage = data[0].get("quota_usage", 0) if data else 0
        return max(MAX_POSTS_PER_24H - usage, 0)

    def _create_carousel_item(self, image_url: str) -> str:
        payload = self._post(f"{self.ig_user_id}/media", {"image_url": image_url, "is_carousel_item": "true"})
        return payload["id"]

    def _create_carousel_container(self, children_ids: Sequence[str], caption: str) -> str:
        payload = self._post(
            f"{self.ig_user_id}/media",
            {"media_type": "CAROUSEL", "children": ",".join(children_ids), "caption": caption},
        )
        return payload["id"]

    def _publish_container(self, creation_id: str) -> str:
        payload = self._post(f"{self.ig_user_id}/media_publish", {"creation_id": creation_id})
        return payload["id"]

    def publish_carousel(self, image_urls: Sequence[str], caption: str) -> str:
        """Runs the full container-create -> publish flow, returns the media id.

        image_urls must be publicly reachable URLs (Graph API requirement) —
        local file paths need to be uploaded/hosted before calling this.
        """
        if not image_urls:
            raise ValueError("image_urls must not be empty")
        if len(image_urls) > MAX_CAROUSEL_ITEMS:
            raise ValueError(f"Graph API allows at most {MAX_CAROUSEL_ITEMS} carousel items")

        if self.get_rate_limit_remaining() <= 0:
            raise RateLimitExceededError("24h content publishing limit reached")

        children_ids = [self._create_carousel_item(url) for url in image_urls]
        container_id = self._create_carousel_container(children_ids, caption)
        return self._publish_container(container_id)


class MockIGClient:
    """In-memory stand-in for IGClient; no network calls, no token required."""

    def __init__(self, max_posts_per_24h: int = MAX_POSTS_PER_24H, fail_next: bool = False):
        self.max_posts_per_24h = max_posts_per_24h
        self.fail_next = fail_next
        self._published: list[dict] = []
        self._next_id = 1000

    def get_rate_limit_remaining(self) -> int:
        return max(self.max_posts_per_24h - len(self._published), 0)

    def publish_carousel(self, image_urls: Sequence[str], caption: str) -> str:
        if not image_urls:
            raise ValueError("image_urls must not be empty")
        if len(image_urls) > MAX_CAROUSEL_ITEMS:
            raise ValueError(f"Graph API allows at most {MAX_CAROUSEL_ITEMS} carousel items")
        if self.fail_next:
            self.fail_next = False
            raise IGAPIError("Simulated Graph API failure")
        if self.get_rate_limit_remaining() <= 0:
            raise RateLimitExceededError("24h content publishing limit reached (mock)")

        self._next_id += 1
        media_id = f"mock-media-{self._next_id}"
        self._published.append({"media_id": media_id, "image_urls": list(image_urls), "caption": caption})
        return media_id

    @property
    def published(self) -> list[dict]:
        return list(self._published)


def create_ig_client(
    ig_user_id: Optional[str] = None,
    access_token: Optional[str] = None,
    mock: Optional[bool] = None,
):
    """Factory: returns a real IGClient, or a MockIGClient when credentials
    are absent / IG_MOCK_MODE=true, so callers don't need real tokens to run."""
    ig_user_id = ig_user_id or os.getenv("IG_USER_ID")
    access_token = access_token or os.getenv("IG_ACCESS_TOKEN")

    if mock is None:
        env_flag = os.getenv("IG_MOCK_MODE", "").strip().lower()
        mock = env_flag == "true" or not (ig_user_id and access_token)

    if mock:
        return MockIGClient()
    return IGClient(ig_user_id=ig_user_id, access_token=access_token)
