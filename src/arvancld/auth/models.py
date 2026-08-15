# src/arvancld/auth/models.py
"""Typed account-authentication response models."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
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


class TOTPChallenge(BaseModel):
    """Pending time-based one-time-password challenge returned by login."""

    model_config = ConfigDict(extra="ignore", frozen=True, populate_by_name=True)

    flow: str = Field(min_length=1)
    next: Literal["ChallengeTOTPPossession"]
    flow_token: str = Field(alias="flowToken", min_length=1, repr=False)


class LoginResponse(BaseModel):
    """Envelope returned by the account login endpoint."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    data: LoginResult | TOTPChallenge


class ChallengeResponse(BaseModel):
    """Envelope returned after a successful authentication challenge."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    data: LoginResult


class RefreshResult(BaseModel):
    """Rotated credentials returned by the token refresh endpoint."""

    model_config = ConfigDict(extra="ignore", frozen=True, populate_by_name=True)

    access_token: str = Field(alias="accessToken", min_length=1, repr=False)
    refresh_token: str = Field(alias="refreshToken", min_length=1, repr=False)
    expires_at: datetime = Field(alias="expiresAt")

    @field_validator("expires_at")
    @classmethod
    def ensure_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("expiresAt must include a timezone")
        return value


class RefreshResponse(BaseModel):
    """Envelope returned by the token refresh endpoint."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    data: RefreshResult
