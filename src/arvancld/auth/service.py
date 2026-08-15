# src/arvancld/auth/service.py
"""Synchronous and asynchronous account-authentication services."""

from __future__ import annotations

import asyncio
from pathlib import Path

from arvancld._transport import AsyncTransport, SyncTransport
from arvancld.auth.models import (
    ChallengeResponse,
    LoginResponse,
    LoginResult,
    RefreshResponse,
    RefreshResult,
    TOTPChallenge,
)
from arvancld.auth.session import clear_session_file, load_session_file, save_session_file
from arvancld.config import ClientConfig
from arvancld.exceptions import AuthenticationRequiredError, TOTPRequiredError

LOGIN_PATH = "/v1/auth/login"
CHALLENGE_PATH = "/v1/auth/challenge"
REFRESH_PATH = "/v1/auth/refresh-token"


def _login_payload(email: str, password: str) -> dict[str, str]:
    if not email.strip():
        raise ValueError("email must not be blank")
    if not password:
        raise ValueError("password must not be blank")
    return {"email": email, "password": password}


def _totp_payload(challenge: TOTPChallenge, code: str) -> dict[str, str]:
    if not isinstance(code, str):
        raise ValueError("code must contain exactly six ASCII digits")
    candidate = code.strip()
    if len(candidate) != 6 or not candidate.isascii() or not candidate.isdecimal():
        raise ValueError("code must contain exactly six ASCII digits")
    return {
        "code": candidate,
        "flow": challenge.next,
        "flowToken": challenge.flow_token,
    }


def _refresh_headers(tokens: LoginResult) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {tokens.access_token}.{tokens.default_account}",
    }


def _merge_refreshed_tokens(tokens: LoginResult, refreshed: RefreshResult) -> LoginResult:
    return tokens.model_copy(
        update={
            "access_token": refreshed.access_token,
            "refresh_token": refreshed.refresh_token,
            "expires_at": refreshed.expires_at,
        }
    )


class AuthService:
    """Synchronous account-authentication operations."""

    def __init__(self, transport: SyncTransport, config: ClientConfig) -> None:
        self._transport = transport
        self._config = config
        self._tokens: LoginResult | None = None
        self._pending_totp: TOTPChallenge | None = None

    @property
    def tokens(self) -> LoginResult | None:
        """The most recent successful login result, stored only in memory."""

        return self._tokens

    @property
    def pending_totp(self) -> TOTPChallenge | None:
        """The current in-memory TOTP challenge, if login requires one."""

        return self._pending_totp

    def login(self, email: str, password: str) -> LoginResult:
        """Authenticate an account and retain the returned tokens in memory."""

        self._pending_totp = None
        response = self._transport.request_model(
            "POST",
            self._config.auth_url(LOGIN_PATH),
            model=LoginResponse,
            json=_login_payload(email, password),
            headers={"X-Redirect-Uri": self._config.redirect_uri},
        )
        result = response.data
        if isinstance(result, TOTPChallenge):
            self._pending_totp = result
            raise TOTPRequiredError("Login requires a time-based one-time-password challenge")
        self._tokens = result
        return result

    def submit_totp(self, code: str) -> LoginResult:
        """Complete the current TOTP challenge and retain the returned tokens."""

        challenge = self._pending_totp
        if challenge is None:
            raise AuthenticationRequiredError(
                "A pending TOTP challenge is required before submitting a code"
            )
        response = self._transport.request_model(
            "POST",
            self._config.auth_url(CHALLENGE_PATH),
            model=ChallengeResponse,
            json=_totp_payload(challenge, code),
            headers={"X-Redirect-Uri": self._config.redirect_uri},
        )
        self._tokens = response.data
        self._pending_totp = None
        return response.data

    def refresh(self) -> LoginResult:
        """Rotate the current account tokens and retain the complete session."""

        tokens = self._tokens
        if tokens is None:
            raise AuthenticationRequiredError(
                "A successful login or loaded session is required before refreshing"
            )
        response = self._transport.request_model(
            "POST",
            self._config.auth_url(REFRESH_PATH),
            model=RefreshResponse,
            json={"refreshToken": tokens.refresh_token},
            headers=_refresh_headers(tokens),
        )
        refreshed_tokens = _merge_refreshed_tokens(tokens, response.data)
        self._tokens = refreshed_tokens
        self._pending_totp = None
        return refreshed_tokens

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
        self._pending_totp = None
        return tokens

    def clear_session(self, path: str | Path) -> None:
        """Delete a saved session file and clear the in-memory login state."""

        clear_session_file(path)
        self._tokens = None
        self._pending_totp = None


