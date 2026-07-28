# src/arvancld/__init__.py
"""Public package interface for arvancld."""

from arvancld.auth import LoginResult, StoredSession
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
    ArvanCloudError,
    ArvanCloudTimeoutError,
    AuthenticationError,
    AuthenticationRequiredError,
    InvalidResponseError,
    InvalidSessionError,
    NetworkError,
    SessionError,
    SessionExpiredError,
)

__version__ = "0.1.0"

__all__ = [
    "APIError",
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
    "__version__",
]
