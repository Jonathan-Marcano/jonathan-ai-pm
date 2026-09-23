"""Parser de filas: tipos, validación por fila y conteos (CF2-03)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from cuentafaro.importing.contract import (
    FIELD_BY_KEY,
    ImportFormatError,
    parse_amount,
    validate_values,
)
from cuentafaro.importing.extract import ExtractedTable

_SHORT_DATE = re.compile(r"^\d{1,2}([/.\-])\d{1,2}$")
_DATE_SHAPE = re.compile(
    r"^\d{1,2}[/.\-]\d{1,2}(?:[/.\-]\d{2,4})?$|^\d{4}[/\-]\d{1,2}[/\-]\d{1,2}$"
)


@dataclass
class ParsedRow:
    row_number: int
    values: dict[str, str | None] = field(default_factory=dict)
    valid: bool = True
    errors: list[str] = field(default_factory=list)


@dataclass
class ParsedBatch:
    headers: list[str]
    rows: list[ParsedRow]
    total_rows: int = 0
    valid_rows: int = 0
    invalid_rows: int = 0


def _expand_date_year(value: object, default_year: int | None) -> str | None:
    """Completa fechas abreviadas (``03/08``) con el año del período de la cartola."""
    if default_year is None:
        return value if value is None else str(value).strip()
    text = str(value).strip()
    if not text or re.search(r"\d{4}", text):
        return text or None
    match = _SHORT_DATE.match(text)
    if not match:
        return text or None
    return f"{text}{match.group(1)}{default_year}"


def parse_batch(table: ExtractedTable, column_mapping: dict[str, str]) -> ParsedBatch:
    """Valida las filas contra el contrato respetando el mapeo de columnas.

    El mapeo debe venir normalizado (claves del contrato -> columna existente).
    Si no hay columna de monto pero sí de ``cargos``/``abonos``, el monto se
    deriva con signo: abonos (ingresos) positivos y cargos (gastos) negativos.
    """
    derive_amount = "amount" not in column_mapping and (
        "cargos" in column_mapping or "abonos" in column_mapping
    )
    rows: list[ParsedRow] = []
    for index, source_row in enumerate(table.rows):
        values: dict[str, str | None] = {}
        for key in FIELD_BY_KEY:
            column = column_mapping.get(key)
            values[key] = source_row.get(column) if column else None
        values["date"] = _expand_date_year(values.get("date"), table.default_year)
        if derive_amount:
            try:
                cargos = _amount_or_zero(values.get("cargos"))
                abonos = _amount_or_zero(values.get("abonos"))
                values["amount"] = str(abonos - cargos)
            except ImportFormatError:
                values["amount"] = None
        errors = validate_values(values)
        rows.append(
            ParsedRow(
                row_number=table.first_row_number + index,
                values=values,
                valid=not errors,
                errors=errors,
            )
        )
    # Filtrar bloque de datos: solo conservar filas entre la primera y la última
    # que tengan fecha válida. Filas fuera del rango (resumen, pies, metadatos)
    # se descartan silenciosamente.
    if rows:
        valid_indices = [
            i for i, row in enumerate(rows)
            if row.values.get("date") and _looks_like_date(row.values["date"])
        ]
        if valid_indices:
            first, last = valid_indices[0], valid_indices[-1]
            rows = rows[first:last + 1]
    total = len(rows)
    return ParsedBatch(
        headers=table.headers,
        rows=rows,
        total_rows=total,
        valid_rows=sum(1 for row in rows if row.valid),
        invalid_rows=sum(1 for row in rows if not row.valid),
    )


def _looks_like_date(value: str | None) -> bool:
    """Devuelve True si el valor tiene forma de fecha (límite del bloque de datos).

    Usa la forma (dd/mm, dd/mm/yyyy, yyyy-mm-dd) y no el parseo estricto, para
    que una fila con fecha mal formada pero real se conserve en la cola de
    revisión y solo se descarten filas de resumen/pie (textos sin forma de fecha).
    """
    if not value:
        return False
    return bool(_DATE_SHAPE.match(value.strip()))


def _amount_or_zero(value: object) -> int:
    text = (value or "").strip()
    if not text:
        return 0
    return parse_amount(text)
