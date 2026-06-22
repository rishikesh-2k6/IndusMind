"""Per-format text extraction."""
from __future__ import annotations

import csv
import io

from app.core.exceptions import ProcessingError, UnsupportedFileTypeError
from app.services.document_processing.ocr import OCREngine

# Maps file extensions to a normalised type tag.
SUPPORTED_TYPES: dict[str, str] = {
    "pdf": "pdf",
    "docx": "docx",
    "xlsx": "xlsx",
    "xls": "xlsx",
    "csv": "csv",
    "txt": "txt",
    "md": "txt",
    "png": "image",
    "jpg": "image",
    "jpeg": "image",
}


def detect_file_type(file_name: str) -> str:
    """Return the normalised type tag for a file name, or raise if unsupported."""
    ext = file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""
    if ext not in SUPPORTED_TYPES:
        raise UnsupportedFileTypeError(f"Unsupported file type: '.{ext or file_name}'")
    return SUPPORTED_TYPES[ext]


def extract(data: bytes, file_type: str, ocr: OCREngine) -> tuple[str, int]:
    """Extract text from raw bytes. Returns (text, page_count)."""
    try:
        if file_type == "pdf":
            return _extract_pdf(data)
        if file_type == "docx":
            return _extract_docx(data), 1
        if file_type == "xlsx":
            return _extract_xlsx(data), 1
        if file_type == "csv":
            return _extract_csv(data), 1
        if file_type == "txt":
            return data.decode("utf-8", errors="replace"), 1
        if file_type == "image":
            return ocr.image_to_text(data), 1
    except ProcessingError:
        raise
    except UnsupportedFileTypeError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise ProcessingError(f"Failed to extract text: {exc}") from exc

    raise UnsupportedFileTypeError(f"Unsupported file type: {file_type}")


def _extract_pdf(data: bytes) -> tuple[str, int]:
    import fitz  # PyMuPDF

    parts: list[str] = []
    with fitz.open(stream=data, filetype="pdf") as doc:
        page_count = doc.page_count
        for page in doc:
            parts.append(page.get_text())
    return "\n".join(parts), page_count


def _extract_docx(data: bytes) -> str:
    from docx import Document as DocxDocument

    doc = DocxDocument(io.BytesIO(data))
    parts = [p.text for p in doc.paragraphs if p.text]
    for table in doc.tables:
        for row in table.rows:
            cells = [c.text.strip() for c in row.cells]
            if any(cells):
                parts.append(" | ".join(cells))
    return "\n".join(parts)


def _extract_xlsx(data: bytes) -> str:
    from openpyxl import load_workbook

    wb = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    parts: list[str] = []
    for ws in wb.worksheets:
        parts.append(f"# Sheet: {ws.title}")
        for row in ws.iter_rows(values_only=True):
            cells = ["" if c is None else str(c) for c in row]
            if any(cells):
                parts.append(", ".join(cells))
    wb.close()
    return "\n".join(parts)


def _extract_csv(data: bytes) -> str:
    text = data.decode("utf-8", errors="replace")
    # Round-trip through csv to normalise delimiters/quoting into readable rows.
    reader = csv.reader(io.StringIO(text))
    return "\n".join(", ".join(row) for row in reader)
