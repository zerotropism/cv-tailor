"""Markdown to DOCX, PDF and plain text. Callers get bytes, never library objects."""

from io import BytesIO

from bs4 import BeautifulSoup, Tag
from docx import Document
from docx.shared import RGBColor
from markdown import markdown

MARKDOWN_EXTENSIONS = ["extra", "nl2br"]
MAX_HEADING_LEVEL = 6
BULLET_STYLES = {"ul": "List Bullet", "ol": "List Number"}


def to_html(markdown_text: str) -> str:
    """Shared by the DOCX and PDF paths, so both render the same Markdown features."""
    return markdown(markdown_text, extensions=MARKDOWN_EXTENSIONS)


def _parse_inline_elements(element, paragraph):
    """Add a tag's inline content to a Word paragraph, skipping nested block elements."""
    for content in element.children:
        if isinstance(content, str):
            paragraph.add_run(content)
        elif content.name in ("strong", "b"):
            run = paragraph.add_run(content.get_text())
            run.bold = True
        elif content.name in ("em", "i"):
            run = paragraph.add_run(content.get_text())
            run.italic = True
        elif content.name == "code":
            run = paragraph.add_run(content.get_text())
            run.font.name = "Courier New"
        elif content.name == "a":
            run = paragraph.add_run(content.get_text())
            run.font.color.rgb = RGBColor(0, 0, 255)
            run.underline = True


def _add_list(doc, list_tag, depth: int = 0) -> None:
    """Add a list and its nested sublists. python-docx styles go up to 'List Bullet 3'."""
    style = BULLET_STYLES[list_tag.name]
    suffix = f" {depth + 1}" if depth else ""

    for item in list_tag.find_all("li", recursive=False):
        paragraph = doc.add_paragraph(style=f"{style}{suffix}")
        _parse_inline_elements(item, paragraph)
        for nested in item.find_all(("ul", "ol"), recursive=False):
            _add_list(doc, nested, depth + 1)


def _to_document(markdown_text: str) -> Document:
    """Build a python-docx Document. Kept private: callers want bytes."""
    soup = BeautifulSoup(to_html(markdown_text), "html.parser")
    doc = Document()

    for element in soup.children:
        if not isinstance(element, Tag):
            continue
        if element.name in BULLET_STYLES:
            _add_list(doc, element)
        elif element.name == "pre":
            doc.add_paragraph(element.get_text(), style="No Spacing")
        elif element.name and element.name.startswith("h") and element.name[1:].isdigit():
            # h4 and beyond exist in Markdown but not as Word styles: clamp to the deepest
            doc.add_heading(element.get_text(), level=min(int(element.name[1:]), MAX_HEADING_LEVEL))
        else:
            paragraph = doc.add_paragraph()
            _parse_inline_elements(element, paragraph)

    return doc


def to_docx(markdown_text: str) -> bytes:
    buffer = BytesIO()
    _to_document(markdown_text).save(buffer)
    return buffer.getvalue()


def to_pdf(markdown_text: str) -> bytes:
    from weasyprint import HTML

    buffer = BytesIO()
    HTML(string=to_html(markdown_text)).write_pdf(buffer)
    return buffer.getvalue()


def to_txt(markdown_text: str) -> bytes:
    return markdown_text.encode("utf-8")
