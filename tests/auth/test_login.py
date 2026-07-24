# tests/auth/test_login.py
"""Mocked tests for synchronous and asynchronous account login."""

from __future__ import annotations

import json
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
    InvalidResponseError,
    NetworkError,
)

LOGIN_URL = "https://dejban.arvancloud.ir/v1/auth/login"
TEST_EMAIL = "person@example.com"
TEST_PASSWORD = "do-not-leak-this-password"


@respx.mock
def test_sync_login_sends_expected_request_and_stores_tokens(
    login_payload: dict[str, object],
) -> None:
    route = respx.post(LOGIN_URL).mock(
        return_value=httpx.Response(
            200,
            json={**login_payload, "ignoredEnvelopeField": True},
        )
    )

    with ArvanCloud() as client:
        result = client.auth.login(TEST_EMAIL, TEST_PASSWORD)

        assert client.auth.tokens is result
        assert result.access_token == "access-secret"
        assert result.refresh_token == "refresh-secret"
        assert result.expires_at == datetime(2026, 7, 25, 4, 7, 52, tzinfo=UTC)
        assert result.default_account == UUID("af999c67-2a12-517c-b52b-8bb5e2b59bad")
        assert result.flow == "ProvideCredential"
        assert result.next == "RedirectToPanel"
        assert "access-secret" not in repr(result)
        assert "refresh-secret" not in repr(result)

    request = route.calls[0].request
    assert json.loads(request.content) == {
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD,
    }
    assert request.headers["Accept"] == "application/json"
    assert request.headers["Content-Type"] == "application/json"
    assert request.headers["User-Agent"] == "arvancld/0.1.0"
    assert request.headers["X-Redirect-Uri"] == "https://panel.arvancloud.ir/"

    forbidden_headers = {
        "sec-fetch-dest",
        "sec-fetch-mode",
        "sec-fetch-site",
        "x-content-type-options",
        "x-frame-options",
    }
    assert forbidden_headers.isdisjoint(request.headers)


@respx.mock
@pytest.mark.asyncio
async def test_async_login_sends_expected_request_and_stores_tokens(
    login_payload: dict[str, object],
) -> None:
    route = respx.post(LOGIN_URL).mock(return_value=httpx.Response(200, json=login_payload))

    async with AsyncArvanCloud(redirect_uri="https://example.test/after-login") as client:
        result = await client.auth.login(TEST_EMAIL, TEST_PASSWORD)

        assert client.auth.tokens is result
        assert result.access_token == "access-secret"

    request = route.calls[0].request
    assert request.method == "POST"
    assert json.loads(request.content) == {
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD,
    }
    assert request.headers["X-Redirect-Uri"] == "https://example.test/after-login"


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
def test_login_maps_api_errors_without_leaking_credentials(
    status_code: int,
    exception_type: type[APIError],
) -> None:
    respx.post(LOGIN_URL).mock(
        return_value=httpx.Response(
            status_code,
            headers={"X-Request-Id": "request-123"},
            json={
                "message": f"rejected {TEST_PASSWORD}",
                "token": "server-secret-token",
            },
        )
    )

    with ArvanCloud() as client, pytest.raises(exception_type) as captured:
        client.auth.login(TEST_EMAIL, TEST_PASSWORD)

    error = captured.value
    assert error.status_code == status_code
    assert error.request_id == "request-123"
    assert TEST_PASSWORD not in str(error)
    assert "server-secret-token" not in str(error)


@respx.mock
def test_login_maps_timeout_without_leaking_credentials() -> None:
    respx.post(LOGIN_URL).mock(side_effect=httpx.ReadTimeout("transport timed out"))

    with ArvanCloud() as client, pytest.raises(ArvanCloudTimeoutError) as captured:
        client.auth.login(TEST_EMAIL, TEST_PASSWORD)

    assert TEST_PASSWORD not in str(captured.value)


@respx.mock
def test_login_maps_network_failure_without_leaking_credentials() -> None:
    respx.post(LOGIN_URL).mock(side_effect=httpx.ConnectError("connection failed"))

    with ArvanCloud() as client, pytest.raises(NetworkError) as captured:
        client.auth.login(TEST_EMAIL, TEST_PASSWORD)

    assert TEST_PASSWORD not in str(captured.value)


@respx.mock
def test_login_rejects_malformed_json() -> None:
    respx.post(LOGIN_URL).mock(
        return_value=httpx.Response(
            200,
            headers={"Content-Type": "application/json"},
            content=b"{",
        )
    )

    with ArvanCloud() as client, pytest.raises(InvalidResponseError, match="invalid JSON"):
        client.auth.login(TEST_EMAIL, TEST_PASSWORD)


@respx.mock
def test_login_rejects_missing_required_response_fields() -> None:
    respx.post(LOGIN_URL).mock(return_value=httpx.Response(200, json={"data": {}}))

    with ArvanCloud() as client, pytest.raises(InvalidResponseError, match="expected contract"):
        client.auth.login(TEST_EMAIL, TEST_PASSWORD)


@respx.mock
def test_login_ignores_unknown_response_fields(login_payload: dict[str, object]) -> None:
    response_payload = dict(login_payload)
    response_data = dict(response_payload["data"])
    response_data["futureField"] = {"can": "be ignored"}
    response_payload["data"] = response_data
    respx.post(LOGIN_URL).mock(return_value=httpx.Response(200, json=response_payload))

    with ArvanCloud() as client:
        result = client.auth.login(TEST_EMAIL, TEST_PASSWORD)

    assert result.default_account == UUID("af999c67-2a12-517c-b52b-8bb5e2b59bad")


def test_login_rejects_blank_credentials_before_request() -> None:
    with ArvanCloud() as client:
        with pytest.raises(ValueError, match="email"):
            client.auth.login(" ", TEST_PASSWORD)
        with pytest.raises(ValueError, match="password"):
            client.auth.login(TEST_EMAIL, "")
