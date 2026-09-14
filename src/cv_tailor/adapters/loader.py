"""Reading CVs and job descriptions from disk or from an upload."""

from pathlib import Path

from docx import Document

from cv_tailor.config import CV_DIR


def load_resumes(data_dir: str | Path | None = None) -> dict[str, str]:
    """Load every .txt resume from a directory.

    Args:
        data_dir: Directory holding the .txt files. Defaults to the packaged CV directory.
    Returns:
        Filenames without their .txt extension, mapped to their content.
    """
    data_path = Path(data_dir) if data_dir else CV_DIR

    if not data_path.is_dir():
        raise FileNotFoundError(f"Resume directory '{data_path}' not found.")

    return {
        file_path.stem: file_path.read_text(encoding="utf-8")
        for file_path in sorted(data_path.iterdir())
        if file_path.suffix == ".txt"
    }


def extract_text_from_docx(file) -> str:
    """Read a .docx from a path or an uploaded file-like object."""
    return "\n".join(paragraph.text for paragraph in Document(file).paragraphs)
