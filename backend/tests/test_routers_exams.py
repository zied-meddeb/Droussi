"""Router tests for /api/exams using a fake Supabase client and stubbed services."""
import pytest

from .conftest import make_content
from .fakes import FakeResp, FakeSupabase

SPEC = {
    "difficulty": "medium",
    "question_types": ["mcq", "open"],
    "num_exercises": 2,
    "total_points": 10,
    "per_exercise_points": [3, 7],
    "export_format": "pdf",
}
EXAM_PENDING = {
    "id": "exam1",
    "user_id": "user123",
    "document_id": "doc1",
    "spec": {},
    "status": "pending",
    "created_at": "2026-07-01T00:00:00+00:00",
}
EXAM_READY = {**EXAM_PENDING, "export_format": "pdf", "export_path": "user123/x.pdf", "status": "ready"}


def _patch_sb(monkeypatch, sb):
    monkeypatch.setattr("app.routers.exams.get_supabase", lambda: sb)


class TestCreateDraft:
    def test_document_not_found_404(self, client, monkeypatch):
        _patch_sb(monkeypatch, FakeSupabase(tables={"documents": [FakeResp(None)]}))
        r = client.post("/api/exams/draft", params={"document_id": "doc1"})
        assert r.status_code == 404

    def test_returns_existing_pending_draft(self, client, monkeypatch):
        sb = FakeSupabase(
            tables={"documents": [FakeResp({"id": "doc1"})], "exams": [FakeResp([EXAM_PENDING])]}
        )
        _patch_sb(monkeypatch, sb)
        r = client.post("/api/exams/draft", params={"document_id": "doc1"})
        assert r.status_code == 200
        assert r.json()["id"] == "exam1"

    def test_creates_new_draft(self, client, monkeypatch):
        sb = FakeSupabase(
            tables={
                "documents": [FakeResp({"id": "doc1"})],
                "exams": [FakeResp([]), FakeResp([EXAM_PENDING])],
            }
        )
        _patch_sb(monkeypatch, sb)
        r = client.post("/api/exams/draft", params={"document_id": "doc1"})
        assert r.status_code == 200

    def test_insert_failure_500(self, client, monkeypatch):
        sb = FakeSupabase(
            tables={"documents": [FakeResp({"id": "doc1"})], "exams": [FakeResp([]), FakeResp([])]}
        )
        _patch_sb(monkeypatch, sb)
        r = client.post("/api/exams/draft", params={"document_id": "doc1"})
        assert r.status_code == 500


class TestGenerate:
    @pytest.fixture(autouse=True)
    def _no_quota_check(self, monkeypatch):
        monkeypatch.setattr(
            "app.routers.exams.usage_service.ensure_can_generate_exam",
            lambda *_a, **_k: None,
        )

    def _stub_generate(self, monkeypatch, behavior):
        async def fake(**_kwargs):
            return behavior()

        monkeypatch.setattr("app.routers.exams.exam_generator.generate_exam", fake)

    def test_too_many_documents_400(self, client, monkeypatch):
        _patch_sb(monkeypatch, FakeSupabase())
        body = {"document_id": "d0", "document_ids": [f"d{i}" for i in range(6)], "spec": SPEC}
        r = client.post("/api/exams/exam1/generate", json=body)
        assert r.status_code == 400

    def test_foreign_exam_returns_404(self, client, monkeypatch):
        # Exam id the caller does not own: ownership pre-check must reject it
        # before any documents are loaded or generation is attempted.
        _patch_sb(monkeypatch, FakeSupabase(tables={"exams": [FakeResp(None)]}))
        r = client.post("/api/exams/exam1/generate", json={"document_id": "doc1", "spec": SPEC})
        assert r.status_code == 404

    def test_documents_not_found_404(self, client, monkeypatch):
        sb = FakeSupabase(
            tables={
                "exams": [FakeResp({"id": "exam1"})],
                "documents": [FakeResp([])],
            }
        )
        _patch_sb(monkeypatch, sb)
        r = client.post("/api/exams/exam1/generate", json={"document_id": "doc1", "spec": SPEC})
        assert r.status_code == 404

    def test_no_extracted_text_422(self, client, monkeypatch):
        sb = FakeSupabase(
            tables={
                "exams": [FakeResp({"id": "exam1"})],
                "documents": [FakeResp([{"id": "doc1", "extracted_text": "  "}])],
            }
        )
        _patch_sb(monkeypatch, sb)
        r = client.post("/api/exams/exam1/generate", json={"document_id": "doc1", "spec": SPEC})
        assert r.status_code == 422

    def test_success(self, client, monkeypatch):
        sb = FakeSupabase(
            tables={
                "documents": [FakeResp([{"id": "doc1", "extracted_text": "course text"}])],
                "exams": [FakeResp({"id": "exam1"}), FakeResp(None), FakeResp([EXAM_READY])],
            }
        )
        _patch_sb(monkeypatch, sb)
        self._stub_generate(monkeypatch, lambda: make_content())
        r = client.post("/api/exams/exam1/generate", json={"document_id": "doc1", "spec": SPEC})
        assert r.status_code == 200
        assert r.json()["status"] == "ready"

    def test_timeout_504(self, client, monkeypatch):
        sb = FakeSupabase(
            tables={
                "documents": [FakeResp([{"id": "doc1", "extracted_text": "course text"}])],
                "exams": [FakeResp({"id": "exam1"}), FakeResp(None), FakeResp(None)],
            }
        )
        _patch_sb(monkeypatch, sb)

        def boom():
            raise TimeoutError()

        self._stub_generate(monkeypatch, boom)
        r = client.post("/api/exams/exam1/generate", json={"document_id": "doc1", "spec": SPEC})
        assert r.status_code == 504

    def test_generation_error_502(self, client, monkeypatch):
        sb = FakeSupabase(
            tables={
                "documents": [FakeResp([{"id": "doc1", "extracted_text": "course text"}])],
                "exams": [FakeResp({"id": "exam1"}), FakeResp(None), FakeResp(None)],
            }
        )
        _patch_sb(monkeypatch, sb)

        def boom():
            raise RuntimeError("model exploded")

        self._stub_generate(monkeypatch, boom)
        r = client.post("/api/exams/exam1/generate", json={"document_id": "doc1", "spec": SPEC})
        assert r.status_code == 502


