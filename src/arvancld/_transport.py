# src/arvancld/_transport.py
"""Internal synchronous and asynchronous HTTP transports."""

from __future__ import annotations

from typing import Any, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from arvancld.config import ClientConfig
from arvancld.exceptions import (
    APIError,
    ArvanCloudTimeoutError,
    AuthenticationError,
    InvalidResponseError,
    NetworkError,
)

ModelT = TypeVar("ModelT", bound=BaseModel)


def _raise_for_api_error(response: httpx.Response) -> None:
    if response.status_code < 400:
        return

    error_type = AuthenticationError if response.status_code in {401, 403} else APIError
    message = (
        "ArvanCloud authentication failed"
        if error_type is AuthenticationError
        else "ArvanCloud API request failed"
    )
    raise error_type(
        status_code=response.status_code,
        request_id=response.headers.get("X-Request-Id"),
        message=message,
    )


def _parse_model(response: httpx.Response, model: type[ModelT]) -> ModelT:
    _raise_for_api_error(response)

    try:
        payload = response.json()
    except ValueError:
        raise InvalidResponseError("ArvanCloud API returned invalid JSON") from None

    try:
        return model.model_validate(payload)
    except ValidationError:
        raise InvalidResponseError(
            "ArvanCloud API response did not match the expected contract"
        ) from None


class SyncTransport:
    """Owned synchronous HTTP transport."""

    def __init__(self, config: ClientConfig) -> None:
        self._client = httpx.Client(
            timeout=config.timeout,
            headers={
                "Accept": "application/json",
                "User-Agent": config.user_agent,
            },
        )

    @property
    def is_closed(self) -> bool:
        return self._client.is_closed

    def request_model(
        self,
        method: str,
        url: str,
        *,
        model: type[ModelT],
        json: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> ModelT:
        try:
            response = self._client.request(method, url, json=json, headers=headers)
        except httpx.TimeoutException:
            raise ArvanCloudTimeoutError("ArvanCloud API request timed out") from None
        except httpx.RequestError:
            raise NetworkError("Could not reach the ArvanCloud API") from None

        return _parse_model(response, model)

    def close(self) -> None:
        self._client.close()


class AsyncTransport:
    """Owned asynchronous HTTP transport."""

    def __init__(self, config: ClientConfig) -> None:
        self._client = httpx.AsyncClient(
            timeout=config.timeout,
            headers={
                "Accept": "application/json",
                "User-Agent": config.user_agent,
            },
        )

    @property
    def is_closed(self) -> bool:
        return self._client.is_closed

    async def request_model(
        self,
        method: str,
        url: str,
        *,
        model: type[ModelT],
        json: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> ModelT:
        try:
            response = await self._client.request(method, url, json=json, headers=headers)
        except httpx.TimeoutException:
            raise ArvanCloudTimeoutError("ArvanCloud API request timed out") from None
        except httpx.RequestError:
            raise NetworkError("Could not reach the ArvanCloud API") from None

        return _parse_model(response, model)

    async def close(self) -> None:
        await self._client.aclose()
