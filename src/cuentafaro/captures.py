"""Extracción y propuesta local de capturas (Fase 4, CF4-04).

Transforma el contenido de una captura en una propuesta determinista
(fecha, monto y descripción) que la persona confirma o corrige antes de que
se persista cualquier movimiento (CF4-05). Nada sale del proceso local:
texto directo, OCR local con Tesseract para imágenes, y para audio (sin
transcripción local) la captura pasa a revisión humana.
"""

from __future__ import annotations

import re
from datetime import date

_AMOUNT = re.compile(
    r"(?P<amount>\d{1,3}(?:[.,]\d{3})+|\d{1,6})(?:\s*(?:pesos|clp|p\\$))?",
    re.IGNORECASE,
)
_DATE = re.compile(r"(?P<day>\d{1,2})[/-](?P<month>\d{1,2})[/-](?P<year>\d{2,4})")


def extract_capture_text(*, kind: str, raw_text: str | None, payload: dict) -> str | None:
    """Devuelve el texto legible según el tipo de captura (None = revisión humana).

    - text: el propio mensaje.
    - image: OCR local de la imagen en ``payload["media"]`` (ruta del archivo).
    - audio: sin transcripción local disponible → None (requiere revisión).
    """
    if kind == "text":
        return (raw_text or "").strip() or None
    if kind == "image":
        return _ocr_image_text(payload)
    if kind == "audio":
        return None
    return None


def _ocr_image_text(payload: dict) -> str | None:
    media = payload.get("media")
    if not media or not isinstance(media, str):
        return None
    try:
        from cuentafaro.ai.ocr import extract_image_text

        return extract_image_text(media) or None
    except Exception:
        return None


def parse_capture_proposal(text: str) -> dict:
    """Propuesta determinista: ``date`` (ISO), ``amount`` (pesos) y ``description``.

    Si no hay datos reconocibles devuelve un diccionario parcial o vacío; la
    persona completa o corrige antes de confirmar.
    """
    proposal: dict = {}
    haystack = (text or "").strip()
    if not haystack:
        return proposal

    removed: list[tuple[int, int]] = []
    date_value = _match_date(haystack)
    if date_value is not None:
        proposal["date"], span = date_value
        removed.append(span)

    amount = _match_amount(haystack, removed)
    if amount is not None:
        amount_value, span = amount
        if amount_value > 0:
            proposal["amount"] = amount_value
        removed.append(span)

    pieces = []
    for chunk in _split_spans(haystack, removed):
        piece = re.sub(r"\s+", " ", chunk).strip(" \t-.,;:/|()[]{}")
        if piece:
            pieces.append(piece)
    description = " ".join(pieces).strip()
    description = re.sub(r"\s+", " ", description).strip()
    if description:
        proposal["description"] = description

    return proposal


def _match_date(text: str) -> tuple[str, tuple[int, int]] | None:
    match = _DATE.search(text)
    if not match:
        return None
    try:
        day = int(match.group("day"))
        month = int(match.group("month"))
        year = int(match.group("year"))
    except ValueError:
        return None
    if year < 100:
        year += 2000 if year <= 69 else 1900
    try:
        value = date(year, month, day)
    except ValueError:
        return None
    return value.isoformat(), match.span()


def _match_amount(text: str, removed: list[tuple[int, int]]) -> tuple[int, tuple[int, int]] | None:
    candidates = list(_AMOUNT.finditer(text))
    if not candidates:
        return None
    preferred = (
        next(
            (match for match in candidates if "." in match.group("amount")),
            None,
        )
        or candidates[-1]
    )
    raw = re.sub(r"[.,]", "", preferred.group("amount"))
    if not raw.isdigit():
        return None
    value = int(raw)
    if value <= 0 or value >= 1_000_000_000:
        return None
    return value, preferred.span()


def _split_spans(text: str, spans: list[tuple[int, int]]) -> list[str]:
    parts: list[str] = []
    cursor = 0
    for start, end in sorted(spans):
        if end <= cursor:
            continue
        parts.append(text[cursor:start])
        cursor = end
    parts.append(text[cursor:])
    return parts
