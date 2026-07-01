"""Unit tests for the document text extractor."""
from app.services.exporter import to_pdf
from app.services.pdf_parser import extract_text

from .conftest import make_content, make_exercise


class TestExtractText:
    def test_decodes_plain_text_by_mime_type(self):
        assert extract_text("hello world".encode("utf-8"), "text/plain") == "hello world"

    def test_ignores_invalid_utf8_bytes_for_text(self):
        # errors="ignore" drops the bad byte rather than raising.
        assert extract_text(b"caf\xe9", "text/plain") == "caf"

    def test_markdown_is_treated_as_text(self):
        assert extract_text(b"# Title", "text/markdown") == "# Title"

    def test_extracts_text_from_a_real_pdf(self):
        # Build a genuine PDF with the exporter, then read it back.
        content = make_content(
            exercises=[make_exercise(question="Explain gravity", type="open", choices=None)],
            title="Physics Quiz",
        )
        text = extract_text(to_pdf(content), "application/pdf")
        assert "Physics Quiz" in text

    def test_pdf_with_no_mime_type_uses_pdf_reader(self):
        text = extract_text(to_pdf(make_content(title="Untitled Exam")), None)
        assert "Untitled Exam" in text

