"""Exporters return bytes callers can hand straight to a download."""

from cv_tailor.adapters.exporters import to_docx, to_html, to_pdf, to_txt

MARKDOWN = "# Title\n\n- **bold** item\n- plain item\n"
NESTED = """### Title

#### Section

*   **Job** | Company
    *   Detail one
    *   Detail two
"""


def _docx_text(markdown_text: str) -> str:
    from io import BytesIO

    from docx import Document

    return "\n".join(p.text for p in Document(BytesIO(to_docx(markdown_text))).paragraphs)


def test_docx_keeps_headings_below_level_three() -> None:
    """h4 has no direct Word style: it must be clamped, not dropped."""
    assert "Section" in _docx_text(NESTED)


def test_docx_keeps_nested_list_items() -> None:
    text = _docx_text(NESTED)
    assert "Detail one" in text
    assert "Detail two" in text


def test_docx_and_txt_carry_the_same_words() -> None:
    """The three exports must not differ in substance."""
    docx_words = set(_docx_text(NESTED).split())
    txt_words = set(to_txt(NESTED).decode().replace("#", " ").replace("*", " ").split())
    assert txt_words - docx_words - {"|"} == set()


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
