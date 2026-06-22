"""Unit tests for file-type detection and the universal text extractor."""
import pytest

from app.core.exceptions import ProcessingError, UnsupportedFileTypeError
from app.services.document_processing import extractor
from app.services.document_processing.ocr import DisabledOCR


def test_detect_rich_types():
    assert extractor.detect_file_type("report.pdf") == "pdf"
    assert extractor.detect_file_type("deck.pptx") == "pptx"
    assert extractor.detect_file_type("photo.PNG") == "image"
    assert extractor.detect_file_type("data.csv") == "csv"


def test_detect_unknown_falls_back_to_text():
    # Any unknown/textual extension is accepted as generic text.
    assert extractor.detect_file_type("notes.json") == "text"
    assert extractor.detect_file_type("config.yaml") == "text"
    assert extractor.detect_file_type("server.log") == "text"
    assert extractor.detect_file_type("noextension") == "text"


def test_extract_plain_text():
    text, pages = extractor.extract(b"Pump P101 failed.", "text", DisabledOCR())
    assert "Pump P101" in text
    assert pages == 1


def test_extract_json_as_text():
    text, _ = extractor.extract(b'{"equipment": "P101"}', "text", DisabledOCR())
    assert "equipment" in text


def test_extract_html_strips_tags():
    html = b"<html><body><h1>Boiler</h1><script>x=1</script><p>B201 ready</p></body></html>"
    text, _ = extractor.extract(html, "html", DisabledOCR())
    assert "Boiler" in text and "B201 ready" in text
    assert "x=1" not in text  # script content removed


def test_extract_binary_rejected():
    blob = bytes(range(256)) * 10  # mostly non-printable
    with pytest.raises(UnsupportedFileTypeError):
        extractor.extract(blob, "text", DisabledOCR())


def test_extract_empty_rejected():
    with pytest.raises(ProcessingError):
        extractor.extract(b"", "text", DisabledOCR())
