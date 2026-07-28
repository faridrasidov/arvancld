# tests/test_client.py
"""Top-level client lifecycle and configuration tests."""

from __future__ import annotations

import httpx
import pytest

from arvancld import ArvanCloud, AsyncArvanCloud, ClientConfig, RetryPolicy


def test_sync_client_context_manager_closes_transport() -> None:
    client = ArvanCloud()

    assert not client.is_closed
    with client as active_client:
        assert active_client is client
        assert active_client.cdn.domains is not None
        assert active_client.cdn.dns_records is not None
        assert not active_client.is_closed

    assert client.is_closed


@pytest.mark.asyncio
async def test_async_client_context_manager_closes_transport() -> None:
    client = AsyncArvanCloud()

    assert not client.is_closed
    async with client as active_client:
        assert active_client is client
        assert active_client.cdn.domains is not None
        assert active_client.cdn.dns_records is not None
        assert not active_client.is_closed

    assert client.is_closed


def test_sync_client_accepts_native_httpx_timeout_and_limits() -> None:
    timeout = httpx.Timeout(connect=1.0, read=2.0, write=3.0, pool=4.0)
    limits = httpx.Limits(
        max_connections=20,
        max_keepalive_connections=10,
        keepalive_expiry=15.0,
    )

    with ArvanCloud(timeout=timeout, limits=limits) as client:
        assert client.config.timeout is timeout
        assert client.config.limits is limits


@pytest.mark.asyncio
async def test_async_client_accepts_native_httpx_timeout_and_limits() -> None:
    timeout = httpx.Timeout(connect=1.0, read=2.0, write=3.0, pool=4.0)
    limits = httpx.Limits(
        max_connections=20,
        max_keepalive_connections=10,
        keepalive_expiry=15.0,
    )

    async with AsyncArvanCloud(timeout=timeout, limits=limits) as client:
        assert client.config.timeout is timeout
        assert client.config.limits is limits


def test_client_enables_retries_by_default_and_allows_opt_out() -> None:
    with ArvanCloud() as default_client, ArvanCloud(retry_policy=None) as opt_out_client:
        assert default_client.config.retry_policy == RetryPolicy()
        assert opt_out_client.config.retry_policy is None


def test_retry_policy_copies_status_codes_into_an_immutable_set() -> None:
    source = {429}
    policy = RetryPolicy(status_codes=source)  # type: ignore[arg-type]

    source.add(503)

    assert policy.status_codes == frozenset({429})


def test_config_normalizes_base_urls() -> None:
    config = ClientConfig(
        auth_base_url="https://auth.example.test/",
        cdn_base_url="https://cdn.example.test/",
    )

    assert config.auth_base_url == "https://auth.example.test"
    assert config.cdn_base_url == "https://cdn.example.test"
    assert config.auth_url("/v1/auth/login") == "https://auth.example.test/v1/auth/login"
    assert config.cdn_url("/domains") == "https://cdn.example.test/domains"


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


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"max_attempts": 0}, "max_attempts"),
        ({"backoff_factor": -0.1}, "backoff_factor"),
        ({"max_backoff": -0.1}, "max_backoff"),
        ({"max_retry_after": -0.1}, "max_retry_after"),
        ({"status_codes": frozenset({200})}, "status_codes"),
    ],
)
def test_retry_policy_rejects_invalid_values(
    kwargs: dict[str, object],
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        RetryPolicy(**kwargs)
