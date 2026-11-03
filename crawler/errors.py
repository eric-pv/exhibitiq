"""Structured crawl errors (D1-07).

One error shape for every crawler. A ``CrawlError`` carries enough detail for
the run log, and can be reduced to the small ``error_samples`` item that the
shared ``crawl_run`` contract allows (``code``, ``message``, ``url``,
``occurred_at``). Extra detail (HTTP status, retryability) stays in the run
log only, because the contract is ``additionalProperties: false``.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class ErrorCode(StrEnum):
    CONFIG_INVALID = "config_invalid"
    NETWORK_ERROR = "network_error"
    TIMEOUT = "timeout"
    HTTP_ERROR = "http_error"
    ACCESS_BLOCKED = "access_blocked"  # 403/429, captcha, anti-bot: stop and report, never evade
    PARSE_ERROR = "parse_error"
    UNEXPECTED = "unexpected"


# Whether retrying the same request may help. A default only; callers may override.
RETRYABLE_BY_DEFAULT: dict[ErrorCode, bool] = {
    ErrorCode.CONFIG_INVALID: False,
    ErrorCode.NETWORK_ERROR: True,
    ErrorCode.TIMEOUT: True,
    ErrorCode.HTTP_ERROR: False,
    ErrorCode.ACCESS_BLOCKED: False,
    ErrorCode.PARSE_ERROR: False,
    ErrorCode.UNEXPECTED: False,
}


@dataclass(frozen=True)
class CrawlError:
    code: ErrorCode
    message: str
    url: str | None = None
    occurred_at: str | None = None  # UTC RFC 3339 ending in "Z"; RunLog fills it if missing
    http_status: int | None = None
    retryable: bool | None = None  # None -> RETRYABLE_BY_DEFAULT[code]

    def __post_init__(self) -> None:
        if not isinstance(self.message, str) or not self.message.strip():
            raise ValueError("CrawlError.message must be a non-empty string")
        if self.retryable is None:
            object.__setattr__(self, "retryable", RETRYABLE_BY_DEFAULT[ErrorCode(self.code)])

    def to_error_sample(self) -> dict[str, str]:
        """The subset allowed in crawl_run.error_samples; absent fields are omitted, not null."""
        sample = {"code": str(self.code), "message": self.message}
        if self.url is not None:
            sample["url"] = self.url
        if self.occurred_at is not None:
            sample["occurred_at"] = self.occurred_at
        return sample

    def to_log_fields(self) -> dict[str, Any]:
        """Full detail for the run log (absent fields omitted)."""
        fields: dict[str, Any] = {"code": str(self.code), "retryable": self.retryable}
        if self.url is not None:
            fields["url"] = self.url
        if self.http_status is not None:
            fields["http_status"] = self.http_status
        return fields
