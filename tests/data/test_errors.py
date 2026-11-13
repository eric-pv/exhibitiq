"""Tests for crawler.errors (D1-07)."""
from __future__ import annotations

import pytest

from crawler.errors import RETRYABLE_BY_DEFAULT, CrawlError, ErrorCode


def test_every_code_has_a_retry_default() -> None:
    assert set(RETRYABLE_BY_DEFAULT) == set(ErrorCode)


def test_retryable_defaults_follow_the_code_and_can_be_overridden() -> None:
    assert CrawlError(ErrorCode.TIMEOUT, "slow").retryable is True
    assert CrawlError(ErrorCode.ACCESS_BLOCKED, "403").retryable is False
    assert CrawlError(ErrorCode.TIMEOUT, "slow", retryable=False).retryable is False


def test_error_sample_contains_only_contract_fields_and_omits_absent_ones() -> None:
    minimal = CrawlError(ErrorCode.PARSE_ERROR, "no table found")
    assert minimal.to_error_sample() == {"code": "parse_error", "message": "no table found"}
    full = CrawlError(
        ErrorCode.HTTP_ERROR,
        "bad status",
        url="https://www.example.com/x",
        occurred_at="2026-11-03T06:00:00Z",
        http_status=500,
    )
    assert full.to_error_sample() == {
        "code": "http_error",
        "message": "bad status",
        "url": "https://www.example.com/x",
        "occurred_at": "2026-11-03T06:00:00Z",
    }


def test_log_fields_keep_the_extra_detail() -> None:
    err = CrawlError(ErrorCode.HTTP_ERROR, "bad", url="https://www.example.com/x", http_status=500)
    assert err.to_log_fields() == {
        "code": "http_error",
        "retryable": False,
        "url": "https://www.example.com/x",
        "http_status": 500,
    }


@pytest.mark.parametrize("message", ["", "   "])
def test_empty_message_is_rejected(message: str) -> None:
    with pytest.raises(ValueError):
        CrawlError(ErrorCode.UNEXPECTED, message)
