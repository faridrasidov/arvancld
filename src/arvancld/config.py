# src/arvancld/config.py
"""Client configuration and endpoint defaults."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlsplit

import httpx

DEFAULT_AUTH_BASE_URL = "https://dejban.arvancloud.ir"
DEFAULT_CDN_BASE_URL = "https://napi.arvancloud.ir/cdn/4.0"
DEFAULT_REDIRECT_URI = "https://panel.arvancloud.ir/"
DEFAULT_TIMEOUT = 30.0
DEFAULT_USER_AGENT = "arvancld/0.1.0"
DEFAULT_RETRY_STATUS_CODES = frozenset({429, 502, 503, 504})


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    """Retry settings applied only to idempotent GET requests."""

    max_attempts: int = 3
    backoff_factor: float = 0.5
    max_backoff: float = 8.0
    max_retry_after: float = 30.0
    status_codes: frozenset[int] = DEFAULT_RETRY_STATUS_CODES

    def __post_init__(self) -> None:
        status_codes = frozenset(self.status_codes)
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be greater than zero")
        if self.backoff_factor < 0:
            raise ValueError("backoff_factor must not be negative")
        if self.max_backoff < 0:
            raise ValueError("max_backoff must not be negative")
        if self.max_retry_after < 0:
            raise ValueError("max_retry_after must not be negative")
        if any(
            not isinstance(status_code, int) or status_code < 400 or status_code > 599
            for status_code in status_codes
        ):
            raise ValueError("status_codes must contain HTTP error status codes")
        object.__setattr__(self, "status_codes", status_codes)


DEFAULT_RETRY_POLICY = RetryPolicy()


def _validate_http_url(value: str, *, field_name: str) -> str:
    candidate = value.strip()
    parsed = urlsplit(candidate)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"{field_name} must be an absolute HTTP or HTTPS URL")
    return candidate


@dataclass(frozen=True, slots=True)
class ClientConfig:
    """Configuration shared by synchronous and asynchronous clients."""

    auth_base_url: str = DEFAULT_AUTH_BASE_URL
    cdn_base_url: str = DEFAULT_CDN_BASE_URL
    redirect_uri: str = DEFAULT_REDIRECT_URI
    timeout: float | httpx.Timeout = DEFAULT_TIMEOUT
    user_agent: str = DEFAULT_USER_AGENT
    limits: httpx.Limits | None = None
    retry_policy: RetryPolicy | None = DEFAULT_RETRY_POLICY

    def __post_init__(self) -> None:
        if isinstance(self.timeout, int | float) and self.timeout <= 0:
            raise ValueError("timeout must be greater than zero")
        if not isinstance(self.timeout, int | float | httpx.Timeout):
            raise TypeError("timeout must be a number or httpx.Timeout")
        if self.limits is not None and not isinstance(self.limits, httpx.Limits):
            raise TypeError("limits must be httpx.Limits or None")
        if self.retry_policy is not None and not isinstance(self.retry_policy, RetryPolicy):
            raise TypeError("retry_policy must be RetryPolicy or None")
        if not self.user_agent.strip():
            raise ValueError("user_agent must not be blank")

        auth_base_url = _validate_http_url(self.auth_base_url, field_name="auth_base_url")
        cdn_base_url = _validate_http_url(self.cdn_base_url, field_name="cdn_base_url")
        redirect_uri = _validate_http_url(self.redirect_uri, field_name="redirect_uri")

        object.__setattr__(self, "auth_base_url", auth_base_url.rstrip("/"))
        object.__setattr__(self, "cdn_base_url", cdn_base_url.rstrip("/"))
        object.__setattr__(self, "redirect_uri", redirect_uri)
        object.__setattr__(self, "user_agent", self.user_agent.strip())

    def auth_url(self, path: str) -> str:
        """Build an absolute URL for the account authentication service."""

        return f"{self.auth_base_url}/{path.lstrip('/')}"

    def cdn_url(self, path: str) -> str:
        """Build an absolute URL for the CDN service."""

        return f"{self.cdn_base_url}/{path.lstrip('/')}"
