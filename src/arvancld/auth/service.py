# src/arvancld/auth/service.py
"""Synchronous and asynchronous account-authentication services."""

from __future__ import annotations

from pathlib import Path

from arvancld._transport import AsyncTransport, SyncTransport
from arvancld.auth.models import LoginResponse, LoginResult
from arvancld.auth.session import clear_session_file, load_session_file, save_session_file
from arvancld.config import ClientConfig
from arvancld.exceptions import AuthenticationRequiredError

LOGIN_PATH = "/v1/auth/login"


def _login_payload(email: str, password: str) -> dict[str, str]:
    if not email.strip():
        raise ValueError("email must not be blank")
    if not password:
        raise ValueError("password must not be blank")
    return {"email": email, "password": password}


class AuthService:
    """Synchronous account-authentication operations."""

    def __init__(self, transport: SyncTransport, config: ClientConfig) -> None:
        self._transport = transport
        self._config = config
        self._tokens: LoginResult | None = None

    @property
    def tokens(self) -> LoginResult | None:
        """The most recent successful login result, stored only in memory."""

        return self._tokens

    def login(self, email: str, password: str) -> LoginResult:
        """Authenticate an account and retain the returned tokens in memory."""

        response = self._transport.request_model(
            "POST",
            self._config.auth_url(LOGIN_PATH),
            model=LoginResponse,
            json=_login_payload(email, password),
            headers={"X-Redirect-Uri": self._config.redirect_uri},
        )
        self._tokens = response.data
        return response.data

    def save_session(self, path: str | Path) -> None:
        """Persist the current login result to an explicit plaintext JSON path."""

        if self._tokens is None:
            raise AuthenticationRequiredError(
                "A successful login is required before saving a session"
            )
        save_session_file(path, self._tokens)

    def load_session(self, path: str | Path) -> LoginResult:
        """Load an unexpired saved session and retain its tokens in memory."""

        tokens = load_session_file(path)
        self._tokens = tokens
        return tokens

    def clear_session(self, path: str | Path) -> None:
        """Delete a saved session file and clear the in-memory login state."""

        clear_session_file(path)
        self._tokens = None


class AsyncAuthService:
    """Asynchronous account-authentication operations."""

    def __init__(self, transport: AsyncTransport, config: ClientConfig) -> None:
        self._transport = transport
        self._config = config
        self._tokens: LoginResult | None = None

    @property
    def tokens(self) -> LoginResult | None:
        """The most recent successful login result, stored only in memory."""

        return self._tokens

    async def login(self, email: str, password: str) -> LoginResult:
        """Authenticate an account and retain the returned tokens in memory."""

        response = await self._transport.request_model(
            "POST",
            self._config.auth_url(LOGIN_PATH),
            model=LoginResponse,
            json=_login_payload(email, password),
            headers={"X-Redirect-Uri": self._config.redirect_uri},
        )
        self._tokens = response.data
        return response.data

    def save_session(self, path: str | Path) -> None:
        """Persist the current login result to an explicit plaintext JSON path."""

        if self._tokens is None:
            raise AuthenticationRequiredError(
                "A successful login is required before saving a session"
            )
        save_session_file(path, self._tokens)

    def load_session(self, path: str | Path) -> LoginResult:
        """Load an unexpired saved session and retain its tokens in memory."""

        tokens = load_session_file(path)
        self._tokens = tokens
        return tokens

    def clear_session(self, path: str | Path) -> None:
        """Delete a saved session file and clear the in-memory login state."""

        clear_session_file(path)
        self._tokens = None
