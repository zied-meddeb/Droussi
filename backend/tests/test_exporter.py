"""Unit tests for the DOCX/PDF exporters — assert they render valid file bytes."""
from app.services.exporter import _pdf_text, to_docx, to_pdf

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

    def test_renders_content_with_markup_characters(self):
        # Angle brackets / ampersands from the LLM must not break rendering.
        content = make_content(
            exercises=[
                make_exercise(
                    question="Is 3 < 5 & 2 > 1?",
                    answer="Yes <b>always</b>",
                    explanation="Because a < b & c",
                    choices=["a < b", "c > d"],
                )
            ]
        )
        assert to_pdf(content)[:4] == b"%PDF"


class TestPdfTextEscaping:
    def test_escapes_markup_characters(self):
        assert _pdf_text("a < b & c > d") == "a &lt; b &amp; c &gt; d"

    def test_keeps_linebreaks_only_when_requested(self):
        assert _pdf_text("one\ntwo", keep_linebreaks=True) == "one<br/>two"
        assert _pdf_text("one\ntwo") == "one\ntwo"

    def test_handles_none(self):
        assert _pdf_text(None) == ""
