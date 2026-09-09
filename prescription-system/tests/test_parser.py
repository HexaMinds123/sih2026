from app.prescription_parser import parse_prescription


def test_parses_patient_condition_and_multiple_medications():
    result = parse_prescription(
        """Patient: Example Patient
Age: 45
Gender: Female
Diagnosis: Type 2 Diabetes
Date: 09/09/2026

Metformin 500 mg
1 tablet twice daily
30 days

Aspirin 75 mg
1 tablet once daily
30 days
"""
    )

    assert result.patient.name == "Example Patient"
    assert result.patient.age == 45
    assert result.condition == "Type 2 Diabetes"
    assert result.prescription_date.isoformat() == "2026-09-09"
    assert [medication.name for medication in result.medications] == ["Metformin", "Aspirin"]
    assert result.medications[0].strength == "500 mg"
    assert result.medications[0].frequency == "1 tablet twice daily"
    assert result.medications[0].duration == "30 days"


def test_missing_values_remain_null():
    result = parse_prescription("Metformin 500 mg")

    assert result.condition is None
    assert result.patient.name is None
    assert result.medications[0].strength == "500 mg"
    assert result.medications[0].dose is None
    assert result.medications[0].frequency is None
    assert result.medications[0].route is None
    assert result.medications[0].duration is None


def test_uncertain_medication_is_flagged_without_correction():
    result = parse_prescription("Metfornin 500 mg")

    assert result.medications == []
    assert result.uncertain_medications[0].text == "Metfornin 500 mg"
    assert "may be misspelled" in result.uncertain_medications[0].reason


def test_empty_text_returns_review_warning():
    result = parse_prescription("")

    assert result.medications == []
    assert result.warnings
