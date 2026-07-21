import os

import pytest

from src.publisher.ig_client import (
    IGAPIError,
    IGClient,
    MockIGClient,
    RateLimitExceededError,
    create_ig_client,
)


def test_mock_client_publishes_and_tracks_rate_limit():
    client = MockIGClient()
    assert client.get_rate_limit_remaining() == 25

    media_id = client.publish_carousel(["img1.png", "img2.png"], "caption text")

    assert media_id.startswith("mock-media-")
    assert client.get_rate_limit_remaining() == 24
    assert client.published[0]["caption"] == "caption text"


def test_mock_client_rejects_empty_or_too_many_images():
    client = MockIGClient()
    with pytest.raises(ValueError):
        client.publish_carousel([], "caption")
    with pytest.raises(ValueError):
        client.publish_carousel([f"img{i}.png" for i in range(11)], "caption")


def test_mock_client_simulated_failure():
    client = MockIGClient(fail_next=True)
    with pytest.raises(IGAPIError):
        client.publish_carousel(["img1.png"], "caption")
    # failure did not consume rate limit / record a publish
    assert client.published == []


def test_mock_client_rate_limit_exhausted():
    client = MockIGClient(max_posts_per_24h=1)
    client.publish_carousel(["img1.png"], "caption")
    with pytest.raises(RateLimitExceededError):
        client.publish_carousel(["img2.png"], "caption")


def test_create_ig_client_defaults_to_mock_without_credentials(monkeypatch):
    monkeypatch.delenv("IG_USER_ID", raising=False)
    monkeypatch.delenv("IG_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("IG_MOCK_MODE", raising=False)

    client = create_ig_client()
    assert isinstance(client, MockIGClient)


def test_create_ig_client_uses_real_client_when_credentials_present(monkeypatch):
    monkeypatch.setenv("IG_USER_ID", "12345")
    monkeypatch.setenv("IG_ACCESS_TOKEN", "token")
    monkeypatch.delenv("IG_MOCK_MODE", raising=False)

    client = create_ig_client()
    assert isinstance(client, IGClient)


def test_create_ig_client_forces_mock_via_env(monkeypatch):
    monkeypatch.setenv("IG_USER_ID", "12345")
    monkeypatch.setenv("IG_ACCESS_TOKEN", "token")
    monkeypatch.setenv("IG_MOCK_MODE", "true")

    client = create_ig_client()
    assert isinstance(client, MockIGClient)


def test_ig_client_requires_credentials():
    with pytest.raises(ValueError):
        IGClient(ig_user_id="", access_token="")
