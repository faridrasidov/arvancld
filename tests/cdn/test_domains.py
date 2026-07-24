# tests/cdn/test_domains.py
"""Mocked tests for CDN domain listing."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import httpx
import pytest
import respx

from arvancld import (
    APIError,
    ArvanCloud,
    ArvanCloudTimeoutError,
    AsyncArvanCloud,
    AuthenticationError,
    AuthenticationRequiredError,
    InvalidResponseError,
    NetworkError,
)

LOGIN_URL = "https://dejban.arvancloud.ir/v1/auth/login"
DOMAINS_URL = "https://napi.arvancloud.ir/cdn/4.0/domains"
TEST_EMAIL = "person@example.com"
TEST_PASSWORD = "do-not-leak-this-password"


def _mock_login(login_payload: dict[str, object]) -> None:
    respx.post(LOGIN_URL).mock(return_value=httpx.Response(200, json=login_payload))


def _assert_no_browser_headers(request: httpx.Request) -> None:
    forbidden_headers = {
        "dnt",
        "origin",
        "referer",
        "sec-fetch-dest",
        "sec-fetch-mode",
        "sec-fetch-site",
        "sec-gpc",
    }
    assert forbidden_headers.isdisjoint(request.headers)


@respx.mock
def test_sync_list_domains_sends_expected_request_and_parses_fields(
    login_payload: dict[str, object],
    cdn_domain_payload: dict[str, object],
) -> None:
    _mock_login(login_payload)
    route = respx.get(DOMAINS_URL, params={"page": "1", "perPage": "5"}).mock(
        return_value=httpx.Response(
            200,
            json={**cdn_domain_payload, "ignoredEnvelopeField": True},
        )
    )

    with ArvanCloud() as client:
        client.auth.login(TEST_EMAIL, TEST_PASSWORD)
        page = client.cdn.domains.list(page=1, per_page=5)

    domain = page.data[0]
    assert domain.id == UUID("f1b2ad75-ae1d-4c73-ba25-e1d55b950d07")
    assert domain.account_id == UUID("af999c67-2a12-517c-b52b-8bb5e2b59bad")
    assert domain.user_id == UUID("af999c67-2a12-517c-b52b-8bb5e2b59bad")
    assert domain.domain == "snapp.ir"
    assert domain.ns_keys == ["f.ns.arvancdn.ir", "s.ns.arvancdn.ir"]
    assert domain.current_ns == ["f.ns.arvancdn.ir", "s.ns.arvancdn.ir"]
    assert domain.status == "active"
    assert domain.cname_target is None
    assert domain.use_new_waf_engine is True
    assert domain.fingerprint_status is False
    assert domain.created_at == datetime(2026, 4, 2, 18, 26, 45, tzinfo=UTC)
    assert domain.updated_at == datetime(2026, 7, 24, 15, 15, 12, tzinfo=UTC)
    assert page.meta.per_page == 15
    assert page.message == ""

    request = route.calls[0].request
    assert request.method == "GET"
    assert request.url.path == "/cdn/4.0/domains"
    assert request.url.params["page"] == "1"
    assert request.url.params["perPage"] == "5"
    assert request.headers["Accept"] == "application/json"
    assert request.headers["User-Agent"] == "arvancld/0.1.0"
    assert request.headers["Authorization"] == "Bearer access-secret"
    _assert_no_browser_headers(request)


@respx.mock
@pytest.mark.asyncio
async def test_async_list_domains_sends_expected_request(
    login_payload: dict[str, object],
    cdn_domain_payload: dict[str, object],
) -> None:
    _mock_login(login_payload)
    route = respx.get(DOMAINS_URL, params={"page": "2", "perPage": "10"}).mock(
        return_value=httpx.Response(200, json=cdn_domain_payload)
    )

    async with AsyncArvanCloud() as client:
        await client.auth.login(TEST_EMAIL, TEST_PASSWORD)
        page = await client.cdn.domains.list(page=2, per_page=10)

    assert page.data[0].domain == "snapp.ir"
    request = route.calls[0].request
    assert request.headers["Authorization"] == "Bearer access-secret"
    assert request.url.params["page"] == "2"
    assert request.url.params["perPage"] == "10"


def test_list_domains_requires_login() -> None:
    with ArvanCloud() as client, pytest.raises(AuthenticationRequiredError) as captured:
        client.cdn.domains.list()

    assert "access-secret" not in str(captured.value)


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"page": 0}, "page"),
        ({"per_page": 0}, "per_page"),
    ],
)
def test_list_domains_rejects_invalid_pagination(
    kwargs: dict[str, int],
    message: str,
) -> None:
    with ArvanCloud() as client, pytest.raises(ValueError, match=message):
        client.cdn.domains.list(**kwargs)


@pytest.mark.parametrize(
    ("status_code", "exception_type"),
    [
        (400, APIError),
        (401, AuthenticationError),
        (403, AuthenticationError),
        (500, APIError),
    ],
)
@respx.mock
def test_list_domains_maps_api_errors_without_leaking_secrets(
    status_code: int,
    exception_type: type[APIError],
    login_payload: dict[str, object],
) -> None:
    _mock_login(login_payload)
    respx.get(DOMAINS_URL, params={"page": "1", "perPage": "5"}).mock(
        return_value=httpx.Response(
            status_code,
            headers={"X-Request-Id": "request-456"},
            json={
                "message": f"rejected {TEST_PASSWORD}",
                "token": "server-secret-token",
            },
        )
    )

    with ArvanCloud() as client, pytest.raises(exception_type) as captured:
        client.auth.login(TEST_EMAIL, TEST_PASSWORD)
        client.cdn.domains.list()

    error = captured.value
    assert error.status_code == status_code
    assert error.request_id == "request-456"
    assert TEST_PASSWORD not in str(error)
    assert "access-secret" not in str(error)
    assert "server-secret-token" not in str(error)


@respx.mock
def test_list_domains_maps_timeout_without_leaking_token(
    login_payload: dict[str, object],
) -> None:
    _mock_login(login_payload)
    respx.get(DOMAINS_URL, params={"page": "1", "perPage": "5"}).mock(
        side_effect=httpx.ReadTimeout("transport timed out")
    )

    with ArvanCloud() as client, pytest.raises(ArvanCloudTimeoutError) as captured:
        client.auth.login(TEST_EMAIL, TEST_PASSWORD)
        client.cdn.domains.list()

    assert "access-secret" not in str(captured.value)


@respx.mock
def test_list_domains_maps_network_failure_without_leaking_token(
    login_payload: dict[str, object],
) -> None:
    _mock_login(login_payload)
    respx.get(DOMAINS_URL, params={"page": "1", "perPage": "5"}).mock(
        side_effect=httpx.ConnectError("connection failed")
    )

    with ArvanCloud() as client, pytest.raises(NetworkError) as captured:
        client.auth.login(TEST_EMAIL, TEST_PASSWORD)
        client.cdn.domains.list()

    assert "access-secret" not in str(captured.value)


@respx.mock
def test_list_domains_rejects_malformed_json(login_payload: dict[str, object]) -> None:
    _mock_login(login_payload)
    respx.get(DOMAINS_URL, params={"page": "1", "perPage": "5"}).mock(
        return_value=httpx.Response(
            200,
            headers={"Content-Type": "application/json"},
            content=b"{",
        )
    )

    with ArvanCloud() as client, pytest.raises(InvalidResponseError, match="invalid JSON"):
        client.auth.login(TEST_EMAIL, TEST_PASSWORD)
        client.cdn.domains.list()


@respx.mock
def test_list_domains_rejects_missing_required_response_fields(
    login_payload: dict[str, object],
) -> None:
    _mock_login(login_payload)
    respx.get(DOMAINS_URL, params={"page": "1", "perPage": "5"}).mock(
        return_value=httpx.Response(200, json={"data": []})
    )

    with ArvanCloud() as client, pytest.raises(InvalidResponseError, match="expected contract"):
        client.auth.login(TEST_EMAIL, TEST_PASSWORD)
        client.cdn.domains.list()


@respx.mock
def test_list_domains_ignores_unknown_response_fields(
    login_payload: dict[str, object],
    cdn_domain_payload: dict[str, object],
) -> None:
    payload = dict(cdn_domain_payload)
    domains = list(payload["data"])
    first_domain = dict(domains[0])
    first_domain["futureField"] = {"can": "be ignored"}
    payload["data"] = [first_domain]
    _mock_login(login_payload)
    respx.get(DOMAINS_URL, params={"page": "1", "perPage": "5"}).mock(
        return_value=httpx.Response(200, json=payload)
    )

    with ArvanCloud() as client:
        client.auth.login(TEST_EMAIL, TEST_PASSWORD)
        page = client.cdn.domains.list()

    assert page.data[0].domain == "snapp.ir"
