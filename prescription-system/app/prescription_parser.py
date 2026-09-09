"""Conservative, regex-based extraction from OCR text."""

from __future__ import annotations

import re
from datetime import date, datetime
from difflib import get_close_matches

from .models import Medication, ParserWarning, Patient, Prescription


_MEDICATION_RE = re.compile(
	r"^(?:tab(?:let)?\s+)?(?P<name>[A-Za-z][A-Za-z-]{2,})(?:\s+(?P<strength>\d+(?:\.\d+)?\s*(?:mg|mcg|g|ml|units?)))?\s*$",
	re.IGNORECASE,
)
_STRENGTH_RE = re.compile(r"(?P<strength>\d+(?:\.\d+)?\s*(?:mg|mcg|g|ml|units?))", re.IGNORECASE)
_DATE_RE = re.compile(r"(?:date|prescription date)\s*:\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})", re.IGNORECASE)
_KNOWN_MEDICATIONS = {
	"amlodipine", "amiodarone", "apixaban", "aspirin", "digoxin", "ibuprofen",
	"lisinopril", "metformin", "methotrexate", "simvastatin", "trimethoprim",
	"warfarin",
}


def _value_after_label(text: str, label: str) -> str | None:
	match = re.search(rf"^{label}\s*:\s*(.+)$", text, re.IGNORECASE | re.MULTILINE)
	return match.group(1).strip() if match else None


def _parse_age(text: str) -> int | None:
	value = _value_after_label(text, "age")
	if value is None:
		return None
	match = re.search(r"\d{1,3}", value)
	return int(match.group()) if match else None


def _parse_date(text: str) -> date | None:
	match = _DATE_RE.search(text)
	if not match:
		return None
	for pattern in ("%d/%m/%Y", "%d-%m-%Y", "%d/%m/%y", "%d-%m-%y"):
		try:
			return datetime.strptime(match.group(1), pattern).date()
		except ValueError:
			continue
	return None


def _is_instruction(line: str) -> bool:
	lowered = line.lower()
	return any(token in lowered for token in ("tablet", "capsule", "daily", "twice", "once", "weekly", "morning", "evening", "days", "oral", "topical"))


def parse_prescription(raw_text: str) -> Prescription:
	lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
	text = "\n".join(lines)
	patient = Patient(
		name=_value_after_label(text, "patient") or _value_after_label(text, "name"),
		age=_parse_age(text),
		gender=_value_after_label(text, "gender"),
	)
	condition = _value_after_label(text, "diagnosis") or _value_after_label(text, "condition")
	medications: list[Medication] = []
	uncertain: list[ParserWarning] = []
	warnings: list[ParserWarning] = []

	for index, line in enumerate(lines):
		if any(line.lower().startswith(prefix) for prefix in ("patient:", "name:", "age:", "gender:", "diagnosis:", "condition:", "date:", "prescription date:")):
			continue
		match = _MEDICATION_RE.match(line)
		if not match:
			if _STRENGTH_RE.search(line) and not _is_instruction(line):
				uncertain.append(ParserWarning(text=line, reason="Medication line could not be parsed confidently"))
			continue
		name = match.group("name")
		strength = match.group("strength")
		close_names = get_close_matches(name.lower(), _KNOWN_MEDICATIONS, n=1, cutoff=0.75)
		if close_names and close_names[0] != name.lower():
			uncertain.append(ParserWarning(text=line, reason="Medication name may be misspelled"))
			continue
		following = lines[index + 1] if index + 1 < len(lines) else ""
		duration_line = lines[index + 2] if index + 2 < len(lines) else ""
		medications.append(Medication(
			name=name,
			strength=strength,
			dose=following if _is_instruction(following) else None,
			frequency=following if any(token in following.lower() for token in ("daily", "twice", "once", "weekly", "morning", "evening")) else None,
			duration=duration_line if re.search(r"\b\d+\s*days?\b", duration_line, re.IGNORECASE) else None,
		))

	if not medications:
		warnings.append(ParserWarning(text=raw_text[:120], reason="No medication could be extracted confidently"))
	return Prescription(
		patient=patient,
		prescription_date=_parse_date(text),
		condition=condition,
		medications=medications,
		uncertain_medications=uncertain,
		warnings=warnings,
	)
