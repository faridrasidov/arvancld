# tests/test_transport.py
"""Low-level response parsing tests."""

from __future__ import annotations

import httpx
import pytest
from pydantic import BaseModel

from arvancld import APIError, InvalidResponseError
from arvancld._transport import _parse_model


class SampleResponse(BaseModel):
    value: int


def test_parse_model_validates_response_bytes_directly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_if_called(response: httpx.Response) -> object:
        raise AssertionError("response.json() should not be called")

    monkeypatch.setattr(httpx.Response, "json", fail_if_called)

    parsed = _parse_model(
        httpx.Response(200, content=b'{"value": 42}'),
        SampleResponse,
    )

    assert parsed.value == 42


def test_parse_model_distinguishes_invalid_json_from_schema_mismatch() -> None:
    with pytest.raises(InvalidResponseError, match="invalid JSON"):
        _parse_model(httpx.Response(200, content=b"{"), SampleResponse)

    with pytest.raises(InvalidResponseError, match="expected contract"):
        _parse_model(
            httpx.Response(200, content=b'{"value": "not-an-integer"}'),
            SampleResponse,
        )


def test_parse_model_raises_api_error_before_parsing_body() -> None:
    response = httpx.Response(
        503,
        headers={"X-Request-Id": "request-before-parse"},
        content=b"{",
    )

    with pytest.raises(APIError) as captured:
        _parse_model(response, SampleResponse)

    assert captured.value.status_code == 503
    assert captured.value.request_id == "request-before-parse"