class TestGenerateAsync:
    @pytest.fixture(autouse=True)
    def _no_quota_check(self, monkeypatch):
        monkeypatch.setattr(
            "app.routers.exams.usage_service.ensure_can_generate_exam",
            lambda *_a, **_k: None,
        )

    def test_foreign_exam_returns_404(self, client, monkeypatch):
        _patch_sb(monkeypatch, FakeSupabase(tables={"exams": [FakeResp(None)]}))
        r = client.post(
            "/api/exams/exam1/generate-async",
            json={"document_id": "doc1", "spec": SPEC},
        )
        assert r.status_code == 404

    def test_accepts_and_returns_generating(self, client, monkeypatch):
        # Prevent the spawned job from actually running during the test.
        monkeypatch.setattr("app.routers.exams.jobs.spawn", lambda coro: coro.close())
        sb = FakeSupabase(
            tables={
                "exams": [
                    FakeResp({"id": "exam1"}),  # ownership check
                    FakeResp(None),             # set generating
                    FakeResp({**EXAM_PENDING, "status": "generating"}),  # read-back
                ],
                "documents": [FakeResp([{"id": "doc1", "extracted_text": "course text"}])],
            }
        )
        _patch_sb(monkeypatch, sb)
        r = client.post(
            "/api/exams/exam1/generate-async",
            json={"document_id": "doc1", "spec": SPEC},
        )
        assert r.status_code == 202
        assert r.json()["status"] == "generating"


class TestGetExam:
    def test_not_found_404(self, client, monkeypatch):
        _patch_sb(monkeypatch, FakeSupabase(tables={"exams": [FakeResp(None)]}))
        r = client.get("/api/exams/exam1")
        assert r.status_code == 404

    def test_returns_exam(self, client, monkeypatch):
        _patch_sb(monkeypatch, FakeSupabase(tables={"exams": [FakeResp(EXAM_READY)]}))
        r = client.get("/api/exams/exam1")
        assert r.status_code == 200
        assert r.json()["status"] == "ready"


class TestUpdateContent:
    def _body(self):
        return {
            "title": "Edited Exam",
            "exercises": [{"type": "open", "question": "q?", "answer": "a", "points": 5}],
        }

    def test_not_found_404(self, client, monkeypatch):
        _patch_sb(monkeypatch, FakeSupabase(tables={"exams": [FakeResp(None)]}))
        r = client.put("/api/exams/exam1/content", json=self._body())
        assert r.status_code == 404

    def test_success(self, client, monkeypatch):
        sb = FakeSupabase(
            tables={"exams": [FakeResp({"export_format": "pdf"}), FakeResp([EXAM_READY])]}
        )
        _patch_sb(monkeypatch, sb)
        r = client.put("/api/exams/exam1/content", json=self._body())
        assert r.status_code == 200


class TestDownloadUrl:
    def test_not_ready_404(self, client, monkeypatch):
        _patch_sb(monkeypatch, FakeSupabase(tables={"exams": [FakeResp(None)]}))
        r = client.get("/api/exams/exam1/download")
        assert r.status_code == 404

    def test_success(self, client, monkeypatch):
        sb = FakeSupabase(
            tables={"exams": [FakeResp({"export_path": "user123/x.pdf"})]},
            signed_url="https://signed.example/x.pdf",
        )
        _patch_sb(monkeypatch, sb)
        r = client.get("/api/exams/exam1/download")
        assert r.status_code == 200
        assert r.json()["url"] == "https://signed.example/x.pdf"

    def test_signing_failure_500(self, client, monkeypatch):
        sb = FakeSupabase(
            tables={"exams": [FakeResp({"export_path": "user123/x.pdf"})]}, signed_url=""
        )
        _patch_sb(monkeypatch, sb)
        r = client.get("/api/exams/exam1/download")
        assert r.status_code == 500
