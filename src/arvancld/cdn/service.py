# src/arvancld/cdn/service.py
"""Synchronous and asynchronous service adapters for the CDN v4 API."""

from __future__ import annotations

from typing import Protocol
from urllib.parse import quote
from uuid import UUID

from arvancld._transport import AsyncTransport, SyncTransport
from arvancld.auth.models import LoginResult
from arvancld.cdn.models import (
    CDNDomainPage,
    DNSRecord,
    DNSRecordCloudUpdateResponse,
    DNSRecordCreate,
    DNSRecordCreateResponse,
    DNSRecordPage,
)
from arvancld.config import ClientConfig
from arvancld.exceptions import AuthenticationRequiredError


class _TokenProvider(Protocol):
    @property
    def tokens(self) -> LoginResult | None:
        """Return the current in-memory login state."""


def _validate_pagination(page: int, per_page: int) -> None:
    if page < 1:
        raise ValueError("page must be greater than zero")
    if per_page < 1:
        raise ValueError("per_page must be greater than zero")


def _validate_domain(domain: str) -> str:
    candidate = domain.strip()
    if not candidate:
        raise ValueError("domain must not be blank")
    if "/" in candidate:
        raise ValueError("domain must not contain '/'")
    return candidate


def _validate_record_id(record_id: UUID | str) -> str:
    if isinstance(record_id, UUID):
        return str(record_id)

    candidate = record_id.strip()
    if not candidate:
        raise ValueError("record_id must not be blank")
    if "/" in candidate:
        raise ValueError("record_id must not contain '/'")
    return candidate


def _authorization_header(token_provider: _TokenProvider) -> dict[str, str]:
    tokens = token_provider.tokens
    if tokens is None:
        raise AuthenticationRequiredError("CDN requests require a successful login first")
    return {"Authorization": f"Bearer {tokens.access_token}"}


class DomainService:
    """Synchronous CDN domain operations."""

    def __init__(
        self,
        transport: SyncTransport,
        config: ClientConfig,
        token_provider: _TokenProvider,
    ) -> None:
        self._transport = transport
        self._config = config
        self._token_provider = token_provider

    def list(self, *, page: int = 1, per_page: int = 5) -> CDNDomainPage:
        """List CDN domains for the logged-in account."""

        _validate_pagination(page, per_page)
        return self._transport.request_model(
            "GET",
            self._config.cdn_url("/domains"),
            model=CDNDomainPage,
            params={"page": page, "perPage": per_page},
            headers=_authorization_header(self._token_provider),
        )


class DNSRecordService:
    """Synchronous CDN DNS record operations."""

    def __init__(
        self,
        transport: SyncTransport,
        config: ClientConfig,
        token_provider: _TokenProvider,
    ) -> None:
        self._transport = transport
        self._config = config
        self._token_provider = token_provider

    def list(
        self,
        domain: str,
        *,
        page: int = 1,
        per_page: int = 25,
    ) -> DNSRecordPage:
        """List DNS records for a CDN domain."""

        _validate_pagination(page, per_page)
        domain = quote(_validate_domain(domain), safe=".-")
        return self._transport.request_model(
            "GET",
            self._config.cdn_url(f"/domains/{domain}/dns-records"),
            model=DNSRecordPage,
            params={"page": page, "per_page": per_page},
            headers=_authorization_header(self._token_provider),
        )

    def create(self, domain: str, record: DNSRecordCreate) -> DNSRecord:
        """Create a DNS record for a CDN domain."""

        domain = quote(_validate_domain(domain), safe=".-")
        response = self._transport.request_model(
            "POST",
            self._config.cdn_url(f"/domains/{domain}/dns-records"),
            model=DNSRecordCreateResponse,
            json=record.model_dump(mode="json", by_alias=True),
            headers=_authorization_header(self._token_provider),
        )
        return response.data

    def set_cloud(self, domain: str, record_id: UUID | str, *, cloud: bool) -> DNSRecord:
        """Turn the CDN cloud proxy on or off for a DNS record."""

        domain = quote(_validate_domain(domain), safe=".-")
        record_id = quote(_validate_record_id(record_id), safe="-")
        response = self._transport.request_model(
            "PUT",
            self._config.cdn_url(f"/domains/{domain}/dns-records/{record_id}/cloud"),
            model=DNSRecordCloudUpdateResponse,
            json={"cloud": cloud},
            headers=_authorization_header(self._token_provider),
        )
        return response.data


