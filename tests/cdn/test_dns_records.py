# tests/cdn/test_dns_records.py
"""Mocked tests for CDN DNS record listing."""

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
DNS_RECORDS_URL = "https://napi.arvancloud.ir/cdn/4.0/domains/snapp.ir/dns-records"
TEST_EMAIL = "person@example.com"
TEST_PASSWORD = "do-not-leak-this-password"


def _mock_login(login_payload: dict[str, object]) -> None:
    respx.post(LOGIN_URL).mock(return_value=httpx.Response(200, json=login_payload))


@respx.mock
def test_sync_list_dns_records_sends_expected_request_and_parses_fields(
    login_payload: dict[str, object],
    dns_records_payload: dict[str, object],
) -> None:
    _mock_login(login_payload)
    route = respx.get(DNS_RECORDS_URL, params={"page": "1", "per_page": "25"}).mock(
        return_value=httpx.Response(
            200,
            json={**dns_records_payload, "ignoredEnvelopeField": True},
        )
    )

    with ArvanCloud() as client:
        tokens = client.auth.login(TEST_EMAIL, TEST_PASSWORD)
        page = client.cdn.dns_records.list("snapp.ir", page=1, per_page=25)

        assert client.auth.tokens is tokens

    a_record = page.data[0]
    ns_record = page.data[1]
    assert a_record.id == UUID("fc14fa54-0ea9-40ec-aba8-f5426e988b57")
    assert a_record.type == "a"
    assert a_record.name == "home-1"
    assert a_record.value == [{"ip": "2.180.180.167", "port": None, "weight": 100, "country": ""}]
    assert a_record.ttl == 120
    assert a_record.cloud is False
    assert a_record.ip_filter_mode.count == "single"
    assert a_record.is_protected is False
    assert a_record.created_at == datetime(2026, 4, 4, 9, 54, 21, tzinfo=UTC)
    assert ns_record.value == {"host": "s.ns.arvancdn.ir."}
    assert ns_record.is_protected is True
    assert ns_record.updated_at == datetime(2026, 4, 2, 18, 26, 49, tzinfo=UTC)
    assert page.meta.total == 2

    request = route.calls[0].request
    assert request.method == "GET"
    assert request.url.path == "/cdn/4.0/domains/snapp.ir/dns-records"
    assert request.url.params["page"] == "1"
    assert request.url.params["per_page"] == "25"
    assert request.headers["Authorization"] == "Bearer access-secret"
    assert "origin" not in request.headers
    assert "referer" not in request.headers
    assert "sec-fetch-mode" not in request.headers


@respx.mock
@pytest.mark.asyncio
async def test_async_list_dns_records_sends_expected_request(
    login_payload: dict[str, object],
    dns_records_payload: dict[str, object],
) -> None:
    _mock_login(login_payload)
    route = respx.get(DNS_RECORDS_URL, params={"page": "2", "per_page": "50"}).mock(
        return_value=httpx.Response(200, json=dns_records_payload)
    )

    async with AsyncArvanCloud() as client:
        await client.auth.login(TEST_EMAIL, TEST_PASSWORD)
        page = await client.cdn.dns_records.list("snapp.ir", page=2, per_page=50)

    assert page.data[0].name == "home-1"
    request = route.calls[0].request
    assert request.headers["Authorization"] == "Bearer access-secret"
    assert request.url.params["page"] == "2"
    assert request.url.params["per_page"] == "50"


def test_list_dns_records_requires_login() -> None:
    with ArvanCloud() as client, pytest.raises(AuthenticationRequiredError):
        client.cdn.dns_records.list("snapp.ir")