class AsyncAuthService:
    """Asynchronous account-authentication operations."""

    def __init__(self, transport: AsyncTransport, config: ClientConfig) -> None:
        self._transport = transport
        self._config = config
        self._tokens: LoginResult | None = None
        self._pending_totp: TOTPChallenge | None = None

    @property
    def tokens(self) -> LoginResult | None:
        """The most recent successful login result, stored only in memory."""

        return self._tokens

    @property
    def pending_totp(self) -> TOTPChallenge | None:
        """The current in-memory TOTP challenge, if login requires one."""

        return self._pending_totp

    async def login(self, email: str, password: str) -> LoginResult:
        """Authenticate an account and retain the returned tokens in memory."""

        self._pending_totp = None
        response = await self._transport.request_model(
            "POST",
            self._config.auth_url(LOGIN_PATH),
            model=LoginResponse,
            json=_login_payload(email, password),
            headers={"X-Redirect-Uri": self._config.redirect_uri},
        )
        result = response.data
        if isinstance(result, TOTPChallenge):
            self._pending_totp = result
            raise TOTPRequiredError("Login requires a time-based one-time-password challenge")
        self._tokens = result
        return result

    async def submit_totp(self, code: str) -> LoginResult:
        """Complete the current TOTP challenge and retain the returned tokens."""

        challenge = self._pending_totp
        if challenge is None:
            raise AuthenticationRequiredError(
                "A pending TOTP challenge is required before submitting a code"
            )
        response = await self._transport.request_model(
            "POST",
            self._config.auth_url(CHALLENGE_PATH),
            model=ChallengeResponse,
            json=_totp_payload(challenge, code),
            headers={"X-Redirect-Uri": self._config.redirect_uri},
        )
        self._tokens = response.data
        self._pending_totp = None
        return response.data

    async def refresh(self) -> LoginResult:
        """Rotate the current account tokens and retain the complete session."""

        tokens = self._tokens
        if tokens is None:
            raise AuthenticationRequiredError(
                "A successful login or loaded session is required before refreshing"
            )
        response = await self._transport.request_model(
            "POST",
            self._config.auth_url(REFRESH_PATH),
            model=RefreshResponse,
            json={"refreshToken": tokens.refresh_token},
            headers=_refresh_headers(tokens),
        )
        refreshed_tokens = _merge_refreshed_tokens(tokens, response.data)
        self._tokens = refreshed_tokens
        self._pending_totp = None
        return refreshed_tokens

    def save_session(self, path: str | Path) -> None:
        """Persist the current login result to an explicit plaintext JSON path."""

        if self._tokens is None:
            raise AuthenticationRequiredError(
                "A successful login is required before saving a session"
            )
        save_session_file(path, self._tokens)

    async def asave_session(self, path: str | Path) -> None:
        """Persist the current login result without blocking the event loop."""

        tokens = self._tokens
        if tokens is None:
            raise AuthenticationRequiredError(
                "A successful login is required before saving a session"
            )
        await asyncio.to_thread(save_session_file, path, tokens)

    def load_session(self, path: str | Path) -> LoginResult:
        """Load an unexpired saved session and retain its tokens in memory."""

        tokens = load_session_file(path)
        self._tokens = tokens
        self._pending_totp = None
        return tokens

    async def aload_session(self, path: str | Path) -> LoginResult:
        """Load a saved session without blocking the event loop."""

        tokens = await asyncio.to_thread(load_session_file, path)
        self._tokens = tokens
        self._pending_totp = None
        return tokens

    def clear_session(self, path: str | Path) -> None:
        """Delete a saved session file and clear the in-memory login state."""

        clear_session_file(path)
        self._tokens = None
        self._pending_totp = None

    async def aclear_session(self, path: str | Path) -> None:
        """Clear a saved session without blocking the event loop."""

        await asyncio.to_thread(clear_session_file, path)
        self._tokens = None
        self._pending_totp = None
