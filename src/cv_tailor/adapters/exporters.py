"""Markdown to DOCX, PDF and plain text. Callers get bytes, never library objects."""

from io import BytesIO

from bs4 import BeautifulSoup, Tag
from docx import Document
from docx.shared import RGBColor
from markdown import markdown

MARKDOWN_EXTENSIONS = ["extra", "nl2br"]


def to_html(markdown_text: str) -> str:
    """Shared by the DOCX and PDF paths, so both render the same Markdown features."""
    return markdown(markdown_text, extensions=MARKDOWN_EXTENSIONS)


def _parse_inline_elements(element, paragraph):
    """
    Parse les éléments inline (gras, italique, liens) et les ajoute au paragraphe.

    Args:
        element: L'élément BeautifulSoup à parser
        paragraph: Le paragraphe Word où ajouter le texte
    """
    for content in element.children:
        if isinstance(content, str):
            paragraph.add_run(content)
        elif content.name == "strong" or content.name == "b":
            run = paragraph.add_run(content.get_text())
            run.bold = True
        elif content.name == "em" or content.name == "i":
            run = paragraph.add_run(content.get_text())
            run.italic = True
        elif content.name == "code":
            run = paragraph.add_run(content.get_text())
            run.font.name = "Courier New"
        elif content.name == "a":
            run = paragraph.add_run(content.get_text())
            run.font.color.rgb = RGBColor(0, 0, 255)
            run.underline = True


def _to_document(markdown_text: str) -> Document:
    """Build a python-docx Document. Kept private: callers want bytes."""
    soup = BeautifulSoup(to_html(markdown_text), "html.parser")
    doc = Document()

    for element in soup.children:
        if not isinstance(element, Tag):
            continue
        if element.name == "h1":
            doc.add_heading(element.get_text(), level=1)
        elif element.name == "h2":
            doc.add_heading(element.get_text(), level=2)
        elif element.name == "h3":
            doc.add_heading(element.get_text(), level=3)
        elif element.name == "p":
            paragraph = doc.add_paragraph()
            _parse_inline_elements(element, paragraph)
        elif element.name == "ul":
            for li in element.find_all("li", recursive=False):
                paragraph = doc.add_paragraph(style="List Bullet")
                _parse_inline_elements(li, paragraph)
        elif element.name == "ol":
            for li in element.find_all("li", recursive=False):
                paragraph = doc.add_paragraph(style="List Number")
                _parse_inline_elements(li, paragraph)
        elif element.name == "pre":
            doc.add_paragraph(element.get_text(), style="No Spacing")

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
