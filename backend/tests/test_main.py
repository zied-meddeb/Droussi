"""Tests for the top-level app routes."""


class TestHealth:
    def test_health_ok(self, client):
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json() == {"status": "ok"}


class TestMe:
    def test_me_returns_current_user(self, client):
        r = client.get("/api/me")
        assert r.status_code == 200
        body = r.json()
        assert body["id"] == "user123"
        assert body["email"] == "user@test.com"
        assert body["is_admin"] is False
