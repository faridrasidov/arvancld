# src/arvancld/cdn/models.py
"""Typed models for ArvanCloud CDN read APIs."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

DNSRecordValue = dict[str, Any] | list[dict[str, Any]]


def _ensure_timezone(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must include a timezone")
    return value


class PaginationLinks(BaseModel):
    """Top-level pagination links returned by CDN list endpoints."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    first: str
    last: str
    prev: str | None
    next: str | None


class PaginationMetaLink(BaseModel):
    """Individual pagination link metadata."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    url: str | None
    label: str
    page: int | None
    active: bool


class PaginationMeta(BaseModel):
    """Pagination metadata returned by CDN list endpoints."""

    model_config = ConfigDict(extra="ignore", frozen=True, populate_by_name=True)

    current_page: int
    from_: int | None = Field(alias="from")
    last_page: int
    links: list[PaginationMetaLink]
    path: str
    per_page: int
    to: int | None
    total: int


class CDNDomain(BaseModel):
    """A CDN domain returned by the domains list endpoint."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    id: UUID
    account_id: UUID
    user_id: UUID
    domain: str
    name: str
    plan_level: int
    plan_duration: int
    ns_keys: list[str]
    smart_routing_status: str
    current_ns: list[str]
    status: str
    restriction: list[Any]
    type: str
    cname_target: str | None
    custom_cname: str
    use_new_waf_engine: bool
    transfer: dict[str, Any] | None
    fingerprint_status: bool
    created_at: datetime
    updated_at: datetime

    @field_validator("created_at", "updated_at")
    @classmethod
    def ensure_timezone(cls, value: datetime) -> datetime:
        return _ensure_timezone(value)


class CDNDomainPage(BaseModel):
    """Paginated CDN domain list response."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    data: list[CDNDomain]
    links: PaginationLinks
    meta: PaginationMeta
    message: str | None = None


class IPFilterMode(BaseModel):
    """IP filter mode details for a DNS record."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    count: str
    order: str
    geo_filter: str


class DNSRecordIPValue(BaseModel):
    """IP target value for DNS record create requests."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    ip: str
    port: int | None = None
    weight: int | None = None
    country: str = ""


DNSRecordCreateValue = dict[str, Any] | list[DNSRecordIPValue | dict[str, Any]]


class DNSRecordCreate(BaseModel):
    """Payload for creating a DNS record."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    type: str
    name: str
    cloud: bool
    value: DNSRecordCreateValue
    ttl: int
    upstream_https: str
    ip_filter_mode: IPFilterMode

    @field_validator("type", "name", "upstream_https")
    @classmethod
    def ensure_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("field must not be blank")
        return value

    @field_validator("ttl")
    @classmethod
    def ensure_positive_ttl(cls, value: int) -> int:
        if value < 1:
            raise ValueError("ttl must be greater than zero")
        return value


class DNSRecordUpdate(DNSRecordCreate):
    """Payload for updating a DNS record."""

    id: UUID


class DNSRecord(BaseModel):
    """A DNS record returned by the CDN DNS records endpoint."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    id: UUID
    type: str
    name: str
    value: DNSRecordValue
    ttl: int
    cloud: bool
    upstream_https: str
    ip_filter_mode: IPFilterMode
    is_protected: bool
    usage: list[Any]
    created_at: datetime
    updated_at: datetime

    @field_validator("created_at", "updated_at")
    @classmethod
    def ensure_timezone(cls, value: datetime) -> datetime:
        return _ensure_timezone(value)


class DNSRecordPage(BaseModel):
    """Paginated DNS record list response."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    data: list[DNSRecord]
    links: PaginationLinks
    meta: PaginationMeta
    message: str | None = None


class DNSRecordCreateResponse(BaseModel):
    """Envelope returned by the DNS record create endpoint."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    data: DNSRecord
    message: str | None = None


class DNSRecordCloudUpdateResponse(BaseModel):
    """Envelope returned by the DNS record cloud toggle endpoint."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    data: DNSRecord
    message: str | None = None


class DNSRecordUpdateResponse(BaseModel):
    """Envelope returned by the DNS record update endpoint."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    data: DNSRecord
    message: str | None = None


class DNSRecordDeleteResult(BaseModel):
    """Result returned by the DNS record delete endpoint."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    data: list[Any]
    message: str
