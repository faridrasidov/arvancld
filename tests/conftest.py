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
