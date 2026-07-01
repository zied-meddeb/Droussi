"""Unit tests for the pure quota helpers in the usage service."""
from datetime import date, datetime, timezone

from app.services.usage import UsageSnapshot, _resets_at_utc, _today_utc


def _snapshot(used: int, limit: int) -> UsageSnapshot:
    return UsageSnapshot(
        exams_used=used,
        exams_limit=limit,
        cost_usd_today=0.0,
        usage_date=date(2026, 7, 1),
        resets_at=_resets_at_utc(date(2026, 7, 1)),
    )


class TestUsageSnapshot:
    def test_remaining_is_limit_minus_used(self):
        assert _snapshot(3, 10).remaining == 7

    def test_remaining_never_negative(self):
        assert _snapshot(15, 10).remaining == 0

    def test_percent(self):
        assert _snapshot(5, 10).percent == 50.0

    def test_percent_capped_at_100(self):
        assert _snapshot(20, 10).percent == 100.0

    def test_percent_is_100_when_limit_is_zero(self):
        assert _snapshot(0, 0).percent == 100.0


class TestResetsAt:
    def test_resets_at_next_midnight_utc(self):
        assert _resets_at_utc(date(2026, 7, 1)) == datetime(
            2026, 7, 2, 0, 0, tzinfo=timezone.utc
        )


class TestTodayUtc:
    def test_returns_a_date(self):
        assert isinstance(_today_utc(), date)
