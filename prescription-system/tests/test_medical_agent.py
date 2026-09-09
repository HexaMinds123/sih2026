import asyncio

from app.medical_agent import analyze_prescription
from app.models import ExtractionResponse, Medication, OCRResult, Patient, Prescription


class FakeMCPClient:
    def __init__(self, guidance=None, interactions=None, error=None):
        self.guidance = guidance or {}
        self.interactions = interactions or {"interaction_found": False, "interactions": []}
        self.error = error
        self.connect_calls = 0
        self.interaction_calls = []
        self.guidance_calls = []
        self.close_calls = 0

    async def connect(self):
        self.connect_calls += 1
        if self.error:
            raise self.error
        return ["query_drug_interactions", "search_prescription_guidance"]

    async def close(self):
        self.close_calls += 1

    async def query_drug_interactions(self, medications):
        self.interaction_calls.append(medications)
        if self.error:
            raise self.error
        return self.interactions

    async def search_prescription_guidance(self, medication, condition=None, dosage=None):
        self.guidance_calls.append((medication, condition, dosage))
        if self.error:
            raise self.error
        return self.guidance.get(medication.lower(), {
            "medication": medication.lower(),
            "evidence_found": False,
            "evidence": [],
        })


def extraction(*medications, condition="Type 2 Diabetes", uncertain=None, ocr_review=False):
    return ExtractionResponse(
        prescription_id="RX-AGENT",
        ocr=OCRResult(raw_text="prescription", ocr_confidence=0.9, human_verification_required=ocr_review),
        prescription=Prescription(
            patient=Patient(),
            condition=condition,
            medications=list(medications),
            uncertain_medications=uncertain or [],
        ),
        human_verification_required=ocr_review,
    )


def evidence(source="DailyMed"):
    return [{
        "text": "Reference evidence",
        "source": source,
        "document_id": "doc-1",
        "section": "1 INDICATIONS AND USAGE",
        "page": None,
        "version": 6,
        "jurisdiction": "United States",
        "publication_date": "2026-06-24",
        "source_url": "https://example.invalid/doc-1",
        "similarity_score": 0.78,
    }]


def run(coroutine):
    return asyncio.run(coroutine)


def test_single_medication_preserves_evidence_and_audit():
    client = FakeMCPClient(guidance={"metformin": {"evidence_found": True, "evidence": evidence()}})
    result = run(analyze_prescription(
        extraction(Medication(name="Metformin", strength="500 mg", frequency="twice daily")), client
    ))

    assert result.status == "INFORMATIONAL"
    assert result.human_review_required is False
    assert result.medications[0].evidence_status == "EVIDENCE_FOUND"
    assert result.medications[0].evidence[0].retrieval_similarity_score == 0.78
    assert result.audit["tools_called"][0].tool == "search_prescription_guidance"
    assert client.interaction_calls == []
    assert len(client.guidance_calls) == 1


def test_multiple_medications_calls_interactions_once():
    client = FakeMCPClient(guidance={
        "metformin": {"evidence_found": True, "evidence": evidence()},
        "aspirin": {"evidence_found": True, "evidence": evidence()},
    })
    result = run(analyze_prescription(
        extraction(
            Medication(name="Metformin", strength="500 mg", frequency="twice daily"),
            Medication(name="Aspirin", strength="75 mg", frequency="once daily"),
        ), client
    ))

    assert result.status == "INFORMATIONAL"
    assert len(client.interaction_calls) == 1
    assert len(client.guidance_calls) == 2
    assert [call.tool for call in result.audit["tools_called"]] == [
        "query_drug_interactions", "search_prescription_guidance", "search_prescription_guidance"
    ]


def test_high_severity_interaction_requires_critical_review():
    client = FakeMCPClient(
        guidance={"warfarin": {"evidence_found": True, "evidence": evidence()}, "aspirin": {"evidence_found": True, "evidence": evidence()}},
        interactions={"interaction_found": True, "interactions": [{"severity": "high", "warning": "Bleeding risk"}]},
    )
    result = run(analyze_prescription(
        extraction(Medication(name="Warfarin", strength="2 mg", frequency="daily"), Medication(name="Aspirin", strength="75 mg", frequency="daily")), client
    ))

    assert result.status == "CRITICAL_REVIEW_REQUIRED"
    assert result.human_review_required is True


def test_missing_dosage_requires_review_without_invention():
    client = FakeMCPClient(guidance={"metformin": {"evidence_found": True, "evidence": evidence()}})
    result = run(analyze_prescription(extraction(Medication(name="Metformin", frequency="twice daily")), client))

    assert result.status == "REVIEW_REQUIRED"
    assert any("Dosage is missing" in issue for issue in result.issues)
    assert result.medications[0].dosage == "twice daily"


def test_unsupported_medication_is_insufficient_information():
    client = FakeMCPClient(guidance={"unknownmedicine": {"evidence_found": False, "evidence": []}})
    result = run(analyze_prescription(extraction(Medication(name="Unknownmedicine", strength="10 mg", frequency="daily")), client))

    assert result.status == "INSUFFICIENT_INFORMATION"
    assert result.medications[0].evidence_status == "NO_RELEVANT_EVIDENCE"
    assert result.human_review_required is True


def test_mcp_unavailable_is_controlled_and_not_safe():
    client = FakeMCPClient(error=RuntimeError("service unavailable"))
    result = run(analyze_prescription(extraction(Medication(name="Metformin", strength="500 mg", frequency="daily")), client))

    assert result.status == "INSUFFICIENT_INFORMATION"
    assert result.human_review_required is True
    assert any("Clinical knowledge service unavailable" in issue for issue in result.issues)
    assert "SAFE" not in result.status


def test_malformed_mcp_response_is_controlled():
    client = FakeMCPClient(guidance={"metformin": {"evidence_found": True, "evidence": "not-a-list"}})
    result = run(analyze_prescription(extraction(Medication(name="Metformin", strength="500 mg", frequency="daily")), client))

    assert result.status == "INSUFFICIENT_INFORMATION"
    assert result.human_review_required is True
    assert result.audit["tools_called"][0].result_received is False
