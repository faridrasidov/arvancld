# tests/test_transport.py
"""Low-level response parsing tests."""

from __future__ import annotations

import httpx
import pytest
from pydantic import BaseModel

from arvancld import APIError, APIValidationIssue, InvalidResponseError
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


def test_api_error_exposes_bounded_fastapi_validation_metadata() -> None:
    secret_values = {
        "password": "password-do-not-log",
        "otp": "246810",
        "access": "access-token-do-not-log",
        "refresh": "refresh-token-do-not-log",
        "flow": "flow-token-do-not-log",
        "message": "provider-message-do-not-log",
    }
    body = {
        "detail": [
            {
                "loc": ["body", "otp_code"],
                "type": "string_pattern_mismatch",
                "msg": secret_values["message"],
                "input": secret_values,
            }
        ],
        "message": secret_values["message"],
    }
    response = httpx.Response(
        422,
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "X-Request-Id": "request-validation",
        },
        json=body,
    )

    with pytest.raises(APIError) as captured:
        _parse_model(response, SampleResponse)

    error = captured.value
    assert error.response_content_type == "application/json"
    assert error.response_size == len(response.content)
    assert error.response_fields == ("detail", "message")
    assert error.validation_issues == (
        APIValidationIssue(("body", "otp_code"), "string_pattern_mismatch"),
    )
    rendered = repr(error)
    diagnostics = repr(
        (
            error.response_fields,
            error.validation_issues,
            error.response_content_type,
        )
    )
    for secret in secret_values.values():
        assert secret not in rendered
        assert secret not in diagnostics


@pytest.mark.parametrize("field_container", ["detail", "errors"])
def test_api_error_sanitizes_field_error_dictionaries(field_container: str) -> None:
    response = httpx.Response(
        422,
        headers={"Content-Type": "application/problem+json"},
        json={
            field_container: {
                "otp_code": {
                    "type": "value_error",
                    "message": "rejected 246810 flow-token-do-not-log",
                },
                "unsafe field/value": "provider-message-do-not-log",
                "email": ["email-do-not-log@example.test"],
            }
        },
    )

    with pytest.raises(APIError) as captured:
        _parse_model(response, SampleResponse)

    assert captured.value.validation_issues == (
        APIValidationIssue(("otp_code",), "value_error"),
        APIValidationIssue(("email",), "field_error"),
    )
    assert "246810" not in repr(captured.value.validation_issues)
    assert "email-do-not-log@example.test" not in repr(captured.value.validation_issues)


def test_api_error_non_json_only_exposes_type_and_size() -> None:
    response = httpx.Response(
        502,
        headers={"Content-Type": "text/html; charset=utf-8"},
        content=b"<html>provider-message-do-not-log</html>",
    )

    with pytest.raises(APIError) as captured:
        _parse_model(response, SampleResponse)

    error = captured.value
    assert error.response_content_type == "text/html"
    assert error.response_size == len(response.content)
    assert error.response_fields == ()
    assert error.validation_issues == ()
    assert "provider-message-do-not-log" not in repr(error)


def test_api_error_diagnostics_are_bounded_and_tolerate_malformed_data() -> None:
    body = {
        **{f"field_{index}": index for index in range(20)},
        "detail": [
            {"loc": ["body", f"field_{index}"], "type": "value_error"} for index in range(20)
        ],
    }
    response = httpx.Response(422, json=body)

    with pytest.raises(APIError) as captured:
        _parse_model(response, SampleResponse)

    assert len(captured.value.response_fields) == 16
    assert len(captured.value.validation_issues) == 10

    oversized = httpx.Response(
        422,
        headers={"Content-Type": "application/json"},
        content=b"{" + b'"secret":"' + (b"x" * (64 * 1024)) + b'"}',
    )
    with pytest.raises(APIError) as oversized_captured:
        _parse_model(oversized, SampleResponse)
    assert oversized_captured.value.response_fields == ()
    assert oversized_captured.value.validation_issues == ()

    malformed = httpx.Response(
        422,
        headers={"Content-Type": "application/json"},
        content=b'{"detail":',
    )
    with pytest.raises(APIError) as malformed_captured:
        _parse_model(malformed, SampleResponse)
    assert malformed_captured.value.response_fields == ()
    assert malformed_captured.value.validation_issues == ()
