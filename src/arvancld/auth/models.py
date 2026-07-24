"""Typed account-authentication response models."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class LoginResult(BaseModel):
    """Credentials and account routing information returned by login."""

    model_config = ConfigDict(extra="ignore", frozen=True, populate_by_name=True)

    access_token: str = Field(alias="accessToken", repr=False)
    refresh_token: str = Field(alias="refreshToken", repr=False)
    expires_at: datetime = Field(alias="expiresAt")
    default_account: UUID = Field(alias="defaultAccount")
    flow: str
    next: str

    @field_validator("expires_at")
    @classmethod
    def ensure_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("expiresAt must include a timezone")
        return value


class LoginResponse(BaseModel):
    """Envelope returned by the account login endpoint."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    data: LoginResult
