# tests/auth/test_totp.py
"""Mocked tests for synchronous and asynchronous TOTP login challenges."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest
import respx
from pydantic import ValidationError

from arvancld import (
    APIError,
    ArvanCloud,
    ArvanCloudTimeoutError,
    AsyncArvanCloud,
    AuthenticationError,
    AuthenticationRequiredError,
    InvalidResponseError,
    LoginResult,
    NetworkError,
    TOTPChallenge,
    TOTPRequiredError,
)

LOGIN_URL = "https://dejban.arvancloud.ir/v1/auth/login"
CHALLENGE_URL = "https://dejban.arvancloud.ir/v1/auth/challenge"
REFRESH_URL = "https://dejban.arvancloud.ir/v1/auth/refresh-token"
TEST_EMAIL = "mfa-user@example.com"
TEST_PASSWORD = "synthetic-password"
TOTP_CODE = "246810"
FLOW_TOKEN = "synthetic-flow-token"
DEFAULT_ACCOUNT = "af999c67-2a12-517c-b52b-8bb5e2b59bad"


def _challenge_payload(flow_token: str = FLOW_TOKEN) -> dict[str, object]:
    return {
        "data": {
            "flow": "ProvideCredential",
            "next": "ChallengeTOTPPossession",
            "flowToken": flow_token,
        },
        "meta": {},
    }


def _completed_payload(
    *,
    access_token: str = "synthetic-access-token",
    refresh_token: str = "synthetic-refresh-token",
) -> dict[str, object]:
    return {
        "data": {
            "accessToken": access_token,
            "refreshToken": refresh_token,
            "expiresAt": "2030-08-16T05:39:45Z",
            "defaultAccount": DEFAULT_ACCOUNT,
            "flow": "ProvideCredential",
            "next": "RedirectToPanel",
            "accounts": [
                {
                    "id": DEFAULT_ACCOUNT,
                    "name": "Synthetic account",
                    "mfaRequirementSatisfied": True,
                    "disabled": False,
                    "accountForces2FA": False,
                }
            ],
        }
    }


def _refresh_payload() -> dict[str, object]:
    return {
        "data": {
            "accessToken": "refreshed-access-token",
            "refreshToken": "refreshed-refresh-token",
            "expiresAt": "2030-08-17T05:39:45Z",
        }
    }


def _session_payload() -> dict[str, object]:
    payload = _completed_payload()
    data = dict(payload["data"])
    data["expiresAt"] = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
    return {"schemaVersion": 1, "data": data}


def _begin_sync_challenge(client: ArvanCloud) -> TOTPChallenge:
    with pytest.raises(TOTPRequiredError) as captured:
        client.auth.login(TEST_EMAIL, TEST_PASSWORD)

    challenge = client.auth.pending_totp
    assert challenge is not None
    assert isinstance(captured.value, AuthenticationRequiredError)
    assert TEST_PASSWORD not in str(captured.value)
    assert FLOW_TOKEN not in str(captured.value)
    return challenge


async def _begin_async_challenge(client: AsyncArvanCloud) -> TOTPChallenge:
    with pytest.raises(TOTPRequiredError) as captured:
        await client.auth.login(TEST_EMAIL, TEST_PASSWORD)

    challenge = client.auth.pending_totp
    assert challenge is not None
    assert isinstance(captured.value, AuthenticationRequiredError)
    assert TEST_PASSWORD not in str(captured.value)
    assert FLOW_TOKEN not in str(captured.value)
    return challenge


@respx.mock
def test_sync_totp_login_flow_sends_exact_request_and_clears_pending_state() -> None:
    login_route = respx.post(LOGIN_URL).mock(
        return_value=httpx.Response(201, json=_challenge_payload())
    )
    challenge_route = respx.post(CHALLENGE_URL).mock(
        return_value=httpx.Response(200, json=_completed_payload())
    )

    with ArvanCloud() as client:
        challenge = _begin_sync_challenge(client)

        assert client.auth.tokens is None
        assert challenge.flow == "ProvideCredential"
        assert challenge.next == "ChallengeTOTPPossession"
        assert challenge.flow_token == FLOW_TOKEN
        assert FLOW_TOKEN not in repr(challenge)

        result = client.auth.submit_totp(f"  {TOTP_CODE}  ")

        assert isinstance(result, LoginResult)
        assert client.auth.tokens is result
        assert client.auth.pending_totp is None

    assert json.loads(login_route.calls[0].request.content) == {
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD,
    }
    request = challenge_route.calls[0].request
    assert request.method == "POST"
    assert json.loads(request.content) == {
        "code": TOTP_CODE,
        "flow": "ChallengeTOTPPossession",
        "flowToken": FLOW_TOKEN,
    }
    assert request.headers["Accept"] == "application/json"
    assert request.headers["Content-Type"] == "application/json"
    assert request.headers["User-Agent"] == "arvancld/0.1.0"
    assert request.headers["X-Redirect-Uri"] == "https://panel.arvancloud.ir/"
    browser_headers = {
        "dnt",
        "origin",
        "referer",
        "sec-fetch-dest",
        "sec-fetch-mode",
        "sec-fetch-site",
        "x-content-type-options",
        "x-frame-options",
    }
    assert browser_headers.isdisjoint(request.headers)


@respx.mock
@pytest.mark.asyncio
async def test_async_totp_login_flow_sends_exact_request_and_clears_pending_state() -> None:
    respx.post(LOGIN_URL).mock(return_value=httpx.Response(201, json=_challenge_payload()))
    challenge_route = respx.post(CHALLENGE_URL).mock(
        return_value=httpx.Response(200, json=_completed_payload())
    )

    async with AsyncArvanCloud(redirect_uri="https://example.test/after-login") as client:
        challenge = await _begin_async_challenge(client)
        result = await client.auth.submit_totp(TOTP_CODE)

        assert challenge.flow_token == FLOW_TOKEN
        assert isinstance(result, LoginResult)
        assert client.auth.tokens is result
        assert client.auth.pending_totp is None

    request = challenge_route.calls[0].request
    assert json.loads(request.content) == {
        "code": TOTP_CODE,
        "flow": "ChallengeTOTPPossession",
        "flowToken": FLOW_TOKEN,
    }
    assert request.headers["X-Redirect-Uri"] == "https://example.test/after-login"


@respx.mock
def test_ordinary_login_keeps_login_result_contract_and_has_no_pending_challenge() -> None:
    respx.post(LOGIN_URL).mock(return_value=httpx.Response(200, json=_completed_payload()))

    with ArvanCloud() as client:
        result = client.auth.login(TEST_EMAIL, TEST_PASSWORD)

        assert isinstance(result, LoginResult)
        assert client.auth.tokens is result
        assert client.auth.pending_totp is None


@respx.mock
def test_totp_challenge_is_replaced_by_a_later_challenge() -> None:
    route = respx.post(LOGIN_URL).mock(
        side_effect=[
            httpx.Response(201, json=_challenge_payload("first-synthetic-flow-token")),
            httpx.Response(201, json=_challenge_payload("second-synthetic-flow-token")),
        ]
    )

    with ArvanCloud() as client:
        first = _begin_sync_challenge(client)
        second = _begin_sync_challenge(client)

        assert first.flow_token == "first-synthetic-flow-token"
        assert second.flow_token == "second-synthetic-flow-token"
        assert client.auth.pending_totp is second

    assert route.call_count == 2


@respx.mock
def test_starting_a_new_failed_login_clears_a_stale_challenge() -> None:
    route = respx.post(LOGIN_URL).mock(
        side_effect=[
            httpx.Response(201, json=_challenge_payload()),
            httpx.ConnectError("synthetic connection failure"),
        ]
    )

    with ArvanCloud() as client:
        _begin_sync_challenge(client)

        with pytest.raises(NetworkError):
            client.auth.login(TEST_EMAIL, TEST_PASSWORD)

        assert client.auth.pending_totp is None

    assert route.call_count == 2


@respx.mock
def test_existing_tokens_remain_active_until_totp_succeeds() -> None:
    login_route = respx.post(LOGIN_URL).mock(
        side_effect=[
            httpx.Response(
                200,
                json=_completed_payload(
                    access_token="old-synthetic-access-token",
                    refresh_token="old-synthetic-refresh-token",
                ),
            ),
            httpx.Response(201, json=_challenge_payload()),
        ]
    )
    respx.post(CHALLENGE_URL).mock(
        return_value=httpx.Response(
            200,
            json=_completed_payload(
                access_token="new-synthetic-access-token",
                refresh_token="new-synthetic-refresh-token",
            ),
        )
    )

    with ArvanCloud() as client:
        previous = client.auth.login(TEST_EMAIL, TEST_PASSWORD)
        _begin_sync_challenge(client)

        assert client.auth.tokens is previous

        current = client.auth.submit_totp(TOTP_CODE)

        assert client.auth.tokens is current
        assert current.access_token == "new-synthetic-access-token"
        assert client.auth.pending_totp is None

    assert login_route.call_count == 2


@pytest.mark.parametrize(
    "code",
    [
        "",
        "   ",
        "12345",
        "1234567",
        "12a456",
        "\uff11\uff12\uff13\uff14\uff15\uff16",
        "١٢٣٤٥٦",
        246810,
    ],
)
@respx.mock
def test_submit_totp_rejects_invalid_codes_before_request(code: object) -> None:
    respx.post(LOGIN_URL).mock(return_value=httpx.Response(201, json=_challenge_payload()))
    challenge_route = respx.post(CHALLENGE_URL).mock(
        return_value=httpx.Response(200, json=_completed_payload())
    )

    with ArvanCloud() as client:
        challenge = _begin_sync_challenge(client)

        with pytest.raises(ValueError, match="six ASCII digits"):
            client.auth.submit_totp(code)  # type: ignore[arg-type]

        assert client.auth.pending_totp is challenge

    assert challenge_route.call_count == 0


def test_submit_totp_requires_a_pending_challenge() -> None:
    with ArvanCloud() as client, pytest.raises(AuthenticationRequiredError):
        client.auth.submit_totp(TOTP_CODE)


@pytest.mark.parametrize(
    ("status_code", "exception_type"),
    [
        (400, APIError),
        (401, AuthenticationError),
        (403, AuthenticationError),
        (500, APIError),
        (503, APIError),
    ],
)
@respx.mock
def test_totp_api_errors_preserve_pending_state_and_do_not_retry(
    status_code: int,
    exception_type: type[APIError],
) -> None:
    respx.post(LOGIN_URL).mock(return_value=httpx.Response(201, json=_challenge_payload()))
    route = respx.post(CHALLENGE_URL).mock(
        return_value=httpx.Response(
            status_code,
            headers={"X-Request-Id": "synthetic-request-id"},
            json={"message": f"rejected {TOTP_CODE} {FLOW_TOKEN}"},
        )
    )

    with ArvanCloud() as client:
        challenge = _begin_sync_challenge(client)

        with pytest.raises(exception_type) as captured:
            client.auth.submit_totp(TOTP_CODE)

        assert client.auth.pending_totp is challenge
        assert client.auth.tokens is None

    assert route.call_count == 1
    assert TOTP_CODE not in str(captured.value)
    assert FLOW_TOKEN not in str(captured.value)


@pytest.mark.parametrize(
    ("failure", "exception_type"),
    [
        (httpx.ReadTimeout("synthetic timeout"), ArvanCloudTimeoutError),
        (httpx.ConnectError("synthetic connection failure"), NetworkError),
    ],
)
@respx.mock
def test_totp_transport_errors_preserve_pending_state_without_leaking_secrets(
    failure: httpx.RequestError,
    exception_type: type[NetworkError],
) -> None:
    respx.post(LOGIN_URL).mock(return_value=httpx.Response(201, json=_challenge_payload()))
    route = respx.post(CHALLENGE_URL).mock(side_effect=failure)

    with ArvanCloud() as client:
        challenge = _begin_sync_challenge(client)

        with pytest.raises(exception_type) as captured:
            client.auth.submit_totp(TOTP_CODE)

        assert client.auth.pending_totp is challenge

    assert route.call_count == 1
    assert TOTP_CODE not in str(captured.value)
    assert FLOW_TOKEN not in str(captured.value)


@pytest.mark.parametrize(
    ("response", "message"),
    [
        (
            httpx.Response(
                200,
                headers={"Content-Type": "application/json"},
                content=b"{",
            ),
            "invalid JSON",
        ),
        (httpx.Response(200, json={"data": {}}), "expected contract"),
    ],
)
@respx.mock
def test_malformed_totp_response_preserves_pending_state(
    response: httpx.Response,
    message: str,
) -> None:
    respx.post(LOGIN_URL).mock(return_value=httpx.Response(201, json=_challenge_payload()))
    respx.post(CHALLENGE_URL).mock(return_value=response)

    with ArvanCloud() as client:
        challenge = _begin_sync_challenge(client)

        with pytest.raises(InvalidResponseError, match=message) as captured:
            client.auth.submit_totp(TOTP_CODE)

        assert client.auth.pending_totp is challenge

    assert TOTP_CODE not in str(captured.value)
    assert FLOW_TOKEN not in str(captured.value)


@pytest.mark.parametrize(
    "payload",
    [
        {
            "data": {
                "flow": "ProvideCredential",
                "next": "ChallengeTOTPPossession",
            }
        },
        {
            "data": {
                "flow": "ProvideCredential",
                "next": "UnknownFutureChallenge",
                "flowToken": FLOW_TOKEN,
            }
        },
    ],
)
@respx.mock
def test_login_rejects_malformed_or_unknown_challenges(payload: dict[str, object]) -> None:
    respx.post(LOGIN_URL).mock(return_value=httpx.Response(201, json=payload))

    with ArvanCloud() as client:
        with pytest.raises(InvalidResponseError, match="expected contract") as captured:
            client.auth.login(TEST_EMAIL, TEST_PASSWORD)

        assert client.auth.pending_totp is None

    assert FLOW_TOKEN not in str(captured.value)


@respx.mock
def test_successful_refresh_clears_pending_totp_and_preserves_active_tokens_on_challenge() -> None:
    respx.post(LOGIN_URL).mock(
        side_effect=[
            httpx.Response(200, json=_completed_payload()),
            httpx.Response(201, json=_challenge_payload()),
        ]
    )
    respx.post(REFRESH_URL).mock(return_value=httpx.Response(200, json=_refresh_payload()))

    with ArvanCloud() as client:
        previous = client.auth.login(TEST_EMAIL, TEST_PASSWORD)
        _begin_sync_challenge(client)

        assert client.auth.tokens is previous
        assert client.auth.pending_totp is not None

        refreshed = client.auth.refresh()

        assert client.auth.tokens is refreshed
        assert client.auth.pending_totp is None


@respx.mock
def test_session_save_excludes_challenge_and_successful_load_and_clear_reset_it(
    tmp_path: Path,
) -> None:
    session_path = tmp_path / "session.json"
    session_path.write_text(json.dumps(_session_payload()), encoding="utf-8")
    respx.post(LOGIN_URL).mock(
        side_effect=[
            httpx.Response(201, json=_challenge_payload()),
            httpx.Response(201, json=_challenge_payload("replacement-synthetic-token")),
        ]
    )

    with ArvanCloud() as client:
        _begin_sync_challenge(client)
        loaded = client.auth.load_session(session_path)

        assert client.auth.tokens is loaded
        assert client.auth.pending_totp is None

        _begin_sync_challenge(client)
        client.auth.save_session(session_path)
        serialized = session_path.read_text(encoding="utf-8")
        assert "flowToken" not in serialized
        assert FLOW_TOKEN not in serialized

        client.auth.clear_session(session_path)

        assert client.auth.tokens is None
        assert client.auth.pending_totp is None
        assert not session_path.exists()


@respx.mock
@pytest.mark.asyncio
async def test_async_session_load_and_clear_reset_pending_totp(tmp_path: Path) -> None:
    session_path = tmp_path / "session.json"
    session_path.write_text(json.dumps(_session_payload()), encoding="utf-8")
    respx.post(LOGIN_URL).mock(
        side_effect=[
            httpx.Response(201, json=_challenge_payload()),
            httpx.Response(201, json=_challenge_payload("replacement-synthetic-token")),
        ]
    )

    async with AsyncArvanCloud() as client:
        await _begin_async_challenge(client)
        await client.auth.aload_session(session_path)
        assert client.auth.pending_totp is None

        await _begin_async_challenge(client)
        await client.auth.aclear_session(session_path)
        assert client.auth.tokens is None
        assert client.auth.pending_totp is None


def test_totp_public_types_are_immutable_and_pending_property_is_read_only() -> None:
    challenge = TOTPChallenge(
        flow="ProvideCredential",
        next="ChallengeTOTPPossession",
        flowToken=FLOW_TOKEN,
    )
    assert issubclass(TOTPRequiredError, AuthenticationRequiredError)
    assert FLOW_TOKEN not in repr(challenge)

    with pytest.raises(ValidationError):
        challenge.flow = "changed"  # type: ignore[misc]

    with ArvanCloud() as client, pytest.raises(AttributeError):
        client.auth.pending_totp = challenge  # type: ignore[misc]
