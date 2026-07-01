"""Tests for the usage/quota service with a fake Supabase client."""
import pytest
from fastapi import HTTPException

from app.services import usage as usage_service

from .fakes import FakeResp, FakeSupabase


def _patch(monkeypatch, sb):
    monkeypatch.setattr("app.services.usage.get_supabase", lambda: sb)


class TestPerUserLimit:
    def test_returns_configured_limit(self):
        assert usage_service.per_user_limit() == 30


class TestGetUsage:
    def test_reads_existing_daily_row(self, monkeypatch):
        sb = FakeSupabase(
            tables={
                "app_users": [FakeResp(None)],
                "user_daily_usage": [FakeResp({"exam_count": 3, "cost_usd": 0.05})],
            }
        )
        _patch(monkeypatch, sb)
        snap = usage_service.get_usage("user123", "u@test.com")
        assert snap.exams_used == 3
        assert snap.cost_usd_today == 0.05
        assert snap.exams_limit == 30

    def test_creates_row_when_missing(self, monkeypatch):
        sb = FakeSupabase(
            tables={
                "app_users": [FakeResp(None)],
                "user_daily_usage": [FakeResp(None), FakeResp([{"exam_count": 0, "cost_usd": 0}])],
            }
        )
        _patch(monkeypatch, sb)
        assert usage_service.get_usage("user123").exams_used == 0


class TestGlobalCapacity:
    def test_raises_503_when_budget_exhausted(self, monkeypatch):
        sb = FakeSupabase(tables={"user_daily_usage": [FakeResp([{"cost_usd": 6.0}])]})
        _patch(monkeypatch, sb)
        with pytest.raises(HTTPException) as exc:
            usage_service.ensure_global_capacity()
        assert exc.value.status_code == 503

    def test_ok_when_under_budget(self, monkeypatch):
        sb = FakeSupabase(tables={"user_daily_usage": [FakeResp([{"cost_usd": 1.0}])]})
        _patch(monkeypatch, sb)
        usage_service.ensure_global_capacity()  # no raise


class TestEnsureCanGenerate:
    def test_raises_429_when_quota_reached(self, monkeypatch):
        sb = FakeSupabase(
            tables={
                "app_users": [FakeResp(None)],
                "user_daily_usage": [
                    FakeResp([{"cost_usd": 0.1}]),  # global_cost_today
                    FakeResp({"exam_count": 30, "cost_usd": 0.1}),  # daily row
                ],
            }
        )
        _patch(monkeypatch, sb)
        with pytest.raises(HTTPException) as exc:
            usage_service.ensure_can_generate_exam("user123")
        assert exc.value.status_code == 429

    def test_allows_when_under_quota(self, monkeypatch):
        sb = FakeSupabase(
            tables={
                "app_users": [FakeResp(None)],
                "user_daily_usage": [
                    FakeResp([{"cost_usd": 0.1}]),
                    FakeResp({"exam_count": 2, "cost_usd": 0.1}),
                ],
            }
        )
        _patch(monkeypatch, sb)
        assert usage_service.ensure_can_generate_exam("user123").exams_used == 2


class TestRecording:
    def test_record_exam_increments(self, monkeypatch):
        sb = FakeSupabase(
            tables={
                "app_users": [FakeResp(None)],
                "user_daily_usage": [FakeResp({"exam_count": 1, "cost_usd": 0.0}), FakeResp(None)],
            }
        )
        _patch(monkeypatch, sb)
        usage_service.record_exam("user123", 0.01)  # no raise

    def test_record_cost_ignores_zero(self, monkeypatch):
        # Zero cost returns early — no Supabase interaction needed.
        _patch(monkeypatch, FakeSupabase())
        usage_service.record_cost("user123", 0.0)


class TestAdminAggregation:
    def test_rankings_and_totals(self, monkeypatch):
        sb = FakeSupabase(
            tables={
                "user_daily_usage": [
                    FakeResp(
                        [
                            {"user_id": "u1", "usage_date": "2000-01-01", "exam_count": 2, "cost_usd": 0.2},
                            {"user_id": "u2", "usage_date": "2000-01-01", "exam_count": 5, "cost_usd": 0.5},
                        ]
                    )
                ],
                "app_users": [FakeResp([{"user_id": "u1", "email": "u1@test.com"}])],
            }
        )
        _patch(monkeypatch, sb)
        rankings = usage_service.admin_user_rankings()
        # Ranked by total cost descending -> u2 first.
        assert rankings[0]["user_id"] == "u2"
        assert rankings[0]["cost_usd_total"] == 0.5

    def test_admin_totals_rollup(self, monkeypatch):
        sb = FakeSupabase(
            tables={
                "user_daily_usage": [
                    FakeResp([{"user_id": "u1", "usage_date": "2000-01-01", "exam_count": 3, "cost_usd": 0.3}])
                ],
                "app_users": [FakeResp([])],
            }
        )
        _patch(monkeypatch, sb)
        totals = usage_service.admin_totals()
        assert totals["user_count"] == 1
        assert totals["exams_total"] == 3
