import io

import fitz
from PIL import Image
from pypdf import PdfWriter

from app import ocr


def make_pdf_without_text() -> bytes:
    output = io.BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=300, height=300)
    writer.write(output)
    return output.getvalue()


def test_empty_ocr_requires_human_verification(monkeypatch):
    monkeypatch.setattr(ocr, "_image_ocr", lambda image: ("", 0.32))
    image_buffer = io.BytesIO()
    Image.new("RGB", (40, 40), "white").save(image_buffer, format="PNG")

    result = ocr.extract_image(image_buffer.getvalue())

    assert result.raw_text == ""
    assert result.ocr_confidence == 0.32
    assert result.human_verification_required is True
    assert "OCR produced no usable text" in result.warnings
    assert "OCR confidence is low" in result.warnings


def test_embedded_pdf_text_is_extracted():
    document = fitz.open()
    page = document.new_page(width=300, height=300)
    page.insert_text((30, 50), "Patient: Example Patient\nMetformin 500 mg twice daily")
    embedded_pdf = document.tobytes()

    result = ocr.extract_pdf(embedded_pdf)

    assert "Metformin 500 mg" in result.raw_text
    assert result.ocr_confidence == 0.95
    assert result.human_verification_required is False


def test_scanned_pdf_without_tesseract_requires_review():
    writer = PdfWriter()
    writer.add_blank_page(width=300, height=300)
    output = io.BytesIO()
    writer.write(output)

    result = ocr.extract_pdf(output.getvalue())

    assert result.raw_text == ""
    assert result.human_verification_required is True
    assert any("PDF did not contain usable embedded text" in warning for warning in result.warnings)


def test_quality_flags_short_text():
    result = ocr._quality_result("Metformin", 0.9, [])

    assert result.human_verification_required is True
    assert "OCR text is very short" in result.warnings
