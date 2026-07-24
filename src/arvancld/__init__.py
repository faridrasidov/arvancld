"""Public package interface for arvancld."""

from arvancld.auth import LoginResult
from arvancld.client import ArvanCloud, AsyncArvanCloud
from arvancld.config import ClientConfig
from arvancld.exceptions import (
    APIError,
    ArvanCloudError,
    ArvanCloudTimeoutError,
    AuthenticationError,
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
    "ClientConfig",
    "InvalidResponseError",
    "LoginResult",
    "NetworkError",
    "__version__",
]
