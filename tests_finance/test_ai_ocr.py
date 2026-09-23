"""OCR y extracción de PDF local (Fase 3, CF3-04)."""

import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

from cuentafaro.ai.ocr import (
    extract_pdf_text,
    extract_pdf_text_as_rows,
    ocr_available,
    pdf_rows_to_table,
)
from cuentafaro.api import create_app
from cuentafaro.db import create_engine_and_session
from cuentafaro.deps import get_session
from cuentafaro.importing.contract import ImportFormatError
from cuentafaro.importing.extract import extract_table, guess_source_kind
from cuentafaro.models import Base


def _text_pdf_bytes() -> bytes:
    import pymupdf

    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((72, 72), "01/09/2026    Supermercado    -45.890")
    page.insert_text((72, 100), "02/09/2026    Sueldo    1.500.000")
    payload = document.tobytes()
    document.close()
    return payload


def _scanned_pdf_bytes() -> bytes:
    import pymupdf

    image = Image.new("RGB", (800, 400), "white")
    draw = ImageDraw.Draw(image)
    draw.text((40, 40), "01/09/2026  Supermercado  -45.890", fill="black")
    draw.text((40, 120), "02/09/2026  Sueldo  1.500.000", fill="black")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")

    document = pymupdf.open()
    page = document.new_page(width=800, height=400)
    page.insert_image(page.rect, stream=buffer.getvalue())
    payload = document.tobytes()
    document.close()
    return payload


def test_guess_source_kind_accepts_pdf() -> None:
    assert guess_source_kind("estado_cuenta.PDF") == "pdf"
    with pytest.raises(ImportFormatError):
        guess_source_kind("estado.txt")


def test_extract_pdf_text_reads_embedded_text() -> None:
    text = extract_pdf_text(_text_pdf_bytes())
    assert "Supermercado" in text
    assert "Sueldo" in text


def test_pdf_rows_to_table_uses_columna_headers() -> None:
    rows = extract_pdf_text_as_rows(_text_pdf_bytes())
    assert rows
    table = pdf_rows_to_table(rows)
    assert table.headers == ["columna_1", "columna_2", "columna_3"]
    assert table.rows
    assert "Supermercado" in " ".join(table.rows[0].values())


def test_extract_table_supports_pdf() -> None:
    table = extract_table(_text_pdf_bytes(), source_kind="pdf")
    assert table.headers == ["columna_1", "columna_2", "columna_3"]
    assert len(table.rows) == 2
    assert table.rows[0]["columna_1"] == "01/09/2026"
    assert table.rows[0]["columna_3"] == "-45.890"


def test_scanned_pdf_behaves_with_tesseract_availability() -> None:
    if ocr_available():
        assert extract_pdf_text(_scanned_pdf_bytes())
    else:
        with pytest.raises(ImportFormatError):
            extract_pdf_text(_scanned_pdf_bytes())


@pytest.fixture()
def client(tmp_path):
    engine, session_factory = create_engine_and_session(f"sqlite:///{tmp_path / 'api_ocr.db'}")
    Base.metadata.create_all(engine)
    app = create_app()

    def override_session():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_session] = override_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    engine.dispose()


def test_upload_pdf_creates_batch_with_source_kind_pdf(client) -> None:
    household = client.post(
        "/api/v1/households",
        json={"name": "Hogar PDF", "timezone": "America/Santiago", "status": "active"},
    ).json()
    account = client.post(
        "/api/v1/accounts",
        json={"household_id": household["id"], "name": "Corriente", "type": "checking"},
    ).json()

    response = client.post(
        f"/api/v1/households/{household['id']}/import-batches",
        data={
            "account_id": account["id"],
            "column_mapping": '{"date":"columna_1","description":"columna_2","amount":"columna_3"}',
            "header_row": "1",
            "source_kind": "",
            "separator": "",
        },
        files={"file": ("estado.pdf", _text_pdf_bytes(), "application/pdf")},
    )
    assert response.status_code == 201
    batch = response.json()
    assert batch["source_kind"] == "pdf"
    assert batch["total_rows"] == 2
    assert batch["valid_rows"] == 2
    assert batch["invalid_rows"] == 0
