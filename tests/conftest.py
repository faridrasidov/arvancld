# tests/conftest.py
"""Shared test fixtures and sample payloads."""

from __future__ import annotations

import pytest


@pytest.fixture
def login_payload() -> dict[str, object]:
    return {
        "data": {
            "accessToken": "access-secret",
            "refreshToken": "refresh-secret",
            "expiresAt": "2026-07-25T04:07:52Z",
            "defaultAccount": "af999c67-2a12-517c-b52b-8bb5e2b59bad",
            "flow": "ProvideCredential",
            "next": "RedirectToPanel",
        }
    }


@pytest.fixture
def cdn_domain_payload() -> dict[str, object]:
    return {
        "data": [
            {
                "id": "f1b2ad75-ae1d-4c73-ba25-e1d55b950d07",
                "account_id": "af999c67-2a12-517c-b52b-8bb5e2b59bad",
                "user_id": "af999c67-2a12-517c-b52b-8bb5e2b59bad",
                "domain": "snapp.ir",
                "name": "snapp.ir",
                "plan_level": 1,
                "plan_duration": 0,
                "ns_keys": ["f.ns.arvancdn.ir", "s.ns.arvancdn.ir"],
                "smart_routing_status": "off",
                "current_ns": ["f.ns.arvancdn.ir", "s.ns.arvancdn.ir"],
                "status": "active",
                "restriction": [],
                "type": "full",
                "cname_target": None,
                "custom_cname": "",
                "use_new_waf_engine": True,
                "transfer": None,
                "fingerprint_status": False,
                "created_at": "2026-04-02T18:26:45+00:00",
                "updated_at": "2026-07-24T15:15:12+00:00",
            }
        ],
        "links": {
            "first": "https://napi.arvancloud.ir/4.0/domains?page=1",
            "last": "https://napi.arvancloud.ir/4.0/domains?page=1",
            "prev": None,
            "next": None,
        },
        "meta": {
            "current_page": 1,
            "from": 1,
            "last_page": 1,
            "links": [
                {
                    "url": None,
                    "label": "&laquo; Previous",
                    "page": None,
                    "active": False,
                },
                {
                    "url": "https://napi.arvancloud.ir/4.0/domains?page=1",
                    "label": "1",
                    "page": 1,
                    "active": True,
                },
                {
                    "url": None,
                    "label": "Next &raquo;",
                    "page": None,
                    "active": False,
                },
            ],
            "path": "https://napi.arvancloud.ir/4.0/domains",
            "per_page": 15,
            "to": 1,
            "total": 1,
        },
        "message": "",
    }


@pytest.fixture
def dns_records_payload() -> dict[str, object]:
    return {
        "data": [
            {
                "id": "fc14fa54-0ea9-40ec-aba8-f5426e988b57",
                "type": "a",
                "name": "home-1",
                "value": [
                    {
                        "ip": "2.180.180.167",
                        "port": None,
                        "weight": 100,
                        "country": "",
                    }
                ],
                "ttl": 120,
                "cloud": False,
                "upstream_https": "default",
                "ip_filter_mode": {
                    "count": "single",
                    "order": "none",
                    "geo_filter": "none",
                },
                "is_protected": False,
                "usage": [],
                "created_at": "2026-04-04T09:54:21+00:00",
                "updated_at": "2026-05-27T09:55:14+00:00",
            },
            {
                "id": "0076f83a-0e74-42e0-8e67-5535708aaa86",
                "type": "ns",
                "name": "@",
                "value": {"host": "s.ns.arvancdn.ir."},
                "ttl": 7200,
                "cloud": False,
                "upstream_https": "default",
                "ip_filter_mode": {
                    "count": "single",
                    "order": "none",
                    "geo_filter": "none",
                },
                "is_protected": True,
                "usage": [],
                "created_at": "2026-04-02T18:26:49+00:00",
                "updated_at": "2026-04-02T18:26:49+00:00",
            },
        ],
        "links": {
            "first": "https://napi.arvancloud.ir/4.0/domains/snapp.ir/dns-records?page=1",
            "last": "https://napi.arvancloud.ir/4.0/domains/snapp.ir/dns-records?page=1",
            "prev": None,
            "next": None,
        },
        "meta": {
            "current_page": 1,
            "from": 1,
            "last_page": 1,
            "links": [
                {
                    "url": None,
                    "label": "&laquo; Previous",
                    "page": None,
                    "active": False,
                },
                {
                    "url": "https://napi.arvancloud.ir/4.0/domains/snapp.ir/dns-records?page=1",
                    "label": "1",
                    "page": 1,
                    "active": True,
                },
                {
                    "url": None,
                    "label": "Next &raquo;",
                    "page": None,
                    "active": False,
                },
            ],
            "path": "https://napi.arvancloud.ir/4.0/domains/snapp.ir/dns-records",
            "per_page": 25,
            "to": 2,
            "total": 2,
        },
    }
