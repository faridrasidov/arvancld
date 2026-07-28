# tests/test_retry.py
"""Retry-policy and transport-resilience tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from email.utils import format_datetime

import httpx
import pytest
import respx

from arvancld import (
    APIError,
    ArvanCloud,
    ArvanCloudTimeoutError,
    AsyncArvanCloud,
    RetryPolicy,
)
from arvancld._transport import SyncTransport, _retry_after_seconds, _retry_delay
from arvancld.auth.models import LoginResponse
from arvancld.config import ClientConfig

LOGIN_URL = "https://dejban.arvancloud.ir/v1/auth/login"
DOMAINS_URL = "https://napi.arvancloud.ir/cdn/4.0/domains"
TEST_EMAIL = "person@example.com"
TEST_PASSWORD = "do-not-leak-this-password"


def _mock_login(login_payload: dict[str, object]) -> None:
    respx.post(LOGIN_URL).mock(return_value=httpx.Response(200, json=login_payload))


@respx.mock
def test_sync_get_retries_retryable_statuses_until_success(
    login_payload: dict[str, object],
    cdn_domain_payload: dict[str, object],
) -> None:
    _mock_login(login_payload)
    responses = iter(
        [
            httpx.Response(503, headers={"Retry-After": "0"}),
            httpx.Response(502, headers={"Retry-After": "0"}),
            httpx.Response(200, json=cdn_domain_payload),
        ]
    )
    route = respx.get(DOMAINS_URL).mock(side_effect=lambda request: next(responses))

    with ArvanCloud() as client:
        client.auth.login(TEST_EMAIL, TEST_PASSWORD)
        page = client.cdn.domains.list()

    assert page.data[0].domain == "snapp.ir"
    assert route.call_count == 3


@respx.mock
@pytest.mark.asyncio
async def test_async_get_retries_transport_failure_until_success(
    login_payload: dict[str, object],
    cdn_domain_payload: dict[str, object],
) -> None:
    _mock_login(login_payload)
    responses = iter(
        [
            httpx.ReadTimeout("temporary timeout"),
            httpx.Response(200, json=cdn_domain_payload),
        ]
    )

    def next_result(request: httpx.Request) -> httpx.Response:
        result = next(responses)
        if isinstance(result, Exception):
            raise result
        return result

    route = respx.get(DOMAINS_URL).mock(side_effect=next_result)
    policy = RetryPolicy(backoff_factor=0)

    async with AsyncArvanCloud(retry_policy=policy) as client:
        await client.auth.login(TEST_EMAIL, TEST_PASSWORD)
        page = await client.cdn.domains.list()

    assert page.data[0].domain == "snapp.ir"
    assert route.call_count == 2


@respx.mock
def test_get_raises_final_api_error_after_retry_budget_is_exhausted(
    login_payload: dict[str, object],
) -> None:
    _mock_login(login_payload)
    route = respx.get(DOMAINS_URL).mock(
        side_effect=lambda request: httpx.Response(
            503,
            headers={"Retry-After": "0", "X-Request-Id": "last-attempt"},
        )
    )

    with ArvanCloud() as client, pytest.raises(APIError) as captured:
        client.auth.login(TEST_EMAIL, TEST_PASSWORD)
        client.cdn.domains.list()

    assert captured.value.status_code == 503
    assert captured.value.request_id == "last-attempt"
    assert route.call_count == 3


@respx.mock
def test_retry_policy_none_disables_get_retries(
    login_payload: dict[str, object],
) -> None:
    _mock_login(login_payload)
    route = respx.get(DOMAINS_URL).mock(return_value=httpx.Response(503))

    with ArvanCloud(retry_policy=None) as client, pytest.raises(APIError):
        client.auth.login(TEST_EMAIL, TEST_PASSWORD)
        client.cdn.domains.list()

    assert route.call_count == 1


@pytest.mark.parametrize("method", ["POST", "PUT", "DELETE"])
@respx.mock
def test_non_get_requests_are_never_retried(method: str) -> None:
    url = "https://api.example.test/resource"
    route = getattr(respx, method.lower())(url).mock(return_value=httpx.Response(503))
    transport = SyncTransport(ClientConfig(retry_policy=RetryPolicy(backoff_factor=0)))

    try:
        with pytest.raises(APIError):
            transport.request_model(method, url, model=LoginResponse)
    finally:
        transport.close()

    assert route.call_count == 1


@respx.mock
def test_exhausted_get_timeout_preserves_timeout_exception_mapping(
    login_payload: dict[str, object],
) -> None:
    _mock_login(login_payload)
    route = respx.get(DOMAINS_URL).mock(side_effect=httpx.ReadTimeout("persistent timeout"))
    policy = RetryPolicy(backoff_factor=0)

    with ArvanCloud(retry_policy=policy) as client, pytest.raises(ArvanCloudTimeoutError):
        client.auth.login(TEST_EMAIL, TEST_PASSWORD)
        client.cdn.domains.list()

    assert route.call_count == 3


@respx.mock
def test_retry_after_is_respected_and_capped(
    monkeypatch: pytest.MonkeyPatch,
    login_payload: dict[str, object],
    cdn_domain_payload: dict[str, object],
) -> None:
    _mock_login(login_payload)
    responses = iter(
        [
            httpx.Response(429, headers={"Retry-After": "10"}),
            httpx.Response(200, json=cdn_domain_payload),
        ]
    )
    route = respx.get(DOMAINS_URL).mock(side_effect=lambda request: next(responses))
    sleeps: list[float] = []
    monkeypatch.setattr("arvancld._transport.time.sleep", sleeps.append)
    policy = RetryPolicy(max_retry_after=3)

    with ArvanCloud(retry_policy=policy) as client:
        client.auth.login(TEST_EMAIL, TEST_PASSWORD)
        client.cdn.domains.list()

    assert route.call_count == 2
    assert sleeps == [3.0]


def test_retry_delay_uses_exponential_full_jitter_bound(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bounds: list[tuple[float, float]] = []

    def fake_uniform(lower: float, upper: float) -> float:
        bounds.append((lower, upper))
        return upper

    monkeypatch.setattr("arvancld._transport.random.uniform", fake_uniform)

    delay = _retry_delay(RetryPolicy(), attempt=3)

    assert delay == 2.0
    assert bounds == [(0.0, 2.0)]


def test_retry_after_parses_numeric_and_http_date_values() -> None:
    now = datetime(2026, 7, 28, 12, 0, tzinfo=UTC)
    retry_at = format_datetime(now + timedelta(seconds=12), usegmt=True)

    assert _retry_after_seconds("2.5", now=now) == 2.5
    assert _retry_after_seconds(retry_at, now=now) == 12.0
    assert _retry_after_seconds("-10", now=now) == 0.0
    assert _retry_after_seconds("not-a-date", now=now) is None
