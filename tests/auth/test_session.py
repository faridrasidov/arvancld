# tests/auth/test_session.py
"""Tests for explicit JSON session persistence."""

from __future__ import annotations

import json
import os
import stat
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest
import respx

from arvancld import (
    ArvanCloud,
    AsyncArvanCloud,
    AuthenticationRequiredError,
    InvalidSessionError,
    SessionExpiredError,
)

LOGIN_URL = "https://dejban.arvancloud.ir/v1/auth/login"
DOMAINS_URL = "https://napi.arvancloud.ir/cdn/4.0/domains"
TEST_EMAIL = "person@example.com"
TEST_PASSWORD = "do-not-leak-this-password"
ACCESS_TOKEN = "access-secret"
REFRESH_TOKEN = "refresh-secret"
DEFAULT_ACCOUNT = "af999c67-2a12-517c-b52b-8bb5e2b59bad"


def _session_payload(
    login_payload: dict[str, object],
    *,
    expires_at: str | None = None,
) -> dict[str, object]:
    payload = dict(login_payload)
    data = dict(payload["data"])
    if expires_at is None:
        expires_at = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
    data["expiresAt"] = expires_at
    return {"schemaVersion": 1, "data": data}


def _write_session(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


@respx.mock
def test_save_session_writes_expected_schema_without_password(
    tmp_path: Path,
    login_payload: dict[str, object],
) -> None:
    session_path = tmp_path / ".arvancld-session.json"
    respx.post(LOGIN_URL).mock(return_value=httpx.Response(200, json=login_payload))

    with ArvanCloud() as client:
        client.auth.login(TEST_EMAIL, TEST_PASSWORD)
        client.auth.save_session(session_path)

    stored = json.loads(session_path.read_text(encoding="utf-8"))
    assert stored == {"schemaVersion": 1, "data": login_payload["data"]}
    assert TEST_PASSWORD not in session_path.read_text(encoding="utf-8")

    if os.name != "nt":
        mode = stat.S_IMODE(session_path.stat().st_mode)
        assert mode & 0o077 == 0


def test_save_session_requires_login(tmp_path: Path) -> None:
    session_path = tmp_path / ".arvancld-session.json"

    with ArvanCloud() as client, pytest.raises(AuthenticationRequiredError) as captured:
        client.auth.save_session(session_path)

    assert ACCESS_TOKEN not in str(captured.value)
    assert REFRESH_TOKEN not in str(captured.value)


@respx.mock
def test_load_session_restores_tokens_and_cdn_uses_account_scoped_bearer(
    tmp_path: Path,
    login_payload: dict[str, object],
    cdn_domain_payload: dict[str, object],
) -> None:
    session_path = tmp_path / ".arvancld-session.json"
    _write_session(session_path, _session_payload(login_payload))
    route = respx.get(DOMAINS_URL, params={"page": "1", "perPage": "5"}).mock(
        return_value=httpx.Response(200, json=cdn_domain_payload)
    )

    with ArvanCloud() as client:
        tokens = client.auth.load_session(session_path)
        page = client.cdn.domains.list()

        assert client.auth.tokens is tokens

    assert page.data[0].domain == "snapp.ir"
    request = route.calls[0].request
    assert request.method == "GET"
    assert request.headers["Authorization"] == f"Bearer {ACCESS_TOKEN}.{DEFAULT_ACCOUNT}"
    assert not any(call.request.url == LOGIN_URL for call in respx.calls)


@respx.mock
@pytest.mark.asyncio
async def test_async_client_can_use_loaded_session_without_login(
    tmp_path: Path,
    login_payload: dict[str, object],
    cdn_domain_payload: dict[str, object],
) -> None:
    session_path = tmp_path / ".arvancld-session.json"
    _write_session(session_path, _session_payload(login_payload))
    route = respx.get(DOMAINS_URL, params={"page": "1", "perPage": "5"}).mock(
        return_value=httpx.Response(200, json=cdn_domain_payload)
    )

    async with AsyncArvanCloud() as client:
        tokens = client.auth.load_session(session_path)
        page = await client.cdn.domains.list()

        assert client.auth.tokens is tokens

    assert page.data[0].domain == "snapp.ir"
    assert route.calls[0].request.headers["Authorization"] == (
        f"Bearer {ACCESS_TOKEN}.{DEFAULT_ACCOUNT}"
    )


def test_load_session_missing_file_raises_file_not_found(tmp_path: Path) -> None:
    with ArvanCloud() as client, pytest.raises(FileNotFoundError):
        client.auth.load_session(tmp_path / ".arvancld-session.json")


def test_load_session_rejects_malformed_json_without_leaking_secrets(tmp_path: Path) -> None:
    session_path = tmp_path / ".arvancld-session.json"
    session_path.write_text("{", encoding="utf-8")

    with ArvanCloud() as client, pytest.raises(InvalidSessionError) as captured:
        client.auth.load_session(session_path)

    assert ACCESS_TOKEN not in str(captured.value)
    assert REFRESH_TOKEN not in str(captured.value)
    assert TEST_PASSWORD not in str(captured.value)


def test_load_session_rejects_unsupported_schema_version(
    tmp_path: Path,
    login_payload: dict[str, object],
) -> None:
    session_path = tmp_path / ".arvancld-session.json"
    payload = _session_payload(login_payload)
    payload["schemaVersion"] = 2
    _write_session(session_path, payload)

    with ArvanCloud() as client, pytest.raises(InvalidSessionError) as captured:
        client.auth.load_session(session_path)

    assert ACCESS_TOKEN not in str(captured.value)
    assert REFRESH_TOKEN not in str(captured.value)


def test_load_session_rejects_missing_required_fields(
    tmp_path: Path,
    login_payload: dict[str, object],
) -> None:
    session_path = tmp_path / ".arvancld-session.json"
    payload = _session_payload(login_payload)
    data = dict(payload["data"])
    del data["refreshToken"]
    payload["data"] = data
    _write_session(session_path, payload)

    with ArvanCloud() as client, pytest.raises(InvalidSessionError) as captured:
        client.auth.load_session(session_path)

    assert ACCESS_TOKEN not in str(captured.value)
    assert REFRESH_TOKEN not in str(captured.value)


def test_load_session_rejects_naive_expiry(
    tmp_path: Path,
    login_payload: dict[str, object],
) -> None:
    session_path = tmp_path / ".arvancld-session.json"
    _write_session(session_path, _session_payload(login_payload, expires_at="2026-07-25T04:07:52"))

    with ArvanCloud() as client, pytest.raises(InvalidSessionError) as captured:
        client.auth.load_session(session_path)

    assert ACCESS_TOKEN not in str(captured.value)
    assert REFRESH_TOKEN not in str(captured.value)


def test_load_session_rejects_expired_session_without_setting_tokens(
    tmp_path: Path,
    login_payload: dict[str, object],
) -> None:
    session_path = tmp_path / ".arvancld-session.json"
    expired = (datetime.now(UTC) - timedelta(seconds=1)).isoformat()
    _write_session(session_path, _session_payload(login_payload, expires_at=expired))

    with ArvanCloud() as client, pytest.raises(SessionExpiredError) as captured:
        client.auth.load_session(session_path)

    assert client.auth.tokens is None
    assert ACCESS_TOKEN not in str(captured.value)
    assert REFRESH_TOKEN not in str(captured.value)


@respx.mock
def test_clear_session_removes_file_and_clears_memory(
    tmp_path: Path,
    login_payload: dict[str, object],
) -> None:
    session_path = tmp_path / ".arvancld-session.json"
    respx.post(LOGIN_URL).mock(return_value=httpx.Response(200, json=login_payload))

    with ArvanCloud() as client:
        client.auth.login(TEST_EMAIL, TEST_PASSWORD)
        client.auth.save_session(session_path)

        assert session_path.exists()
        assert client.auth.tokens is not None

        client.auth.clear_session(session_path)

        assert not session_path.exists()
        assert client.auth.tokens is None


def test_clear_session_missing_file_is_harmless(tmp_path: Path) -> None:
    with ArvanCloud() as client:
        client.auth.clear_session(tmp_path / ".arvancld-session.json")
