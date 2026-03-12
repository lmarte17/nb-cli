from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class ErrorPayload:
    error_type: str
    message: str
    details: Any | None = None


class NBCLIError(Exception):
    exit_code = 8
    error_type = "internal_error"

    def __init__(self, message: str, *, details: Any | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details

    def to_payload(self) -> ErrorPayload:
        return ErrorPayload(
            error_type=self.error_type,
            message=self.message,
            details=self.details,
        )


class UsageError(NBCLIError):
    exit_code = 2
    error_type = "usage_error"


class ConfigError(NBCLIError):
    exit_code = 2
    error_type = "config_error"


class AuthError(NBCLIError):
    exit_code = 3
    error_type = "auth_error"


class NotFoundError(NBCLIError):
    exit_code = 4
    error_type = "not_found"


class ValidationError(NBCLIError):
    exit_code = 5
    error_type = "validation_error"


class APIError(NBCLIError):
    exit_code = 6
    error_type = "api_error"


class ConnectivityError(NBCLIError):
    exit_code = 7
    error_type = "connectivity_error"
