# src/arvancld/client.py
"""Top-level synchronous and asynchronous ArvanCloud clients."""

from __future__ import annotations

from types import TracebackType

from arvancld._transport import AsyncTransport, SyncTransport
from arvancld.auth.service import AsyncAuthService, AuthService
from arvancld.config import (
    DEFAULT_AUTH_BASE_URL,
    DEFAULT_CDN_BASE_URL,
    DEFAULT_REDIRECT_URI,
    DEFAULT_TIMEOUT,
    DEFAULT_USER_AGENT,
    ClientConfig,
)


class ArvanCloud:
    """Synchronous ArvanCloud client."""

    def __init__(
        self,
        *,
        auth_base_url: str = DEFAULT_AUTH_BASE_URL,
        cdn_base_url: str = DEFAULT_CDN_BASE_URL,
        redirect_uri: str = DEFAULT_REDIRECT_URI,
        timeout: float = DEFAULT_TIMEOUT,
        user_agent: str = DEFAULT_USER_AGENT,
    ) -> None:
        self.config = ClientConfig(
            auth_base_url=auth_base_url,
            cdn_base_url=cdn_base_url,
            redirect_uri=redirect_uri,
            timeout=timeout,
            user_agent=user_agent,
        )
        self._transport = SyncTransport(self.config)
        self.auth = AuthService(self._transport, self.config)

    @property
    def is_closed(self) -> bool:
        """Whether this client's owned HTTP transport has been closed."""

        return self._transport.is_closed

    def close(self) -> None:
        """Close the owned HTTP transport."""

        self._transport.close()

    def __enter__(self) -> ArvanCloud:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()


class AsyncArvanCloud:
    """Asynchronous ArvanCloud client."""

    def __init__(
        self,
        *,
        auth_base_url: str = DEFAULT_AUTH_BASE_URL,
        cdn_base_url: str = DEFAULT_CDN_BASE_URL,
        redirect_uri: str = DEFAULT_REDIRECT_URI,
        timeout: float = DEFAULT_TIMEOUT,
        user_agent: str = DEFAULT_USER_AGENT,
    ) -> None:
        self.config = ClientConfig(
            auth_base_url=auth_base_url,
            cdn_base_url=cdn_base_url,
            redirect_uri=redirect_uri,
            timeout=timeout,
            user_agent=user_agent,
        )
        self._transport = AsyncTransport(self.config)
        self.auth = AsyncAuthService(self._transport, self.config)

    @property
    def is_closed(self) -> bool:
        """Whether this client's owned HTTP transport has been closed."""

        return self._transport.is_closed

    async def close(self) -> None:
        """Close the owned HTTP transport."""

        await self._transport.close()

    async def __aenter__(self) -> AsyncArvanCloud:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self.close()
