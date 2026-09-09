"""Image and PDF text extraction with conservative OCR quality checks."""

from __future__ import annotations

import io
from pathlib import Path

from .models import OCRResult


MINIMUM_USEFUL_TEXT_LENGTH = 20


def _quality_result(raw_text: str, confidence: float | None, warnings: list[str]) -> OCRResult:
	cleaned = raw_text.strip()
	if not cleaned:
		warnings.append("OCR produced no usable text")
	elif len(cleaned) < MINIMUM_USEFUL_TEXT_LENGTH:
		warnings.append("OCR text is very short")
	if confidence is not None and confidence < 0.60:
		warnings.append("OCR confidence is low")
	suspicious_ratio = sum(character in "�□|" for character in cleaned) / max(len(cleaned), 1)
	if suspicious_ratio > 0.05:
		warnings.append("OCR text contains suspicious or unreadable characters")
	return OCRResult(
		raw_text=raw_text,
		ocr_confidence=confidence,
		warnings=warnings,
		human_verification_required=bool(warnings),
	)


def _image_ocr(image) -> tuple[str, float | None]:
	try:
		import pytesseract
	except ImportError as error:
		raise RuntimeError("Image OCR requires pytesseract") from error

	data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
	confidences = [float(value) for value in data["conf"] if str(value).strip() not in ("", "-1")]
	text = pytesseract.image_to_string(image)
	confidence = (sum(confidences) / len(confidences) / 100) if confidences else None
	return text, confidence


def extract_image(data: bytes) -> OCRResult:
	try:
		from PIL import Image
		image = Image.open(io.BytesIO(data))
	except Exception as error:
		raise ValueError("Unable to read prescription image") from error
	try:
		text, confidence = _image_ocr(image)
	except Exception as error:
		if error.__class__.__name__ == "TesseractNotFoundError":
			return _quality_result("", None, ["Tesseract OCR engine is unavailable"])
		raise
	return _quality_result(text, confidence, [])


def extract_pdf(data: bytes) -> OCRResult:
	try:
		from pypdf import PdfReader
		reader = PdfReader(io.BytesIO(data))
		text = "\n".join(page.extract_text() or "" for page in reader.pages)
	except Exception as error:
		raise ValueError("Unable to read prescription PDF") from error

	if len(text.strip()) >= MINIMUM_USEFUL_TEXT_LENGTH:
		return _quality_result(text, 0.95, [])

	warnings = ["PDF did not contain usable embedded text; page OCR was used"]
	try:
		import fitz
	except ImportError as error:
		warnings.append("Scanned PDF OCR requires PyMuPDF")
		return _quality_result(text, None, warnings)

	document = fitz.open(stream=data, filetype="pdf")
	page_text: list[str] = []
	confidences: list[float] = []
	for page in document:
		pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
		image_result = extract_image(pixmap.tobytes("png"))
		page_text.append(image_result.raw_text)
		if image_result.ocr_confidence is not None:
			confidences.append(image_result.ocr_confidence)
		warnings.extend(image_result.warnings)
	confidence = sum(confidences) / len(confidences) if confidences else None
	return _quality_result("\n".join(page_text), confidence, warnings)


def extract_prescription(path: Path, content_type: str) -> OCRResult:
	data = path.read_bytes()
	if content_type == "application/pdf":
		return extract_pdf(data)
	return extract_image(data)
