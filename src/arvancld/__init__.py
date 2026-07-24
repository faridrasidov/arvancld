# src/arvancld/__init__.py
"""Public package interface for arvancld."""

from arvancld.auth import LoginResult
from arvancld.cdn import CDNDomain, CDNDomainPage, DNSRecord, DNSRecordPage
from arvancld.client import ArvanCloud, AsyncArvanCloud
from arvancld.config import ClientConfig
from arvancld.exceptions import (
    APIError,
    ArvanCloudError,
    ArvanCloudTimeoutError,
    AuthenticationError,
    AuthenticationRequiredError,
    InvalidResponseError,
    NetworkError,
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
    "DNSRecordPage",
    "InvalidResponseError",
    "LoginResult",
    "NetworkError",
    "__version__",
]
