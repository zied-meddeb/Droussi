"""Router test for /api/usage."""
from datetime import date, datetime, timezone

from app.services.usage import UsageSnapshot


def test_get_daily_usage(client, monkeypatch):
    snap = UsageSnapshot(
        exams_used=4,
        exams_limit=30,
        cost_usd_today=0.0123456,
        usage_date=date(2026, 7, 1),
        resets_at=datetime(2026, 7, 2, tzinfo=timezone.utc),
    )
    monkeypatch.setattr(
        "app.routers.usage.usage_service.get_usage", lambda *_a, **_k: snap
    )
    r = client.get("/api/usage")
    assert r.status_code == 200
    body = r.json()
    assert body["exams_used"] == 4
    assert body["exams_limit"] == 30
    assert body["remaining"] == 26
    assert body["cost_usd_today"] == 0.012346  # rounded to 6dp
