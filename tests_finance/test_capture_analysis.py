"""Extracción y propuesta local de capturas (Fase 4, CF4-04)."""

from cuentafaro.ai.ocr import ocr_available
from cuentafaro.captures import extract_capture_text, parse_capture_proposal


def test_text_capture_keeps_raw_text() -> None:
    text = extract_capture_text(kind="text", raw_text="  Supermercado 45.890  ", payload={})
    assert text == "Supermercado 45.890"
    assert extract_capture_text(kind="text", raw_text="   ", payload={}) is None


def test_audio_capture_requires_human_review() -> None:
    assert extract_capture_text(kind="audio", raw_text="", payload={"media": "nota.ogg"}) is None


def test_image_without_media_is_none() -> None:
    assert extract_capture_text(kind="image", raw_text=None, payload={}) is None


def test_image_with_unreadable_media_is_none() -> None:
    assert (
        extract_capture_text(kind="image", raw_text=None, payload={"media": "/no/existe.png"})
        is None
    )


def test_image_ocr_when_available() -> None:
    if not ocr_available():
        return
    import tempfile

    from PIL import Image, ImageDraw

    with tempfile.NamedTemporaryFile(suffix=".png") as handle:
        image = Image.new("RGB", (640, 120), "white")
        draw = ImageDraw.Draw(image)
        draw.text((20, 40), "Supermercado 45.890", fill="black")
        image.save(handle.name)
        text = extract_capture_text(kind="image", raw_text=None, payload={"media": handle.name})
        assert text is not None
        assert "Supermercado" in text


def test_unknown_kind_returns_none() -> None:
    assert extract_capture_text(kind="video", raw_text="x", payload={}) is None


# ---------------- Propuesta determinista ----------------


def test_parse_amount_and_description() -> None:
    proposal = parse_capture_proposal("Supermercado 45.890")
    assert proposal["amount"] == 45890
    assert proposal["description"] == "Supermercado"
    assert "date" not in proposal


def test_parse_thousands_and_plane_amounts() -> None:
    assert parse_capture_proposal("Sueldo 1.500.000")["amount"] == 1500000
    assert parse_capture_proposal("Pago con tarjeta 45890")["amount"] == 45890
    assert parse_capture_proposal("Café 3.500")["amount"] == 3500


def test_parse_date_ddmm_yyyy() -> None:
    proposal = parse_capture_proposal("15/09/2026 Compra 45.890 en tienda")
    assert proposal["date"] == "2026-09-15"
    assert proposal["amount"] == 45890
    assert proposal["description"] == "Compra en tienda"


def test_parse_dash_date_and_two_digit_year() -> None:
    proposal = parse_capture_proposal("Pago 14-05-26 12.000")
    assert proposal["date"] == "2026-05-14"
    assert proposal["amount"] == 12000


def test_parse_without_amount_keeps_description() -> None:
    proposal = parse_capture_proposal("Café con leche")
    assert "amount" not in proposal
    assert proposal["description"] == "Café con leche"


def test_parse_empty_and_blank() -> None:
    assert parse_capture_proposal("") == {}
    assert parse_capture_proposal("   ") == {}
