"""Tests for the top-level app routes."""
from .fakes import FakeResp, FakeSupabase


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


class TestDeleteMe:
    def test_deletes_user_data_and_returns_204(self, client, monkeypatch):
        sb = FakeSupabase(
            tables={
                "documents": [FakeResp([{"storage_path": "user123/a.pdf"}])],
                "exams": [FakeResp([{"export_path": "user123/a.pdf"}])],
            }
        )
        monkeypatch.setattr("app.main.get_supabase", lambda: sb)
        r = client.delete("/api/me")
        assert r.status_code == 204
        # Both the document and the export objects were removed from storage.
        assert sb.storage.removed == [["user123/a.pdf"], ["user123/a.pdf"]]
