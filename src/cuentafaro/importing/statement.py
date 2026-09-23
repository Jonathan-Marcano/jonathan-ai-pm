"""Detección del resumen de un estado de cuenta de tarjeta de crédito (cartola).

Las cartolas de tarjeta traen, además de la tabla de movimientos, un bloque de
metadatos con ``Total a pagar``, ``Pago mínimo``, ``Fecha de vencimiento``,
``Deuda total``, ``Cupo`` y ``Período``. Esas filas no son transacciones y el
parser las descarta, así que se detectan sobre la ``ExtractedTable`` completa:
sus ``rows`` incluyen los metadatos intercalados y su ``preamble`` los que están
en la cabecera sobre la tabla de movimientos.
"""

from __future__ import annotations

import re
import unicodedata

from cuentafaro.importing.contract import parse_amount, parse_date
from cuentafaro.importing.extract import ExtractedTable

CARD_FIELDS = (
    "statement_period",
    "due_date",
    "total_to_pay",
    "minimum_payment",
    "total_debt",
    "available_credit",
    "credit_limit",
)

LABEL = {
    "statement_period": "Período",
    "due_date": "Fecha de vencimiento",
    "total_to_pay": "Total a pagar",
    "minimum_payment": "Pago mínimo",
    "total_debt": "Deuda total",
    "available_credit": "Cupo disponible",
    "credit_limit": "Cupo de la tarjeta",
}

# Los alias se normalizan (sin acentos ni signos, en minúsculas) al comparar.
_ALIASES: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "statement_period",
        (
            "periododefacturacion",
            "periodofacturacion",
            "periodo",
            "periodoestadodecuenta",
            "periodomovimientos",
        ),
    ),
    (
        "due_date",
        (
            "fechadevencimiento",
            "fechalimitedepago",
            "vencimientodelestado",
            "fechavencimiento",
            "vencimiento",
        ),
    ),
    (
        "total_to_pay",
        (
            "montototalapagar",
            "totalapagardelmes",
            "saldoapagardelmes",
            "totalapagar",
            "pagototal",
            "saldoapagar",
            "montopropuesto",
        ),
    ),
    (
        "minimum_payment",
        ("pagominimoapagar", "pagominimodelmes", "cuotaminima", "pagominimo", "minimoapagar"),
    ),
    (
        "total_debt",
        (
            "deudatotaldelestadodecuenta",
            "deudadelestadodecuenta",
            "saldodeudordelestadodecuenta",
            "deudatotal",
            "saldodeudor",
        ),
    ),
    (
        "available_credit",
        ("cupodisponibleparacompras", "cupodisponible", "cupovigente", "cupolibre"),
    ),
    (
        "credit_limit",
        (
            "lineadecreditototal",
            "cupodecreditototal",
            "cupototalasignado",
            "cupototal",
            "cupodecredito",
            "lineadecredito",
            "cupoasignado",
            "cupocompras",
            "cupo",
        ),
    ),
)

_ALL_ALIASES = frozenset(alias for _, aliases in _ALIASES for alias in aliases)


def _norm(value: str) -> str:
    text = str(value).strip().lower()
    text = "".join(c for c in unicodedata.normalize("NFD", text) if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]", "", text)


def _alias_hits(text: str) -> list[tuple[str, str]]:
    """Coincidencias (campo, alias normalizado) para un texto."""
    norm = _norm(text)
    if not norm:
        return []
    hits: list[tuple[str, str]] = []
    for field, aliases in _ALIASES:
        for alias in aliases:
            if norm == alias or (len(alias) >= 9 and alias in norm):
                hits.append((field, alias))
    # El alias más largo y específico primero; al empatar, el orden del contrato
    # (deuda total > total a pagar > cupo disponible > cupo).
    hits.sort(key=lambda item: (-len(item[1]), CARD_FIELDS.index(item[0])))
    return hits


def _clean_amount(value: str) -> str:
    text = value.strip().replace("$", "").replace("CLP", "").replace("clp", "")
    return text.strip("+-()")


def _parse_fragments(field: str, fragments: list[str]) -> object | None:
    """Lee el valor (fecha o monto CLP) desde una lista de celdas adyacentes."""
    fragments = [text for text in fragments if text and text not in {"$", "CLP", "clp"}]
    if not fragments:
        return None
    if field == "statement_period":
        return " ".join(fragments).strip()
    if field == "due_date":
        for fragment in fragments:
            text = _clean_amount(fragment)
            if not text:
                continue
            try:
                return parse_date(text).isoformat()
            except Exception:
                continue
        return None
    for fragment in fragments:
        text = _clean_amount(fragment)
        if not text:
            continue
        try:
            return parse_amount(text)
        except Exception:
            continue
    return None


def scan_sources(table: ExtractedTable) -> list[dict[str, str]]:
    """Combina preámbulo y filas de la tabla para el detector de resumen."""
    return list(table.preamble) + list(table.rows)


def detect_card_statement(table: ExtractedTable) -> dict:
    """Devuelve los campos de resumen de tarjeta detectados en la cartola.

    - Excel/CSV: filas clave/valor con pocas celdas (``Fecha de vencimiento``,
      ``Total a Pagar``, ``Pago Mínimo``, ``Saldo Deudor``, ``Cupo Total``…).
    - PDF: líneas ``[etiqueta, $, 1.234.567]`` o una sola celda
      ``Total a Pagar: 1.234.567``.
    Las filas de datos (muchas celdas pobladas) se ignoran para no confundir
    una columna llamada ``Monto a pagar`` con el total del estado de cuenta.
    """
    info: dict[str, object] = {}
    for row in scan_sources(table):
        cells = [value.strip() for value in row.values()]
        populated = [cell for cell in cells if cell]

        # 1) Celda "Total a Pagar: 123.456" / "Vencimiento 28/09/2026".
        for cell in cells:
            hits = _alias_hits(cell)
            if not hits or hits[0][0] in info:
                continue
            field = hits[0][0]
            remainder = re.split(r"[:;]", cell, maxsplit=1)[-1]
            has_digit = any(character.isdigit() for character in remainder)
            has_separator = ":" in cell or ";" in cell
            # La celda es solo la etiqueta (sin valor): la fila siguiente la
            # resuelve como par clave/valor en el paso 2.
            if not has_separator and not has_digit:
                continue
            value = _parse_fragments(field, re.findall(r"\S+", remainder))
            if value is not None:
                info[field] = value

        # 2) Etiqueta en una celda y valor en celdas adyacentes (clave/valor).
        labeled = [
            (hits[0][0], index)
            for index, cell in enumerate(cells)
            if (hits := _alias_hits(cell))
        ]
        if 2 <= len(populated) <= 4:
            for field, index in labeled:
                if field in info:
                    continue
                value = _parse_fragments(field, cells[index + 1:])
                if value is not None:
                    info[field] = value

    return {key: value for key, value in info.items() if value is not None}