class CDNService:
    """Synchronous CDN API namespace."""

    def __init__(
        self,
        transport: SyncTransport,
        config: ClientConfig,
        token_provider: _TokenProvider,
    ) -> None:
        self.domains = DomainService(transport, config, token_provider)
        self.dns_records = DNSRecordService(transport, config, token_provider)


class AsyncDomainService:
    """Asynchronous CDN domain operations."""

    def __init__(
        self,
        transport: AsyncTransport,
        config: ClientConfig,
        token_provider: _TokenProvider,
    ) -> None:
        self._transport = transport
        self._config = config
        self._token_provider = token_provider

    async def list(self, *, page: int = 1, per_page: int = 5) -> CDNDomainPage:
        """List CDN domains for the logged-in account."""

        _validate_pagination(page, per_page)
        return await self._transport.request_model(
            "GET",
            self._config.cdn_url("/domains"),
            model=CDNDomainPage,
            params={"page": page, "perPage": per_page},
            headers=_authorization_header(self._token_provider),
        )


class AsyncDNSRecordService:
    """Asynchronous CDN DNS record operations."""

    def __init__(
        self,
        transport: AsyncTransport,
        config: ClientConfig,
        token_provider: _TokenProvider,
    ) -> None:
        self._transport = transport
        self._config = config
        self._token_provider = token_provider

    async def list(
        self,
        domain: str,
        *,
        page: int = 1,
        per_page: int = 25,
    ) -> DNSRecordPage:
        """List DNS records for a CDN domain."""

        _validate_pagination(page, per_page)
        domain = quote(_validate_domain(domain), safe=".-")
        return await self._transport.request_model(
            "GET",
            self._config.cdn_url(f"/domains/{domain}/dns-records"),
            model=DNSRecordPage,
            params={"page": page, "per_page": per_page},
            headers=_authorization_header(self._token_provider),
        )

    async def create(self, domain: str, record: DNSRecordCreate) -> DNSRecord:
        """Create a DNS record for a CDN domain."""

        domain = quote(_validate_domain(domain), safe=".-")
        response = await self._transport.request_model(
            "POST",
            self._config.cdn_url(f"/domains/{domain}/dns-records"),
            model=DNSRecordCreateResponse,
            json=record.model_dump(mode="json", by_alias=True),
            headers=_authorization_header(self._token_provider),
        )
        return response.data

    async def set_cloud(self, domain: str, record_id: UUID | str, *, cloud: bool) -> DNSRecord:
        """Turn the CDN cloud proxy on or off for a DNS record."""

        domain = quote(_validate_domain(domain), safe=".-")
        record_id = quote(_validate_record_id(record_id), safe="-")
        response = await self._transport.request_model(
            "PUT",
            self._config.cdn_url(f"/domains/{domain}/dns-records/{record_id}/cloud"),
            model=DNSRecordCloudUpdateResponse,
            json={"cloud": cloud},
            headers=_authorization_header(self._token_provider),
        )
        return response.data


class AsyncCDNService:
    """Asynchronous CDN API namespace."""

    def __init__(
        self,
        transport: AsyncTransport,
        config: ClientConfig,
        token_provider: _TokenProvider,
    ) -> None:
        self.domains = AsyncDomainService(transport, config, token_provider)
        self.dns_records = AsyncDNSRecordService(transport, config, token_provider)