@pytest.mark.parametrize(
    ("domain", "message"),
    [
        (" ", "domain"),
        ("snapp.ir/bad", "domain"),
    ],
)
def test_list_dns_records_rejects_invalid_domain(domain: str, message: str) -> None:
    with ArvanCloud() as client, pytest.raises(ValueError, match=message):
        client.cdn.dns_records.list(domain)


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"page": 0}, "page"),
        ({"per_page": 0}, "per_page"),
    ],
)
def test_list_dns_records_rejects_invalid_pagination(
    kwargs: dict[str, int],
    message: str,
) -> None:
    with ArvanCloud() as client, pytest.raises(ValueError, match=message):
        client.cdn.dns_records.list("snapp.ir", **kwargs)


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
def test_list_dns_records_maps_api_errors_without_leaking_secrets(
    status_code: int,
    exception_type: type[APIError],
    login_payload: dict[str, object],
) -> None:
    _mock_login(login_payload)
    respx.get(DNS_RECORDS_URL, params={"page": "1", "per_page": "25"}).mock(
        return_value=httpx.Response(
            status_code,
            headers={"X-Request-Id": "request-789"},
            json={
                "message": f"rejected {TEST_PASSWORD}",
                "token": "server-secret-token",
            },
        )
    )

    with ArvanCloud() as client, pytest.raises(exception_type) as captured:
        client.auth.login(TEST_EMAIL, TEST_PASSWORD)
        client.cdn.dns_records.list("snapp.ir")

    error = captured.value
    assert error.status_code == status_code
    assert error.request_id == "request-789"
    assert TEST_PASSWORD not in str(error)
    assert "access-secret" not in str(error)
    assert "refresh-secret" not in str(error)
    assert "server-secret-token" not in str(error)


@respx.mock
def test_list_dns_records_maps_timeout_without_leaking_token(
    login_payload: dict[str, object],
) -> None:
    _mock_login(login_payload)
    respx.get(DNS_RECORDS_URL, params={"page": "1", "per_page": "25"}).mock(
        side_effect=httpx.ReadTimeout("transport timed out")
    )

    with ArvanCloud() as client, pytest.raises(ArvanCloudTimeoutError) as captured:
        client.auth.login(TEST_EMAIL, TEST_PASSWORD)
        client.cdn.dns_records.list("snapp.ir")

    assert TEST_PASSWORD not in str(captured.value)
    assert "access-secret" not in str(captured.value)


@respx.mock
def test_list_dns_records_maps_network_failure_without_leaking_token(
    login_payload: dict[str, object],
) -> None:
    _mock_login(login_payload)
    respx.get(DNS_RECORDS_URL, params={"page": "1", "per_page": "25"}).mock(
        side_effect=httpx.ConnectError("connection failed")
    )

    with ArvanCloud() as client, pytest.raises(NetworkError) as captured:
        client.auth.login(TEST_EMAIL, TEST_PASSWORD)
        client.cdn.dns_records.list("snapp.ir")

    assert TEST_PASSWORD not in str(captured.value)
    assert "access-secret" not in str(captured.value)


@respx.mock
def test_list_dns_records_rejects_malformed_json(login_payload: dict[str, object]) -> None:
    _mock_login(login_payload)
    respx.get(DNS_RECORDS_URL, params={"page": "1", "per_page": "25"}).mock(
        return_value=httpx.Response(
            200,
            headers={"Content-Type": "application/json"},
            content=b"{",
        )
    )

    with ArvanCloud() as client, pytest.raises(InvalidResponseError, match="invalid JSON"):
        client.auth.login(TEST_EMAIL, TEST_PASSWORD)
        client.cdn.dns_records.list("snapp.ir")


@respx.mock
def test_list_dns_records_rejects_missing_required_response_fields(
    login_payload: dict[str, object],
) -> None:
    _mock_login(login_payload)
    respx.get(DNS_RECORDS_URL, params={"page": "1", "per_page": "25"}).mock(
        return_value=httpx.Response(200, json={"data": []})
    )

    with ArvanCloud() as client, pytest.raises(InvalidResponseError, match="expected contract"):
        client.auth.login(TEST_EMAIL, TEST_PASSWORD)
        client.cdn.dns_records.list("snapp.ir")


@respx.mock
def test_list_dns_records_ignores_unknown_response_fields(
    login_payload: dict[str, object],
    dns_records_payload: dict[str, object],
) -> None:
    payload = dict(dns_records_payload)
    records = list(payload["data"])
    first_record = dict(records[0])
    first_record["futureField"] = {"can": "be ignored"}
    payload["data"] = [first_record, *records[1:]]
    _mock_login(login_payload)
    respx.get(DNS_RECORDS_URL, params={"page": "1", "per_page": "25"}).mock(
        return_value=httpx.Response(200, json=payload)
    )

    with ArvanCloud() as client:
        client.auth.login(TEST_EMAIL, TEST_PASSWORD)
        page = client.cdn.dns_records.list("snapp.ir")

    assert page.data[0].name == "home-1"
