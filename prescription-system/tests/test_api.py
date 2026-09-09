import io

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_rejects_invalid_file_type():
    response = client.post(
        "/upload-prescription",
        files={"file": ("notes.txt", b"not a prescription", "text/plain")},
    )

    assert response.status_code == 400


def test_upload_and_extract_with_mocked_ocr(monkeypatch):
    from app import main
    from app.models import OCRResult

    monkeypatch.setattr(
        main,
        "extract_prescription",
        lambda path, content_type: OCRResult(
            raw_text="Patient: Example\nMetformin 500 mg",
            ocr_confidence=0.9,
        ),
    )
    response = client.post(
        "/upload-prescription",
        files={"file": ("prescription.jpg", io.BytesIO(b"image"), "image/jpeg")},
    )
    assert response.status_code == 200
    prescription_id = response.json()["prescription_id"]

    extraction = client.post(f"/prescription/{prescription_id}/extract")

    assert extraction.status_code == 200
    body = extraction.json()
    assert body["prescription"]["patient"]["name"] == "Example"
    assert body["prescription"]["medications"][0]["name"] == "Metformin"


def test_analyze_requires_extracted_prescription():
    response = client.post("/prescription/RX-NOT-EXTRACTED/analyze")

    assert response.status_code == 404