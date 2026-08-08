"""Synchronous and asynchronous token refresh tests."""

from __future__ import annotations

import json

import httpx
import pytest
import respx

from arvancld import (
    APIError,
    ArvanCloud,
    AsyncArvanCloud,
    AuthenticationError,
    AuthenticationRequiredError,
    InvalidResponseError,
    NetworkError,
)

LOGIN_URL = "https://dejban.arvancloud.ir/v1/auth/login"
REFRESH_URL = "https://dejban.arvancloud.ir/v1/auth/refresh-token"
TEST_EMAIL = "person@example.com"
TEST_PASSWORD = "account-secret"
OLD_ACCESS_TOKEN = "old-access-secret"
OLD_REFRESH_TOKEN = "old-refresh-secret"
NEW_ACCESS_TOKEN = "new-access-secret"
NEW_REFRESH_TOKEN = "new-refresh-secret"
DEFAULT_ACCOUNT = "af999c67-2a12-517c-b52b-8bb5e2b59bad"


def _login_payload() -> dict[str, object]:
    return {
        "data": {
            "accessToken": OLD_ACCESS_TOKEN,
            "refreshToken": OLD_REFRESH_TOKEN,
            "expiresAt": "2030-08-08T00:00:00Z",
            "defaultAccount": DEFAULT_ACCOUNT,
            "flow": "ProvideCredential",
            "next": "RedirectToPanel",
        }
    }


def _refresh_payload() -> dict[str, object]:
    return {
        "data": {
            "accessToken": NEW_ACCESS_TOKEN,
            "refreshToken": NEW_REFRESH_TOKEN,
            "expiresAt": "2030-08-09T00:00:00Z",
        }
    }


def _mock_login() -> None:
    respx.post(LOGIN_URL).mock(return_value=httpx.Response(200, json=_login_payload()))


@respx.mock
def test_sync_refresh_sends_expected_request_and_preserves_account_state() -> None:
    _mock_login()
    route = respx.post(REFRESH_URL).mock(return_value=httpx.Response(200, json=_refresh_payload()))

    with ArvanCloud() as client:
        previous = client.auth.login(TEST_EMAIL, TEST_PASSWORD)
        refreshed = client.auth.refresh()

        assert client.auth.tokens is refreshed

    request = route.calls[0].request
    assert request.method == "POST"
    assert request.headers["Authorization"] == f"Bearer {OLD_ACCESS_TOKEN}.{DEFAULT_ACCOUNT}"
    assert request.headers["Content-Type"] == "application/json"
    assert request.read() == b'{"refreshToken":"old-refresh-secret"}'
    assert refreshed.access_token == NEW_ACCESS_TOKEN
    assert refreshed.refresh_token == NEW_REFRESH_TOKEN
    assert refreshed.expires_at > previous.expires_at
    assert refreshed.default_account == previous.default_account
    assert refreshed.flow == previous.flow
    assert refreshed.next == previous.next


@respx.mock
@pytest.mark.asyncio
async def test_async_refresh_sends_expected_request_and_preserves_account_state() -> None:
    _mock_login()
    route = respx.post(REFRESH_URL).mock(return_value=httpx.Response(200, json=_refresh_payload()))

    async with AsyncArvanCloud() as client:
        previous = await client.auth.login(TEST_EMAIL, TEST_PASSWORD)
        refreshed = await client.auth.refresh()

        assert client.auth.tokens is refreshed

    request = route.calls[0].request
    assert request.headers["Authorization"] == f"Bearer {OLD_ACCESS_TOKEN}.{DEFAULT_ACCOUNT}"
    assert request.read() == b'{"refreshToken":"old-refresh-secret"}'
    assert refreshed.default_account == previous.default_account
    assert refreshed.flow == previous.flow
    assert refreshed.next == previous.next


def test_refresh_requires_an_in_memory_session() -> None:
    with ArvanCloud() as client, pytest.raises(AuthenticationRequiredError):
        client.auth.refresh()


@respx.mock
def test_refreshed_tokens_save_with_the_existing_session_schema(tmp_path) -> None:
    _mock_login()
    respx.post(REFRESH_URL).mock(return_value=httpx.Response(200, json=_refresh_payload()))
    session_path = tmp_path / "session.json"

    with ArvanCloud() as client:
        client.auth.login(TEST_EMAIL, TEST_PASSWORD)
        client.auth.refresh()
        client.auth.save_session(session_path)

    stored = json.loads(session_path.read_text(encoding="utf-8"))
    assert stored["schemaVersion"] == 1
    assert stored["data"]["accessToken"] == NEW_ACCESS_TOKEN
    assert stored["data"]["refreshToken"] == NEW_REFRESH_TOKEN
    assert stored["data"]["defaultAccount"] == DEFAULT_ACCOUNT
    serialized = session_path.read_text(encoding="utf-8")
    assert OLD_ACCESS_TOKEN not in serialized
    assert OLD_REFRESH_TOKEN not in serialized


@respx.mock
@pytest.mark.parametrize("status_code", [401, 403])
def test_rejected_refresh_keeps_existing_tokens_without_leaking_secrets(
    status_code: int,
) -> None:
    _mock_login()
    respx.post(REFRESH_URL).mock(return_value=httpx.Response(status_code))

    with ArvanCloud() as client:
        previous = client.auth.login(TEST_EMAIL, TEST_PASSWORD)
        with pytest.raises(AuthenticationError) as captured:
            client.auth.refresh()

        assert client.auth.tokens is previous

    message = str(captured.value)
    assert OLD_ACCESS_TOKEN not in message
    assert OLD_REFRESH_TOKEN not in message


@respx.mock
def test_malformed_refresh_keeps_existing_tokens() -> None:
    _mock_login()
    respx.post(REFRESH_URL).mock(return_value=httpx.Response(200, json={"data": {}}))

    with ArvanCloud() as client:
        previous = client.auth.login(TEST_EMAIL, TEST_PASSWORD)
        with pytest.raises(InvalidResponseError):
            client.auth.refresh()

        assert client.auth.tokens is previous


@respx.mock
def test_refresh_network_failure_keeps_existing_tokens_without_leaking_secrets() -> None:
    _mock_login()
    route = respx.post(REFRESH_URL).mock(side_effect=httpx.ConnectError("connection failed"))

    with ArvanCloud() as client:
        previous = client.auth.login(TEST_EMAIL, TEST_PASSWORD)
        with pytest.raises(NetworkError) as captured:
            client.auth.refresh()

        assert client.auth.tokens is previous

    assert route.call_count == 1
    message = str(captured.value)
    assert OLD_ACCESS_TOKEN not in message
    assert OLD_REFRESH_TOKEN not in message


@respx.mock
def test_refresh_post_is_not_retried() -> None:
    _mock_login()
    route = respx.post(REFRESH_URL).mock(return_value=httpx.Response(503))

    with ArvanCloud() as client:
        previous = client.auth.login(TEST_EMAIL, TEST_PASSWORD)
        with pytest.raises(APIError):
            client.auth.refresh()

        assert client.auth.tokens is previous

    assert route.call_count == 1
