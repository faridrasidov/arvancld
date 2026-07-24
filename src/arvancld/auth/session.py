# src/arvancld/auth/session.py
"""Explicit JSON session persistence helpers."""

from __future__ import annotations

import json
import os
import tempfile
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from arvancld.auth.models import LoginResult
from arvancld.exceptions import InvalidSessionError, SessionError, SessionExpiredError

SESSION_SCHEMA_VERSION = 1


class StoredSession(BaseModel):
    """Versioned plaintext session file envelope."""

    model_config = ConfigDict(extra="ignore", frozen=True, populate_by_name=True)

    schema_version: Literal[1] = Field(alias="schemaVersion")
    data: LoginResult


def save_session_file(path: str | Path, tokens: LoginResult) -> None:
    """Write login tokens to a plaintext JSON file atomically."""

    session_path = Path(path)
    parent = session_path.parent

    payload = StoredSession(
        schema_version=SESSION_SCHEMA_VERSION,
        data=tokens,
    ).model_dump_json(by_alias=True, indent=2)

    temp_path: str | None = None
    try:
        parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            "w",
            delete=False,
            dir=parent,
            encoding="utf-8",
            newline="\n",
            prefix=f".{session_path.name}.",
            suffix=".tmp",
        ) as handle:
            temp_path = handle.name
            _chmod_owner_only(Path(temp_path))
            handle.write(payload)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())

        os.replace(temp_path, session_path)
        _chmod_owner_only(session_path)
    except OSError as exc:
        if temp_path is not None:
            with suppress(OSError):
                Path(temp_path).unlink(missing_ok=True)
        raise SessionError("Could not write ArvanCloud session file") from exc


def load_session_file(path: str | Path) -> LoginResult:
    """Load, validate, and return an unexpired saved login session."""

    session_path = Path(path)
    try:
        content = session_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise
    except OSError as exc:
        raise SessionError("Could not read ArvanCloud session file") from exc

    try:
        payload = json.loads(content)
    except json.JSONDecodeError:
        raise InvalidSessionError("Saved ArvanCloud session is not valid JSON") from None

    try:
        session = StoredSession.model_validate(payload)
    except ValidationError:
        raise InvalidSessionError(
            "Saved ArvanCloud session did not match the expected schema"
        ) from None

    if session.data.expires_at <= datetime.now(UTC):
        raise SessionExpiredError("Saved ArvanCloud session has expired")

    return session.data


def clear_session_file(path: str | Path) -> None:
    """Remove a saved session file if it exists."""

    session_path = Path(path)
    try:
        session_path.unlink(missing_ok=True)
    except OSError as exc:
        raise SessionError("Could not clear ArvanCloud session file") from exc


def _chmod_owner_only(path: Path) -> None:
    with suppress(OSError):
        os.chmod(path, 0o600)
