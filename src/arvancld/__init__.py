# src/arvancld/__init__.py
"""Public package interface for arvancld."""

from arvancld.auth import LoginResult, StoredSession, TOTPChallenge
from arvancld.cdn import (
    CDNDomain,
    CDNDomainPage,
    DNSRecord,
    DNSRecordCreate,
    DNSRecordDeleteResult,
    DNSRecordIPValue,
    DNSRecordPage,
    DNSRecordType,
    DNSRecordUpdate,
    IPFilterMode,
)
from arvancld.client import ArvanCloud, AsyncArvanCloud
from arvancld.config import ClientConfig, RetryPolicy
from arvancld.exceptions import (
    APIError,
    APIValidationIssue,
    ArvanCloudError,
    ArvanCloudTimeoutError,
    AuthenticationError,
    AuthenticationRequiredError,
    InvalidResponseError,
    InvalidSessionError,
    NetworkError,
    SessionError,
    SessionExpiredError,
    TOTPRequiredError,
)

__version__ = "0.1.0"

__all__ = [
    "APIError",
    "APIValidationIssue",
    "ArvanCloud",
    "ArvanCloudError",
    "ArvanCloudTimeoutError",
    "AsyncArvanCloud",
    "AuthenticationError",
    "AuthenticationRequiredError",
    "CDNDomain",
    "CDNDomainPage",
    "ClientConfig",
    "DNSRecord",
    "DNSRecordCreate",
    "DNSRecordDeleteResult",
    "DNSRecordIPValue",
    "DNSRecordPage",
    "DNSRecordType",
    "DNSRecordUpdate",
    "IPFilterMode",
    "InvalidResponseError",
    "InvalidSessionError",
    "LoginResult",
    "NetworkError",
    "RetryPolicy",
    "SessionError",
    "SessionExpiredError",
    "StoredSession",
    "TOTPChallenge",
    "TOTPRequiredError",
    "__version__",
]
