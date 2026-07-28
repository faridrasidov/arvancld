# src/arvancld/_transport.py
"""Internal synchronous and asynchronous HTTP transports."""

from __future__ import annotations

import asyncio
import math
import random
import time
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from arvancld.config import ClientConfig, RetryPolicy
from arvancld.exceptions import (
    APIError,
    ArvanCloudTimeoutError,
    AuthenticationError,
    InvalidResponseError,
    NetworkError,
)

ModelT = TypeVar("ModelT", bound=BaseModel)


def _retry_after_seconds(value: str, *, now: datetime | None = None) -> float | None:
    try:
        seconds = float(value)
    except ValueError:
        try:
            retry_at = parsedate_to_datetime(value)
        except (TypeError, ValueError, OverflowError):
            return None
        if retry_at.tzinfo is None or retry_at.utcoffset() is None:
            retry_at = retry_at.replace(tzinfo=UTC)
        current_time = now if now is not None else datetime.now(UTC)
        return max(0.0, (retry_at - current_time).total_seconds())

    if not math.isfinite(seconds):
        return None
    return max(0.0, seconds)


def _retry_delay(
    policy: RetryPolicy,
    *,
    attempt: int,
    response: httpx.Response | None = None,
) -> float:
    if response is not None:
        retry_after = response.headers.get("Retry-After")
        if retry_after is not None:
            seconds = _retry_after_seconds(retry_after)
            if seconds is not None:
                return min(seconds, policy.max_retry_after)

    upper_bound = min(
        policy.max_backoff,
        policy.backoff_factor * (2 ** (attempt - 1)),
    )
    return random.uniform(0.0, upper_bound)


def _max_attempts(method: str, policy: RetryPolicy | None) -> int:
    if method.upper() != "GET" or policy is None:
        return 1
    return policy.max_attempts


def _is_retryable_transport_error(exc: httpx.RequestError) -> bool:
    return isinstance(
        exc,
        (httpx.TimeoutException, httpx.NetworkError, httpx.RemoteProtocolError),
    )


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
        return model.model_validate_json(response.content)
    except ValidationError as exc:
        if any(error["type"] == "json_invalid" for error in exc.errors()):
            raise InvalidResponseError("ArvanCloud API returned invalid JSON") from None
        raise InvalidResponseError(
            "ArvanCloud API response did not match the expected contract"
        ) from None


class SyncTransport:
    """Owned synchronous HTTP transport."""

    def __init__(self, config: ClientConfig) -> None:
        client_options: dict[str, Any] = {
            "timeout": config.timeout,
            "headers": {
                "Accept": "application/json",
                "User-Agent": config.user_agent,
            },
        }
        if config.limits is not None:
            client_options["limits"] = config.limits

        self._client = httpx.Client(**client_options)
        self._retry_policy = config.retry_policy

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
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> ModelT:
        method = method.upper()
        max_attempts = _max_attempts(method, self._retry_policy)

        for attempt in range(1, max_attempts + 1):
            try:
                response = self._client.request(
                    method,
                    url,
                    json=json,
                    params=params,
                    headers=headers,
                )
            except httpx.RequestError as exc:
                if (
                    attempt < max_attempts
                    and self._retry_policy is not None
                    and _is_retryable_transport_error(exc)
                ):
                    time.sleep(_retry_delay(self._retry_policy, attempt=attempt))
                    continue
                if isinstance(exc, httpx.TimeoutException):
                    raise ArvanCloudTimeoutError("ArvanCloud API request timed out") from None
                raise NetworkError("Could not reach the ArvanCloud API") from None

            if (
                attempt < max_attempts
                and self._retry_policy is not None
                and response.status_code in self._retry_policy.status_codes
            ):
                delay = _retry_delay(
                    self._retry_policy,
                    attempt=attempt,
                    response=response,
                )
                response.close()
                time.sleep(delay)
                continue

            return _parse_model(response, model)

        raise AssertionError("request attempts were exhausted without a result")

    def close(self) -> None:
        self._client.close()


class AsyncTransport:
    """Owned asynchronous HTTP transport."""

    def __init__(self, config: ClientConfig) -> None:
        client_options: dict[str, Any] = {
            "timeout": config.timeout,
            "headers": {
                "Accept": "application/json",
                "User-Agent": config.user_agent,
            },
        }
        if config.limits is not None:
            client_options["limits"] = config.limits

        self._client = httpx.AsyncClient(**client_options)
        self._retry_policy = config.retry_policy

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
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> ModelT:
        method = method.upper()
        max_attempts = _max_attempts(method, self._retry_policy)

        for attempt in range(1, max_attempts + 1):
            try:
                response = await self._client.request(
                    method,
                    url,
                    json=json,
                    params=params,
                    headers=headers,
                )
            except httpx.RequestError as exc:
                if (
                    attempt < max_attempts
                    and self._retry_policy is not None
                    and _is_retryable_transport_error(exc)
                ):
                    await asyncio.sleep(_retry_delay(self._retry_policy, attempt=attempt))
                    continue
                if isinstance(exc, httpx.TimeoutException):
                    raise ArvanCloudTimeoutError("ArvanCloud API request timed out") from None
                raise NetworkError("Could not reach the ArvanCloud API") from None

            if (
                attempt < max_attempts
                and self._retry_policy is not None
                and response.status_code in self._retry_policy.status_codes
            ):
                delay = _retry_delay(
                    self._retry_policy,
                    attempt=attempt,
                    response=response,
                )
                await response.aclose()
                await asyncio.sleep(delay)
                continue

            return _parse_model(response, model)

        raise AssertionError("request attempts were exhausted without a result")

    async def close(self) -> None:
        await self._client.aclose()
