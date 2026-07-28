# src/arvancld/cdn/service.py
"""Synchronous and asynchronous service adapters for the CDN v4 API."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator, Sequence
from contextlib import aclosing
from typing import Protocol, TypeVar, get_args
from urllib.parse import quote
from uuid import UUID

from arvancld._transport import AsyncTransport, SyncTransport
from arvancld.auth.models import LoginResult
from arvancld.cdn.models import (
    CDNDomain,
    CDNDomainPage,
    DNSRecord,
    DNSRecordCloudUpdateResponse,
    DNSRecordCreate,
    DNSRecordCreateResponse,
    DNSRecordDeleteResult,
    DNSRecordPage,
    DNSRecordType,
    DNSRecordUpdate,
    DNSRecordUpdateResponse,
)
from arvancld.config import ClientConfig
from arvancld.exceptions import AuthenticationRequiredError

DNSRecordTypeFilter = DNSRecordType | str | Sequence[DNSRecordType | str]
_ALLOWED_DNS_RECORD_TYPES = set(get_args(DNSRecordType))
PageT = TypeVar("PageT", CDNDomainPage, DNSRecordPage)


class _TokenProvider(Protocol):
    @property
    def tokens(self) -> LoginResult | None:
        """Return the current in-memory login state."""


def _validate_pagination(page: int, per_page: int) -> None:
    if page < 1:
        raise ValueError("page must be greater than zero")
    if per_page < 1:
        raise ValueError("per_page must be greater than zero")


def _validate_prefetch(prefetch: int) -> None:
    if prefetch < 1:
        raise ValueError("prefetch must be greater than zero")


async def _iter_async_pages(
    fetch_page: Callable[[int], Awaitable[PageT]],
    *,
    prefetch: int,
) -> AsyncIterator[PageT]:
    """Yield an initial page and its remaining pages in order with bounded prefetch."""

    _validate_prefetch(prefetch)
    first_page = await fetch_page(1)
    yield first_page

    last_page = first_page.meta.last_page
    pending: dict[int, asyncio.Task[PageT]] = {}
    next_page_to_schedule = 2

    try:
        for page_number in range(2, last_page + 1):
            while next_page_to_schedule <= last_page and len(pending) < prefetch:
                pending[next_page_to_schedule] = asyncio.create_task(
                    fetch_page(next_page_to_schedule)
                )
                next_page_to_schedule += 1

            yield await pending.pop(page_number)
    finally:
        for task in pending.values():
            task.cancel()
        if pending:
            await asyncio.gather(*pending.values(), return_exceptions=True)


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


def _validate_optional_nonblank(name: str, value: str | None) -> str | None:
    if value is None:
        return None

    candidate = value.strip()
    if not candidate:
        raise ValueError(f"{name} must not be blank")
    return candidate


def _normalize_record_types(record_types: DNSRecordTypeFilter | None) -> str | None:
    if record_types is None:
        return None

    values = [record_types] if isinstance(record_types, str) else list(record_types)

    if not values:
        raise ValueError("record_types must not be empty")

    normalized: list[str] = []
    for value in values:
        if not isinstance(value, str):
            raise ValueError("record_types must contain strings")

        candidate = value.strip().lower()
        if candidate not in _ALLOWED_DNS_RECORD_TYPES:
            raise ValueError("record_types contains an unsupported DNS record type")
        normalized.append(candidate)

    return ",".join(normalized)


def _dns_record_list_params(
    *,
    page: int,
    per_page: int,
    record_types: DNSRecordTypeFilter | None,
    search: str | None,
    match_type: str | None,
) -> dict[str, int | str]:
    _validate_pagination(page, per_page)
    params: dict[str, int | str] = {"page": page, "per_page": per_page}

    normalized_record_types = _normalize_record_types(record_types)
    if normalized_record_types is not None:
        params["type"] = normalized_record_types

    normalized_search = _validate_optional_nonblank("search", search)
    if normalized_search is not None:
        params["search"] = normalized_search

    normalized_match_type = _validate_optional_nonblank("match_type", match_type)
    if normalized_match_type is not None:
        params["match_type"] = normalized_match_type

    return params


def _authorization_header(token_provider: _TokenProvider) -> dict[str, str]:
    tokens = token_provider.tokens
    if tokens is None:
        raise AuthenticationRequiredError("CDN requests require a successful login first")
    return {"Authorization": f"Bearer {tokens.access_token}.{tokens.default_account}"}


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

    def iter_all(self, *, per_page: int = 5) -> Iterator[CDNDomain]:
        """Yield all CDN domains lazily in page order."""

        _validate_pagination(1, per_page)
        first_page = self.list(page=1, per_page=per_page)
        yield from first_page.data

        for page_number in range(2, first_page.meta.last_page + 1):
            page = self.list(page=page_number, per_page=per_page)
            yield from page.data


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
        record_types: DNSRecordTypeFilter | None = None,
        search: str | None = None,
        match_type: str | None = None,
    ) -> DNSRecordPage:
        """List DNS records for a CDN domain."""

        params = _dns_record_list_params(
            page=page,
            per_page=per_page,
            record_types=record_types,
            search=search,
            match_type=match_type,
        )
        domain = quote(_validate_domain(domain), safe=".-")
        return self._transport.request_model(
            "GET",
            self._config.cdn_url(f"/domains/{domain}/dns-records"),
            model=DNSRecordPage,
            params=params,
            headers=_authorization_header(self._token_provider),
        )

    def iter_all(
        self,
        domain: str,
        *,
        per_page: int = 25,
        record_types: DNSRecordTypeFilter | None = None,
        search: str | None = None,
        match_type: str | None = None,
    ) -> Iterator[DNSRecord]:
        """Yield all DNS records for a CDN domain lazily in page order."""

        _validate_pagination(1, per_page)
        first_page = self.list(
            domain,
            page=1,
            per_page=per_page,
            record_types=record_types,
            search=search,
            match_type=match_type,
        )
        yield from first_page.data

        for page_number in range(2, first_page.meta.last_page + 1):
            page = self.list(
                domain,
                page=page_number,
                per_page=per_page,
                record_types=record_types,
                search=search,
                match_type=match_type,
            )
            yield from page.data

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

    def update(self, domain: str, record: DNSRecordUpdate) -> DNSRecord:
        """Update a DNS record for a CDN domain."""

        domain = quote(_validate_domain(domain), safe=".-")
        record_id = quote(_validate_record_id(record.id), safe="-")
        response = self._transport.request_model(
            "PUT",
            self._config.cdn_url(f"/domains/{domain}/dns-records/{record_id}/"),
            model=DNSRecordUpdateResponse,
            json=record.model_dump(mode="json", by_alias=True),
            headers=_authorization_header(self._token_provider),
        )
        return response.data

    def delete(self, domain: str, record_id: UUID | str) -> DNSRecordDeleteResult:
        """Delete a DNS record from a CDN domain."""

        domain = quote(_validate_domain(domain), safe=".-")
        record_id = quote(_validate_record_id(record_id), safe="-")
        return self._transport.request_model(
            "DELETE",
            self._config.cdn_url(f"/domains/{domain}/dns-records/{record_id}"),
            model=DNSRecordDeleteResult,
            headers=_authorization_header(self._token_provider),
        )


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

    async def iter_all(
        self,
        *,
        per_page: int = 5,
        prefetch: int = 1,
    ) -> AsyncIterator[CDNDomain]:
        """Yield all CDN domains lazily in page order."""

        _validate_pagination(1, per_page)

        async def fetch_page(page_number: int) -> CDNDomainPage:
            return await self.list(page=page_number, per_page=per_page)

        async with aclosing(_iter_async_pages(fetch_page, prefetch=prefetch)) as pages:
            async for page in pages:
                for domain in page.data:
                    yield domain


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
        record_types: DNSRecordTypeFilter | None = None,
        search: str | None = None,
        match_type: str | None = None,
    ) -> DNSRecordPage:
        """List DNS records for a CDN domain."""

        params = _dns_record_list_params(
            page=page,
            per_page=per_page,
            record_types=record_types,
            search=search,
            match_type=match_type,
        )
        domain = quote(_validate_domain(domain), safe=".-")
        return await self._transport.request_model(
            "GET",
            self._config.cdn_url(f"/domains/{domain}/dns-records"),
            model=DNSRecordPage,
            params=params,
            headers=_authorization_header(self._token_provider),
        )

    async def iter_all(
        self,
        domain: str,
        *,
        per_page: int = 25,
        record_types: DNSRecordTypeFilter | None = None,
        search: str | None = None,
        match_type: str | None = None,
        prefetch: int = 1,
    ) -> AsyncIterator[DNSRecord]:
        """Yield all DNS records for a CDN domain lazily in page order."""

        _validate_pagination(1, per_page)

        async def fetch_page(page_number: int) -> DNSRecordPage:
            return await self.list(
                domain,
                page=page_number,
                per_page=per_page,
                record_types=record_types,
                search=search,
                match_type=match_type,
            )

        async with aclosing(_iter_async_pages(fetch_page, prefetch=prefetch)) as pages:
            async for page in pages:
                for record in page.data:
                    yield record

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

    async def update(self, domain: str, record: DNSRecordUpdate) -> DNSRecord:
        """Update a DNS record for a CDN domain."""

        domain = quote(_validate_domain(domain), safe=".-")
        record_id = quote(_validate_record_id(record.id), safe="-")
        response = await self._transport.request_model(
            "PUT",
            self._config.cdn_url(f"/domains/{domain}/dns-records/{record_id}/"),
            model=DNSRecordUpdateResponse,
            json=record.model_dump(mode="json", by_alias=True),
            headers=_authorization_header(self._token_provider),
        )
        return response.data

    async def delete(self, domain: str, record_id: UUID | str) -> DNSRecordDeleteResult:
        """Delete a DNS record from a CDN domain."""

        domain = quote(_validate_domain(domain), safe=".-")
        record_id = quote(_validate_record_id(record_id), safe="-")
        return await self._transport.request_model(
            "DELETE",
            self._config.cdn_url(f"/domains/{domain}/dns-records/{record_id}"),
            model=DNSRecordDeleteResult,
            headers=_authorization_header(self._token_provider),
        )


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
