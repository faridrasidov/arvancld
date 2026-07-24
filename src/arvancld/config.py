# src/arvancld/config.py
"""Client configuration and endpoint defaults."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlsplit

DEFAULT_AUTH_BASE_URL = "https://dejban.arvancloud.ir"
DEFAULT_CDN_BASE_URL = "https://napi.arvancloud.ir/cdn/4.0"
DEFAULT_REDIRECT_URI = "https://panel.arvancloud.ir/"
DEFAULT_TIMEOUT = 30.0
DEFAULT_USER_AGENT = "arvancld/0.1.0"


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
    timeout: float = DEFAULT_TIMEOUT
    user_agent: str = DEFAULT_USER_AGENT

    def __post_init__(self) -> None:
        if self.timeout <= 0:
            raise ValueError("timeout must be greater than zero")
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
