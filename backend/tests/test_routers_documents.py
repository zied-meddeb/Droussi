"""Router tests for /api/documents using a fake Supabase client."""
import pytest

from .fakes import FakeResp, FakeSupabase

DOC_ROW = {
    "id": "doc1",
    "user_id": "user123",
    "filename": "notes.txt",
    "storage_path": "user123/notes.txt",
    "mime_type": "text/plain",
    "size_bytes": 11,
    "created_at": "2026-07-01T00:00:00+00:00",
}


def _patch_sb(monkeypatch, sb):
    monkeypatch.setattr("app.routers.documents.get_supabase", lambda: sb)


def _register_body(**over):
    body = {
        "filename": "notes.txt",
        "storage_path": "user123/notes.txt",
        "mime_type": "text/plain",
        "size_bytes": 11,
    }
    body.update(over)
    return body


class TestRegisterDocument:
    def test_success(self, client, monkeypatch):
        sb = FakeSupabase(tables={"documents": [FakeResp([DOC_ROW])]}, download=b"hello world")
        _patch_sb(monkeypatch, sb)
        r = client.post("/api/documents/register", json=_register_body())
        assert r.status_code == 200
        assert r.json()["id"] == "doc1"

    def test_rejects_foreign_storage_path(self, client, monkeypatch):
        _patch_sb(monkeypatch, FakeSupabase())
        r = client.post(
            "/api/documents/register",
            json=_register_body(storage_path="someone-else/notes.txt"),
        )
        assert r.status_code == 403

    @pytest.mark.parametrize(
        "bad_path",
        [
            "user123/../someone-else/secret.pdf",  # traversal to a sibling folder
            "user123/../../etc/passwd",            # traversal above the bucket root
            "/user123/notes.txt",                  # absolute path
            "user123\\notes.txt",                  # windows separator
            "user123",                             # no object segment, folder only
            "user1234/notes.txt",                  # prefix collision, not the real id
        ],
    )
    def test_rejects_path_traversal(self, client, monkeypatch, bad_path):
        # A malicious path is rejected before any (RLS-bypassing) download runs.
        _patch_sb(monkeypatch, FakeSupabase(download=b"should-not-be-read"))
        r = client.post(
            "/api/documents/register",
            json=_register_body(storage_path=bad_path),
        )
        assert r.status_code == 403

    def test_download_failure_returns_400(self, client, monkeypatch):
        sb = FakeSupabase(download=RuntimeError("no such object"))
        _patch_sb(monkeypatch, sb)
        r = client.post("/api/documents/register", json=_register_body())
        assert r.status_code == 400

    def test_unparseable_document_returns_422(self, client, monkeypatch):
        sb = FakeSupabase(download=b"%PDF broken bytes")
        _patch_sb(monkeypatch, sb)
        r = client.post(
            "/api/documents/register",
            json=_register_body(mime_type="application/pdf"),
        )
        assert r.status_code == 422

    def test_rejects_unsupported_mime_type(self, client, monkeypatch):
        _patch_sb(monkeypatch, FakeSupabase(download=b"data"))
        r = client.post(
            "/api/documents/register",
            json=_register_body(mime_type="image/png"),
        )
        assert r.status_code == 415

    def test_rejects_oversized_declared_size(self, client, monkeypatch):
        _patch_sb(monkeypatch, FakeSupabase(download=b"data"))
        r = client.post(
            "/api/documents/register",
            json=_register_body(size_bytes=100 * 1024 * 1024),
        )
        assert r.status_code == 413

    def test_insert_failure_returns_500(self, client, monkeypatch):
        sb = FakeSupabase(tables={"documents": [FakeResp([])]}, download=b"hello world")
        _patch_sb(monkeypatch, sb)
        r = client.post("/api/documents/register", json=_register_body())
        assert r.status_code == 500


class TestDeleteDocument:
    def test_not_found_returns_404(self, client, monkeypatch):
        _patch_sb(monkeypatch, FakeSupabase(tables={"documents": [FakeResp(None)]}))
        r = client.delete("/api/documents/doc1")
        assert r.status_code == 404

    def test_success_returns_204(self, client, monkeypatch):
        sb = FakeSupabase(
            tables={"documents": [FakeResp({"storage_path": "user123/notes.txt"})]}
        )
        _patch_sb(monkeypatch, sb)
        r = client.delete("/api/documents/doc1")
        assert r.status_code == 204
