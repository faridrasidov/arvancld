# src/arvancld/exceptions.py
"""Stable, credential-safe exceptions raised by arvancld."""

from __future__ import annotations


class ArvanCloudError(Exception):
    """Base class for all arvancld errors."""


class APIError(ArvanCloudError):
    """The remote API returned a non-success response."""

    def __init__(
        self,
        *,
        status_code: int,
        request_id: str | None = None,
        message: str = "ArvanCloud API request failed",
    ) -> None:
        self.status_code = status_code
        self.request_id = request_id

        details = [f"status={status_code}"]
        if request_id:
            details.append(f"request_id={request_id}")
        super().__init__(f"{message} ({', '.join(details)})")


class AuthenticationError(APIError):
    """Authentication was rejected by the remote API."""


class AuthenticationRequiredError(ArvanCloudError):
    """A request requires a prior successful login."""


class NetworkError(ArvanCloudError):
    """The request could not reach the remote API."""


class ArvanCloudTimeoutError(NetworkError):
    """The request exceeded the configured timeout."""


class InvalidResponseError(ArvanCloudError):
    """The API response was not valid JSON or did not match its contract."""
