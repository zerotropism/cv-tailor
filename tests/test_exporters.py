"""Exporters return bytes callers can hand straight to a download."""

from cv_tailor.adapters.exporters import to_docx, to_html, to_pdf, to_txt

MARKDOWN = "# Title\n\n- **bold** item\n- plain item\n"


def test_html_renders_markdown_structure() -> None:
    html = to_html(MARKDOWN)
    assert "<h1>" in html
    assert "<strong>" in html


def test_docx_produces_a_zip_container() -> None:
    """.docx is a zip archive: PK is its magic number."""
    assert to_docx(MARKDOWN).startswith(b"PK")


def test_pdf_produces_a_pdf_header() -> None:
    assert to_pdf(MARKDOWN).startswith(b"%PDF")


def test_txt_is_utf8_and_preserves_accents() -> None:
    assert to_txt("café ☕").decode("utf-8") == "café ☕"
