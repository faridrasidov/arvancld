# src/arvancld/_transport.py
"""Internal synchronous and asynchronous HTTP transports."""

from __future__ import annotations

import asyncio
import json
import math
import random
import re
import time
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from arvancld.config import ClientConfig, RetryPolicy
from arvancld.exceptions import (
    APIError,
    APIValidationIssue,
    ArvanCloudTimeoutError,
    AuthenticationError,
    InvalidResponseError,
    NetworkError,
)

ModelT = TypeVar("ModelT", bound=BaseModel)
MAX_RESPONSE_FIELDS = 16
MAX_VALIDATION_ISSUES = 10
MAX_LOCATION_SEGMENTS = 8
MAX_DIAGNOSTIC_TOKEN_LENGTH = 64
MAX_DIAGNOSTIC_BODY_BYTES = 64 * 1024
_SAFE_DIAGNOSTIC_TOKEN = re.compile(r"^[A-Za-z_][A-Za-z0-9_.:-]{0,63}$")


def _safe_diagnostic_token(value: object) -> str | None:
    if not isinstance(value, str) or len(value) > MAX_DIAGNOSTIC_TOKEN_LENGTH:
        return None
    return value if _SAFE_DIAGNOSTIC_TOKEN.fullmatch(value) else None


def _safe_location(value: object) -> tuple[str | int, ...]:
    if not isinstance(value, (list, tuple)):
        return ()

    result: list[str | int] = []
    for segment in value[:MAX_LOCATION_SEGMENTS]:
        if isinstance(segment, int) and not isinstance(segment, bool) and segment >= 0:
            result.append(segment)
            continue
        safe_segment = _safe_diagnostic_token(segment)
        if safe_segment is None:
            return ()
        result.append(safe_segment)
    return tuple(result)


def _validation_issues(payload: object) -> tuple[APIValidationIssue, ...]:
    if not isinstance(payload, dict):
        return ()

    issues: list[APIValidationIssue] = []
    detail = payload.get("detail")
    if isinstance(detail, list):
        for item in detail:
            if len(issues) >= MAX_VALIDATION_ISSUES:
                break
            if not isinstance(item, dict):
                continue
            location = _safe_location(item.get("loc"))
            error_type = _safe_diagnostic_token(item.get("type"))
            if location and error_type:
                issues.append(APIValidationIssue(location, error_type))

    field_errors = payload.get("errors")
    if not isinstance(field_errors, dict) and isinstance(detail, dict):
        field_errors = detail
    if isinstance(field_errors, dict):
        for field, value in field_errors.items():
            if len(issues) >= MAX_VALIDATION_ISSUES:
                break
            safe_field = _safe_diagnostic_token(field)
            if safe_field is None:
                continue
            error_type = None
            if isinstance(value, dict):
                error_type = _safe_diagnostic_token(value.get("type"))
                if error_type is None:
                    error_type = _safe_diagnostic_token(value.get("code"))
            issues.append(APIValidationIssue((safe_field,), error_type or "field_error"))

    return tuple(issues)


def _error_diagnostics(response: httpx.Response) -> dict[str, object]:
    raw_content_type = response.headers.get("content-type", "")
    content_type = raw_content_type.split(";", 1)[0].strip().lower()
    safe_content_type = (
        content_type[:MAX_DIAGNOSTIC_TOKEN_LENGTH]
        if content_type
        and all(character.isalnum() or character in "/.+-" for character in content_type)
        else None
    )
    diagnostics: dict[str, object] = {
        "response_content_type": safe_content_type,
        "response_size": len(response.content),
    }
    if len(response.content) > MAX_DIAGNOSTIC_BODY_BYTES:
        return diagnostics

    try:
        payload = json.loads(response.content)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return diagnostics
    if not isinstance(payload, dict):
        return diagnostics

    fields: list[str] = []
    for field in payload:
        safe_field = _safe_diagnostic_token(field)
        if safe_field is not None:
            fields.append(safe_field)
        if len(fields) >= MAX_RESPONSE_FIELDS:
            break
    diagnostics["response_fields"] = tuple(fields)
    diagnostics["validation_issues"] = _validation_issues(payload)
    return diagnostics


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
        **_error_diagnostics(response),
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
