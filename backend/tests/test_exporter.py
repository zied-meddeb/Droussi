"""Unit tests for the DOCX/PDF exporters — assert they render valid file bytes."""
from app.services.exporter import to_docx, to_pdf

from .conftest import make_content, make_exercise


class TestToDocx:
    def test_returns_docx_zip_bytes(self):
        data = to_docx(make_content())
        # .docx is a ZIP container — starts with the PK magic number.
        assert data[:2] == b"PK"
        assert len(data) > 0

    def test_handles_open_questions_without_choices(self):
        content = make_content(
            exercises=[make_exercise(type="open", choices=None, explanation=None)]
        )
        assert to_docx(content)[:2] == b"PK"


class TestToPdf:
    def test_returns_pdf_bytes(self):
        data = to_pdf(make_content())
        assert data[:4] == b"%PDF"

    def test_handles_missing_title(self):
        content = make_content(title="")
        assert to_pdf(content)[:4] == b"%PDF"
