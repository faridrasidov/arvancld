# tests/test_client.py
"""Top-level client lifecycle and configuration tests."""

from __future__ import annotations

import pytest

from arvancld import ArvanCloud, AsyncArvanCloud, ClientConfig


def test_sync_client_context_manager_closes_transport() -> None:
    client = ArvanCloud()

    assert not client.is_closed
    with client as active_client:
        assert active_client is client
        assert not active_client.is_closed

    assert client.is_closed


@pytest.mark.asyncio
async def test_async_client_context_manager_closes_transport() -> None:
    client = AsyncArvanCloud()

    assert not client.is_closed
    async with client as active_client:
        assert active_client is client
        assert not active_client.is_closed

    assert client.is_closed


def test_config_normalizes_base_urls() -> None:
    config = ClientConfig(
        auth_base_url="https://auth.example.test/",
        cdn_base_url="https://cdn.example.test/",
    )

    assert config.auth_base_url == "https://auth.example.test"
    assert config.cdn_base_url == "https://cdn.example.test"
    assert config.auth_url("/v1/auth/login") == "https://auth.example.test/v1/auth/login"


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"timeout": 0}, "timeout"),
        ({"auth_base_url": "not-a-url"}, "auth_base_url"),
        ({"cdn_base_url": "/relative"}, "cdn_base_url"),
        ({"redirect_uri": "ftp://example.test"}, "redirect_uri"),
        ({"user_agent": "  "}, "user_agent"),
    ],
)
def test_config_rejects_invalid_values(kwargs: dict[str, object], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        ClientConfig(**kwargs)
