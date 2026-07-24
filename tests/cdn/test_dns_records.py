# tests/cdn/test_dns_records.py
"""Mocked tests for CDN DNS record listing."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from uuid import UUID

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
    DNSRecordCreate,
    DNSRecordIPValue,
    DNSRecordUpdate,
    InvalidResponseError,
    IPFilterMode,
    NetworkError,
)

LOGIN_URL = "https://dejban.arvancloud.ir/v1/auth/login"
DNS_RECORDS_URL = "https://napi.arvancloud.ir/cdn/4.0/domains/snapp.ir/dns-records"
RECORD_ID = UUID("1256bf2b-e19f-448c-8fa2-8a6e83a6acc1")
DNS_RECORD_CLOUD_URL = f"{DNS_RECORDS_URL}/{RECORD_ID}/cloud"
DNS_RECORD_DELETE_URL = f"{DNS_RECORDS_URL}/{RECORD_ID}"
DNS_RECORD_UPDATE_URL = f"{DNS_RECORDS_URL}/{RECORD_ID}/"
TEST_EMAIL = "person@example.com"
TEST_PASSWORD = "do-not-leak-this-password"


def _mock_login(login_payload: dict[str, object]) -> None:
    respx.post(LOGIN_URL).mock(return_value=httpx.Response(200, json=login_payload))


def _create_record() -> DNSRecordCreate:
    return DNSRecordCreate(
        type="A",
        name="sss",
        cloud=True,
        value=[
            DNSRecordIPValue(
                ip="85.5.5.5",
                port=None,
                weight=None,
                country="",
            )
        ],
        ttl=120,
        upstream_https="default",
        ip_filter_mode=IPFilterMode(
            count="single",
            geo_filter="none",
            order="none",
        ),
    )


def _update_record() -> DNSRecordUpdate:
    return DNSRecordUpdate(
        id=RECORD_ID,
        type="A",
        name="sss",
        cloud=True,
        value=[
            DNSRecordIPValue(
                ip="85.5.5.6",
                port=None,
                weight=100,
                country="",
            )
        ],
        ttl=120,
        upstream_https="default",
        ip_filter_mode=IPFilterMode(
            count="single",
            order="none",
            geo_filter="none",
        ),
    )


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
    assert request.headers["Authorization"] == (
        "Bearer access-secret.af999c67-2a12-517c-b52b-8bb5e2b59bad"
    )
    _assert_no_browser_headers(request)


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
    assert request.headers["Authorization"] == (
        "Bearer access-secret.af999c67-2a12-517c-b52b-8bb5e2b59bad"
    )
    assert request.url.params["page"] == "2"
    assert request.url.params["per_page"] == "50"


@respx.mock
def test_sync_create_dns_record_sends_expected_request_and_parses_fields(
    login_payload: dict[str, object],
    dns_record_create_response_payload: dict[str, object],
) -> None:
    _mock_login(login_payload)
    route = respx.post(DNS_RECORDS_URL).mock(
        return_value=httpx.Response(
            201,
            json={**dns_record_create_response_payload, "ignoredEnvelopeField": True},
        )
    )

    with ArvanCloud() as client:
        tokens = client.auth.login(TEST_EMAIL, TEST_PASSWORD)
        record = client.cdn.dns_records.create("snapp.ir", _create_record())

        assert client.auth.tokens is tokens

    assert record.id == UUID("1256bf2b-e19f-448c-8fa2-8a6e83a6acc1")
    assert record.type == "a"
    assert record.name == "sss"
    assert record.value == [{"ip": "85.5.5.5", "port": None, "weight": 100, "country": ""}]
    assert record.ttl == 120
    assert record.cloud is True
    assert record.upstream_https == "default"
    assert record.ip_filter_mode.count == "single"
    assert record.is_protected is False
    assert record.created_at == datetime(2026, 7, 24, 17, 35, 8, tzinfo=UTC)

    request = route.calls[0].request
    assert request.method == "POST"
    assert request.url.path == "/cdn/4.0/domains/snapp.ir/dns-records"
    assert request.headers["Accept"] == "application/json"
    assert request.headers["Content-Type"] == "application/json"
    assert request.headers["User-Agent"] == "arvancld/0.1.0"
    assert request.headers["Authorization"] == (
        "Bearer access-secret.af999c67-2a12-517c-b52b-8bb5e2b59bad"
    )
    assert json.loads(request.content) == {
        "type": "A",
        "name": "sss",
        "cloud": True,
        "value": [{"ip": "85.5.5.5", "port": None, "weight": None, "country": ""}],
        "ttl": 120,
        "upstream_https": "default",
        "ip_filter_mode": {"count": "single", "order": "none", "geo_filter": "none"},
    }
    _assert_no_browser_headers(request)


@respx.mock
@pytest.mark.asyncio
async def test_async_create_dns_record_sends_expected_request(
    login_payload: dict[str, object],
    dns_record_create_response_payload: dict[str, object],
) -> None:
    _mock_login(login_payload)
    route = respx.post(DNS_RECORDS_URL).mock(
        return_value=httpx.Response(201, json=dns_record_create_response_payload)
    )

    async with AsyncArvanCloud() as client:
        await client.auth.login(TEST_EMAIL, TEST_PASSWORD)
        record = await client.cdn.dns_records.create("snapp.ir", _create_record())

    assert record.type == "a"
    request = route.calls[0].request
    assert request.headers["Authorization"] == (
        "Bearer access-secret.af999c67-2a12-517c-b52b-8bb5e2b59bad"
    )
    assert request.url.path == "/cdn/4.0/domains/snapp.ir/dns-records"


@respx.mock
def test_sync_set_dns_record_cloud_sends_expected_request_and_parses_fields(
    login_payload: dict[str, object],
    dns_record_cloud_update_response_payload: dict[str, object],
) -> None:
    _mock_login(login_payload)
    route = respx.put(DNS_RECORD_CLOUD_URL).mock(
        return_value=httpx.Response(
            200,
            json={**dns_record_cloud_update_response_payload, "ignoredEnvelopeField": True},
        )
    )

    with ArvanCloud() as client:
        tokens = client.auth.login(TEST_EMAIL, TEST_PASSWORD)
        record = client.cdn.dns_records.set_cloud("snapp.ir", RECORD_ID, cloud=True)

        assert client.auth.tokens is tokens

    assert record.id == RECORD_ID
    assert record.type == "a"
    assert record.name == "sss"
    assert record.cloud is True
    assert record.value == [{"ip": "85.5.5.5", "port": None, "weight": 100, "country": ""}]
    assert record.updated_at == datetime(2026, 7, 24, 17, 40, 12, tzinfo=UTC)

    request = route.calls[0].request
    assert request.method == "PUT"
    assert request.url.path == f"/cdn/4.0/domains/snapp.ir/dns-records/{RECORD_ID}/cloud"
    assert request.headers["Accept"] == "application/json"
    assert request.headers["Content-Type"] == "application/json"
    assert request.headers["User-Agent"] == "arvancld/0.1.0"
    assert request.headers["Authorization"] == (
        "Bearer access-secret.af999c67-2a12-517c-b52b-8bb5e2b59bad"
    )
    assert json.loads(request.content) == {"cloud": True}
    _assert_no_browser_headers(request)


@respx.mock
@pytest.mark.asyncio
async def test_async_set_dns_record_cloud_can_turn_proxy_off(
    login_payload: dict[str, object],
    dns_record_cloud_update_response_payload: dict[str, object],
) -> None:
    _mock_login(login_payload)
    payload = dict(dns_record_cloud_update_response_payload)
    data = dict(payload["data"])
    data["cloud"] = False
    payload["data"] = data
    route = respx.put(DNS_RECORD_CLOUD_URL).mock(return_value=httpx.Response(200, json=payload))

    async with AsyncArvanCloud() as client:
        await client.auth.login(TEST_EMAIL, TEST_PASSWORD)
        record = await client.cdn.dns_records.set_cloud("snapp.ir", str(RECORD_ID), cloud=False)

    assert record.cloud is False
    request = route.calls[0].request
    assert request.headers["Authorization"] == (
        "Bearer access-secret.af999c67-2a12-517c-b52b-8bb5e2b59bad"
    )
    assert request.url.path == f"/cdn/4.0/domains/snapp.ir/dns-records/{RECORD_ID}/cloud"
    assert json.loads(request.content) == {"cloud": False}


@respx.mock
def test_sync_update_dns_record_sends_expected_request_and_parses_fields(
    login_payload: dict[str, object],
    dns_record_update_response_payload: dict[str, object],
) -> None:
    _mock_login(login_payload)
    route = respx.put(DNS_RECORD_UPDATE_URL).mock(
        return_value=httpx.Response(
            200,
            json={**dns_record_update_response_payload, "ignoredEnvelopeField": True},
        )
    )

    with ArvanCloud() as client:
        tokens = client.auth.login(TEST_EMAIL, TEST_PASSWORD)
        record = client.cdn.dns_records.update("snapp.ir", _update_record())

        assert client.auth.tokens is tokens

    assert record.id == RECORD_ID
    assert record.type == "a"
    assert record.name == "sss"
    assert record.cloud is True
    assert record.value == [{"ip": "85.5.5.6", "port": None, "weight": 100, "country": ""}]
    assert record.updated_at == datetime(2026, 7, 24, 17, 54, 53, tzinfo=UTC)

    request = route.calls[0].request
    assert request.method == "PUT"
    assert request.url.path == f"/cdn/4.0/domains/snapp.ir/dns-records/{RECORD_ID}/"
    assert request.headers["Accept"] == "application/json"
    assert request.headers["Content-Type"] == "application/json"
    assert request.headers["User-Agent"] == "arvancld/0.1.0"
    assert request.headers["Authorization"] == (
        "Bearer access-secret.af999c67-2a12-517c-b52b-8bb5e2b59bad"
    )
    assert json.loads(request.content) == {
        "type": "A",
        "name": "sss",
        "cloud": True,
        "value": [{"ip": "85.5.5.6", "port": None, "weight": 100, "country": ""}],
        "ttl": 120,
        "upstream_https": "default",
        "ip_filter_mode": {"count": "single", "order": "none", "geo_filter": "none"},
        "id": str(RECORD_ID),
    }
    _assert_no_browser_headers(request)


@respx.mock
@pytest.mark.asyncio
async def test_async_update_dns_record_sends_expected_request(
    login_payload: dict[str, object],
    dns_record_update_response_payload: dict[str, object],
) -> None:
    _mock_login(login_payload)
    route = respx.put(DNS_RECORD_UPDATE_URL).mock(
        return_value=httpx.Response(200, json=dns_record_update_response_payload)
    )

    async with AsyncArvanCloud() as client:
        await client.auth.login(TEST_EMAIL, TEST_PASSWORD)
        record = await client.cdn.dns_records.update("snapp.ir", _update_record())

    assert record.value == [{"ip": "85.5.5.6", "port": None, "weight": 100, "country": ""}]
    request = route.calls[0].request
    assert request.headers["Authorization"] == (
        "Bearer access-secret.af999c67-2a12-517c-b52b-8bb5e2b59bad"
    )
    assert request.url.path == f"/cdn/4.0/domains/snapp.ir/dns-records/{RECORD_ID}/"


@respx.mock
def test_sync_delete_dns_record_sends_expected_request_and_parses_result(
    login_payload: dict[str, object],
    dns_record_delete_response_payload: dict[str, object],
) -> None:
    _mock_login(login_payload)
    route = respx.delete(DNS_RECORD_DELETE_URL).mock(
        return_value=httpx.Response(
            200,
            json={**dns_record_delete_response_payload, "ignoredEnvelopeField": True},
        )
    )

    with ArvanCloud() as client:
        tokens = client.auth.login(TEST_EMAIL, TEST_PASSWORD)
        result = client.cdn.dns_records.delete("snapp.ir", RECORD_ID)

        assert client.auth.tokens is tokens

    assert result.data == []
    assert result.message == "DNS record deleted."

    request = route.calls[0].request
    assert request.method == "DELETE"
    assert request.url.path == f"/cdn/4.0/domains/snapp.ir/dns-records/{RECORD_ID}"
    assert request.content == b""
    assert "Content-Type" not in request.headers
    assert request.headers["Accept"] == "application/json"
    assert request.headers["User-Agent"] == "arvancld/0.1.0"
    assert request.headers["Authorization"] == (
        "Bearer access-secret.af999c67-2a12-517c-b52b-8bb5e2b59bad"
    )
    _assert_no_browser_headers(request)


@respx.mock
@pytest.mark.asyncio
async def test_async_delete_dns_record_sends_expected_request(
    login_payload: dict[str, object],
    dns_record_delete_response_payload: dict[str, object],
) -> None:
    _mock_login(login_payload)
    route = respx.delete(DNS_RECORD_DELETE_URL).mock(
        return_value=httpx.Response(200, json=dns_record_delete_response_payload)
    )

    async with AsyncArvanCloud() as client:
        await client.auth.login(TEST_EMAIL, TEST_PASSWORD)
        result = await client.cdn.dns_records.delete("snapp.ir", str(RECORD_ID))

    assert result.message == "DNS record deleted."
    request = route.calls[0].request
    assert request.headers["Authorization"] == (
        "Bearer access-secret.af999c67-2a12-517c-b52b-8bb5e2b59bad"
    )
    assert request.url.path == f"/cdn/4.0/domains/snapp.ir/dns-records/{RECORD_ID}"


def test_list_dns_records_requires_login() -> None:
    with ArvanCloud() as client, pytest.raises(AuthenticationRequiredError):
        client.cdn.dns_records.list("snapp.ir")


def test_create_dns_record_requires_login() -> None:
    with ArvanCloud() as client, pytest.raises(AuthenticationRequiredError):
        client.cdn.dns_records.create("snapp.ir", _create_record())


def test_set_dns_record_cloud_requires_login() -> None:
    with ArvanCloud() as client, pytest.raises(AuthenticationRequiredError):
        client.cdn.dns_records.set_cloud("snapp.ir", RECORD_ID, cloud=True)


def test_update_dns_record_requires_login() -> None:
    with ArvanCloud() as client, pytest.raises(AuthenticationRequiredError):
        client.cdn.dns_records.update("snapp.ir", _update_record())


def test_delete_dns_record_requires_login() -> None:
    with ArvanCloud() as client, pytest.raises(AuthenticationRequiredError):
        client.cdn.dns_records.delete("snapp.ir", RECORD_ID)


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


def test_create_dns_record_rejects_invalid_domain() -> None:
    with ArvanCloud() as client, pytest.raises(ValueError, match="domain"):
        client.cdn.dns_records.create("snapp.ir/bad", _create_record())


def test_set_dns_record_cloud_rejects_invalid_domain() -> None:
    with ArvanCloud() as client, pytest.raises(ValueError, match="domain"):
        client.cdn.dns_records.set_cloud("snapp.ir/bad", RECORD_ID, cloud=True)


def test_update_dns_record_rejects_invalid_domain() -> None:
    with ArvanCloud() as client, pytest.raises(ValueError, match="domain"):
        client.cdn.dns_records.update("snapp.ir/bad", _update_record())


def test_delete_dns_record_rejects_invalid_domain() -> None:
    with ArvanCloud() as client, pytest.raises(ValueError, match="domain"):
        client.cdn.dns_records.delete("snapp.ir/bad", RECORD_ID)


@pytest.mark.parametrize("record_id", [" ", "bad/id"])
def test_set_dns_record_cloud_rejects_invalid_record_id(record_id: str) -> None:
    with ArvanCloud() as client, pytest.raises(ValueError, match="record_id"):
        client.cdn.dns_records.set_cloud("snapp.ir", record_id, cloud=True)


@pytest.mark.parametrize("record_id", [" ", "bad/id"])
def test_delete_dns_record_rejects_invalid_record_id(record_id: str) -> None:
    with ArvanCloud() as client, pytest.raises(ValueError, match="record_id"):
        client.cdn.dns_records.delete("snapp.ir", record_id)


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
    "override",
    [
        {"type": " "},
        {"name": " "},
        {"ttl": 0},
        {"upstream_https": " "},
    ],
)
def test_create_dns_record_rejects_invalid_payload(override: dict[str, object]) -> None:
    payload = {
        "type": "A",
        "name": "sss",
        "cloud": True,
        "value": [{"ip": "85.5.5.5", "port": None, "weight": None, "country": ""}],
        "ttl": 120,
        "upstream_https": "default",
        "ip_filter_mode": {"count": "single", "geo_filter": "none", "order": "none"},
    }
    payload.update(override)

    with pytest.raises(ValidationError):
        DNSRecordCreate.model_validate(payload)


@pytest.mark.parametrize(
    "override",
    [
        {"id": "not-a-uuid"},
        {"type": " "},
        {"name": " "},
        {"ttl": 0},
        {"upstream_https": " "},
    ],
)
def test_update_dns_record_rejects_invalid_payload(override: dict[str, object]) -> None:
    payload = {
        "id": str(RECORD_ID),
        "type": "A",
        "name": "sss",
        "cloud": True,
        "value": [{"ip": "85.5.5.6", "port": None, "weight": 100, "country": ""}],
        "ttl": 120,
        "upstream_https": "default",
        "ip_filter_mode": {"count": "single", "geo_filter": "none", "order": "none"},
    }
    payload.update(override)

    with pytest.raises(ValidationError):
        DNSRecordUpdate.model_validate(payload)


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
def test_create_dns_record_maps_api_errors_without_leaking_secrets(
    status_code: int,
    exception_type: type[APIError],
    login_payload: dict[str, object],
) -> None:
    _mock_login(login_payload)
    respx.post(DNS_RECORDS_URL).mock(
        return_value=httpx.Response(
            status_code,
            headers={"X-Request-Id": "request-987"},
            json={
                "message": f"rejected {TEST_PASSWORD}",
                "token": "server-secret-token",
            },
        )
    )

    with ArvanCloud() as client, pytest.raises(exception_type) as captured:
        client.auth.login(TEST_EMAIL, TEST_PASSWORD)
        client.cdn.dns_records.create("snapp.ir", _create_record())

    error = captured.value
    assert error.status_code == status_code
    assert error.request_id == "request-987"
    assert TEST_PASSWORD not in str(error)
    assert "access-secret" not in str(error)
    assert "refresh-secret" not in str(error)
    assert "server-secret-token" not in str(error)


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
def test_set_dns_record_cloud_maps_api_errors_without_leaking_secrets(
    status_code: int,
    exception_type: type[APIError],
    login_payload: dict[str, object],
) -> None:
    _mock_login(login_payload)
    respx.put(DNS_RECORD_CLOUD_URL).mock(
        return_value=httpx.Response(
            status_code,
            headers={"X-Request-Id": "request-654"},
            json={
                "message": f"rejected {TEST_PASSWORD}",
                "token": "server-secret-token",
            },
        )
    )

    with ArvanCloud() as client, pytest.raises(exception_type) as captured:
        client.auth.login(TEST_EMAIL, TEST_PASSWORD)
        client.cdn.dns_records.set_cloud("snapp.ir", RECORD_ID, cloud=True)

    error = captured.value
    assert error.status_code == status_code
    assert error.request_id == "request-654"
    assert TEST_PASSWORD not in str(error)
    assert "access-secret" not in str(error)
    assert "refresh-secret" not in str(error)
    assert "server-secret-token" not in str(error)


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
def test_update_dns_record_maps_api_errors_without_leaking_secrets(
    status_code: int,
    exception_type: type[APIError],
    login_payload: dict[str, object],
) -> None:
    _mock_login(login_payload)
    respx.put(DNS_RECORD_UPDATE_URL).mock(
        return_value=httpx.Response(
            status_code,
            headers={"X-Request-Id": "request-321"},
            json={
                "message": f"rejected {TEST_PASSWORD}",
                "token": "server-secret-token",
            },
        )
    )

    with ArvanCloud() as client, pytest.raises(exception_type) as captured:
        client.auth.login(TEST_EMAIL, TEST_PASSWORD)
        client.cdn.dns_records.update("snapp.ir", _update_record())

    error = captured.value
    assert error.status_code == status_code
    assert error.request_id == "request-321"
    assert TEST_PASSWORD not in str(error)
    assert "access-secret" not in str(error)
    assert "refresh-secret" not in str(error)
    assert "server-secret-token" not in str(error)


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
def test_delete_dns_record_maps_api_errors_without_leaking_secrets(
    status_code: int,
    exception_type: type[APIError],
    login_payload: dict[str, object],
) -> None:
    _mock_login(login_payload)
    respx.delete(DNS_RECORD_DELETE_URL).mock(
        return_value=httpx.Response(
            status_code,
            headers={"X-Request-Id": "request-159"},
            json={
                "message": f"rejected {TEST_PASSWORD}",
                "token": "server-secret-token",
            },
        )
    )

    with ArvanCloud() as client, pytest.raises(exception_type) as captured:
        client.auth.login(TEST_EMAIL, TEST_PASSWORD)
        client.cdn.dns_records.delete("snapp.ir", RECORD_ID)

    error = captured.value
    assert error.status_code == status_code
    assert error.request_id == "request-159"
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
def test_create_dns_record_maps_timeout_without_leaking_token(
    login_payload: dict[str, object],
) -> None:
    _mock_login(login_payload)
    respx.post(DNS_RECORDS_URL).mock(side_effect=httpx.ReadTimeout("transport timed out"))

    with ArvanCloud() as client, pytest.raises(ArvanCloudTimeoutError) as captured:
        client.auth.login(TEST_EMAIL, TEST_PASSWORD)
        client.cdn.dns_records.create("snapp.ir", _create_record())

    assert TEST_PASSWORD not in str(captured.value)
    assert "access-secret" not in str(captured.value)


@respx.mock
def test_set_dns_record_cloud_maps_timeout_without_leaking_token(
    login_payload: dict[str, object],
) -> None:
    _mock_login(login_payload)
    respx.put(DNS_RECORD_CLOUD_URL).mock(side_effect=httpx.ReadTimeout("transport timed out"))

    with ArvanCloud() as client, pytest.raises(ArvanCloudTimeoutError) as captured:
        client.auth.login(TEST_EMAIL, TEST_PASSWORD)
        client.cdn.dns_records.set_cloud("snapp.ir", RECORD_ID, cloud=True)

    assert TEST_PASSWORD not in str(captured.value)
    assert "access-secret" not in str(captured.value)


@respx.mock
def test_update_dns_record_maps_timeout_without_leaking_token(
    login_payload: dict[str, object],
) -> None:
    _mock_login(login_payload)
    respx.put(DNS_RECORD_UPDATE_URL).mock(side_effect=httpx.ReadTimeout("transport timed out"))

    with ArvanCloud() as client, pytest.raises(ArvanCloudTimeoutError) as captured:
        client.auth.login(TEST_EMAIL, TEST_PASSWORD)
        client.cdn.dns_records.update("snapp.ir", _update_record())

    assert TEST_PASSWORD not in str(captured.value)
    assert "access-secret" not in str(captured.value)


@respx.mock
def test_delete_dns_record_maps_timeout_without_leaking_token(
    login_payload: dict[str, object],
) -> None:
    _mock_login(login_payload)
    respx.delete(DNS_RECORD_DELETE_URL).mock(side_effect=httpx.ReadTimeout("transport timed out"))

    with ArvanCloud() as client, pytest.raises(ArvanCloudTimeoutError) as captured:
        client.auth.login(TEST_EMAIL, TEST_PASSWORD)
        client.cdn.dns_records.delete("snapp.ir", RECORD_ID)

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
def test_create_dns_record_maps_network_failure_without_leaking_token(
    login_payload: dict[str, object],
) -> None:
    _mock_login(login_payload)
    respx.post(DNS_RECORDS_URL).mock(side_effect=httpx.ConnectError("connection failed"))

    with ArvanCloud() as client, pytest.raises(NetworkError) as captured:
        client.auth.login(TEST_EMAIL, TEST_PASSWORD)
        client.cdn.dns_records.create("snapp.ir", _create_record())

    assert TEST_PASSWORD not in str(captured.value)
    assert "access-secret" not in str(captured.value)


@respx.mock
def test_set_dns_record_cloud_maps_network_failure_without_leaking_token(
    login_payload: dict[str, object],
) -> None:
    _mock_login(login_payload)
    respx.put(DNS_RECORD_CLOUD_URL).mock(side_effect=httpx.ConnectError("connection failed"))

    with ArvanCloud() as client, pytest.raises(NetworkError) as captured:
        client.auth.login(TEST_EMAIL, TEST_PASSWORD)
        client.cdn.dns_records.set_cloud("snapp.ir", RECORD_ID, cloud=True)

    assert TEST_PASSWORD not in str(captured.value)
    assert "access-secret" not in str(captured.value)


@respx.mock
def test_update_dns_record_maps_network_failure_without_leaking_token(
    login_payload: dict[str, object],
) -> None:
    _mock_login(login_payload)
    respx.put(DNS_RECORD_UPDATE_URL).mock(side_effect=httpx.ConnectError("connection failed"))

    with ArvanCloud() as client, pytest.raises(NetworkError) as captured:
        client.auth.login(TEST_EMAIL, TEST_PASSWORD)
        client.cdn.dns_records.update("snapp.ir", _update_record())

    assert TEST_PASSWORD not in str(captured.value)
    assert "access-secret" not in str(captured.value)


@respx.mock
def test_delete_dns_record_maps_network_failure_without_leaking_token(
    login_payload: dict[str, object],
) -> None:
    _mock_login(login_payload)
    respx.delete(DNS_RECORD_DELETE_URL).mock(side_effect=httpx.ConnectError("connection failed"))

    with ArvanCloud() as client, pytest.raises(NetworkError) as captured:
        client.auth.login(TEST_EMAIL, TEST_PASSWORD)
        client.cdn.dns_records.delete("snapp.ir", RECORD_ID)

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
def test_create_dns_record_rejects_malformed_json(login_payload: dict[str, object]) -> None:
    _mock_login(login_payload)
    respx.post(DNS_RECORDS_URL).mock(
        return_value=httpx.Response(
            201,
            headers={"Content-Type": "application/json"},
            content=b"{",
        )
    )

    with ArvanCloud() as client, pytest.raises(InvalidResponseError, match="invalid JSON"):
        client.auth.login(TEST_EMAIL, TEST_PASSWORD)
        client.cdn.dns_records.create("snapp.ir", _create_record())


@respx.mock
def test_set_dns_record_cloud_rejects_malformed_json(login_payload: dict[str, object]) -> None:
    _mock_login(login_payload)
    respx.put(DNS_RECORD_CLOUD_URL).mock(
        return_value=httpx.Response(
            200,
            headers={"Content-Type": "application/json"},
            content=b"{",
        )
    )

    with ArvanCloud() as client, pytest.raises(InvalidResponseError, match="invalid JSON"):
        client.auth.login(TEST_EMAIL, TEST_PASSWORD)
        client.cdn.dns_records.set_cloud("snapp.ir", RECORD_ID, cloud=True)


@respx.mock
def test_update_dns_record_rejects_malformed_json(login_payload: dict[str, object]) -> None:
    _mock_login(login_payload)
    respx.put(DNS_RECORD_UPDATE_URL).mock(
        return_value=httpx.Response(
            200,
            headers={"Content-Type": "application/json"},
            content=b"{",
        )
    )

    with ArvanCloud() as client, pytest.raises(InvalidResponseError, match="invalid JSON"):
        client.auth.login(TEST_EMAIL, TEST_PASSWORD)
        client.cdn.dns_records.update("snapp.ir", _update_record())


@respx.mock
def test_delete_dns_record_rejects_malformed_json(login_payload: dict[str, object]) -> None:
    _mock_login(login_payload)
    respx.delete(DNS_RECORD_DELETE_URL).mock(
        return_value=httpx.Response(
            200,
            headers={"Content-Type": "application/json"},
            content=b"{",
        )
    )

    with ArvanCloud() as client, pytest.raises(InvalidResponseError, match="invalid JSON"):
        client.auth.login(TEST_EMAIL, TEST_PASSWORD)
        client.cdn.dns_records.delete("snapp.ir", RECORD_ID)


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
def test_create_dns_record_rejects_missing_required_response_fields(
    login_payload: dict[str, object],
) -> None:
    _mock_login(login_payload)
    respx.post(DNS_RECORDS_URL).mock(return_value=httpx.Response(201, json={"data": {}}))

    with ArvanCloud() as client, pytest.raises(InvalidResponseError, match="expected contract"):
        client.auth.login(TEST_EMAIL, TEST_PASSWORD)
        client.cdn.dns_records.create("snapp.ir", _create_record())


@respx.mock
def test_set_dns_record_cloud_rejects_missing_required_response_fields(
    login_payload: dict[str, object],
) -> None:
    _mock_login(login_payload)
    respx.put(DNS_RECORD_CLOUD_URL).mock(return_value=httpx.Response(200, json={"data": {}}))

    with ArvanCloud() as client, pytest.raises(InvalidResponseError, match="expected contract"):
        client.auth.login(TEST_EMAIL, TEST_PASSWORD)
        client.cdn.dns_records.set_cloud("snapp.ir", RECORD_ID, cloud=True)


@respx.mock
def test_update_dns_record_rejects_missing_required_response_fields(
    login_payload: dict[str, object],
) -> None:
    _mock_login(login_payload)
    respx.put(DNS_RECORD_UPDATE_URL).mock(return_value=httpx.Response(200, json={"data": {}}))

    with ArvanCloud() as client, pytest.raises(InvalidResponseError, match="expected contract"):
        client.auth.login(TEST_EMAIL, TEST_PASSWORD)
        client.cdn.dns_records.update("snapp.ir", _update_record())


@respx.mock
def test_delete_dns_record_rejects_missing_required_response_fields(
    login_payload: dict[str, object],
) -> None:
    _mock_login(login_payload)
    respx.delete(DNS_RECORD_DELETE_URL).mock(return_value=httpx.Response(200, json={"data": []}))

    with ArvanCloud() as client, pytest.raises(InvalidResponseError, match="expected contract"):
        client.auth.login(TEST_EMAIL, TEST_PASSWORD)
        client.cdn.dns_records.delete("snapp.ir", RECORD_ID)


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


@respx.mock
def test_create_dns_record_ignores_unknown_response_fields(
    login_payload: dict[str, object],
    dns_record_create_response_payload: dict[str, object],
) -> None:
    response_payload = dict(dns_record_create_response_payload)
    response_data = dict(response_payload["data"])
    response_data["futureField"] = {"can": "be ignored"}
    response_payload["data"] = response_data
    _mock_login(login_payload)
    respx.post(DNS_RECORDS_URL).mock(return_value=httpx.Response(201, json=response_payload))

    with ArvanCloud() as client:
        client.auth.login(TEST_EMAIL, TEST_PASSWORD)
        record = client.cdn.dns_records.create("snapp.ir", _create_record())

    assert record.name == "sss"


@respx.mock
def test_set_dns_record_cloud_ignores_unknown_response_fields(
    login_payload: dict[str, object],
    dns_record_cloud_update_response_payload: dict[str, object],
) -> None:
    response_payload = dict(dns_record_cloud_update_response_payload)
    response_data = dict(response_payload["data"])
    response_data["futureField"] = {"can": "be ignored"}
    response_payload["data"] = response_data
    _mock_login(login_payload)
    respx.put(DNS_RECORD_CLOUD_URL).mock(return_value=httpx.Response(200, json=response_payload))

    with ArvanCloud() as client:
        client.auth.login(TEST_EMAIL, TEST_PASSWORD)
        record = client.cdn.dns_records.set_cloud("snapp.ir", RECORD_ID, cloud=True)

    assert record.cloud is True


@respx.mock
def test_update_dns_record_ignores_unknown_response_fields(
    login_payload: dict[str, object],
    dns_record_update_response_payload: dict[str, object],
) -> None:
    response_payload = dict(dns_record_update_response_payload)
    response_data = dict(response_payload["data"])
    response_data["futureField"] = {"can": "be ignored"}
    response_payload["data"] = response_data
    _mock_login(login_payload)
    respx.put(DNS_RECORD_UPDATE_URL).mock(return_value=httpx.Response(200, json=response_payload))

    with ArvanCloud() as client:
        client.auth.login(TEST_EMAIL, TEST_PASSWORD)
        record = client.cdn.dns_records.update("snapp.ir", _update_record())

    assert record.value == [{"ip": "85.5.5.6", "port": None, "weight": 100, "country": ""}]


@respx.mock
def test_delete_dns_record_ignores_unknown_response_fields(
    login_payload: dict[str, object],
    dns_record_delete_response_payload: dict[str, object],
) -> None:
    response_payload = {
        **dns_record_delete_response_payload,
        "futureField": {"can": "be ignored"},
    }
    _mock_login(login_payload)
    respx.delete(DNS_RECORD_DELETE_URL).mock(
        return_value=httpx.Response(200, json=response_payload)
    )

    with ArvanCloud() as client:
        client.auth.login(TEST_EMAIL, TEST_PASSWORD)
        result = client.cdn.dns_records.delete("snapp.ir", RECORD_ID)

    assert result.message == "DNS record deleted."
