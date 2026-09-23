"""Contrato de columnas para importar estados de cuenta (CF2-01)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation


class ImportFormatError(ValueError):
    """Error al interpretar un archivo o una fila de importación."""


@dataclass(frozen=True)
class ImportField:
    key: str
    label: str
    value_type: str
    required: bool


IMPORT_FIELDS: tuple[ImportField, ...] = (
    ImportField("date", "Fecha", "date", True),
    ImportField("description", "Descripción", "text", False),
    ImportField("amount", "Monto (CLP)", "integer", True),
    ImportField("balance", "Saldo (CLP)", "integer", False),
    ImportField("external_id", "ID externo", "text", False),
    ImportField("cargos", "Cargos (CLP)", "integer", False),
    ImportField("abonos", "Abonos (CLP)", "integer", False),
)

FIELD_BY_KEY: dict[str, ImportField] = {field.key: field for field in IMPORT_FIELDS}

_DATE_FORMATS = ("%d/%m/%Y", "%Y-%m-%d", "%Y/%m/%d", "%d-%m-%Y", "%d.%m.%Y")


def parse_amount(value: object) -> int:
    """Convierte un monto CLP a entero.

    - Los miles se separan con '.' y los decimales con ',' (convención CLP).
    - También acepta '.' como decimal (formato en-US) y enteros a secas.
    - '1,234' o '1.234' se interpretan como miles; los decimales se redondean
      a la unidad (regla de redondeo estándar bancario, half-up).
    """
    if value is None:
        raise ImportFormatError("monto vacío")
    normalized = str(value).strip().replace(" ", "").replace("$", "").replace("CLP", "")
    if not normalized:
        raise ImportFormatError("monto vacío")
    if "," in normalized and "." in normalized:
        if normalized.rfind(",") > normalized.rfind("."):
            normalized = normalized.replace(".", "").replace(",", ".")
        else:
            normalized = normalized.replace(",", "")
    elif "," in normalized:
        head, _, tail = normalized.rpartition(",")
        if head and tail and len(tail) == 3 and head.count(".") == 0 and len(head) < 4:
            normalized = head + tail
        else:
            normalized = normalized.replace(",", ".")
    elif normalized.count(".") >= 2:
        normalized = normalized.replace(".", "")
    elif normalized.count(".") == 1:
        whole, _, tail = normalized.rpartition(".")
        if whole and tail and len(tail) == 3 and whole.count(",") == 0 and len(whole) < 4:
            normalized = whole + tail
    try:
        return int(Decimal(normalized).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    except (InvalidOperation, ValueError) as error:
        raise ImportFormatError(f"monto inválido: {value!r}") from error


def parse_date(value: object, *, default_year: int | None = None) -> date:
    """Convierte una fecha a date; acepta dd/mm/yyyy, yyyy-mm-dd y variantes.

    Con ``default_year`` también acepta fechas abreviadas sin año (p. ej.
    ``03/08`` para cartolas de un solo período) y completa el año.
    """
    text = str(value).strip()
    if not text:
        raise ImportFormatError("fecha vacía")
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    if default_year is not None:
        for fmt in ("%d/%m", "%d-%m", "%d.%m"):
            try:
                return datetime.strptime(text, fmt).date().replace(year=default_year)
            except ValueError:
                continue
    raise ImportFormatError(f"formato de fecha no reconocido: {text!r}")


def validate_values(values: dict[str, object]) -> list[str]:
    """Valida un dict de valores por contrato; devuelve la lista de errores."""
    errors: list[str] = []
    for field in IMPORT_FIELDS:
        raw = values.get(field.key)
        if raw is None or (isinstance(raw, str) and not raw.strip()):
            if field.required:
                errors.append(f"{field.label}: obligatorio")
            continue
        try:
            if field.value_type == "date":
                parse_date(raw)
            elif field.value_type == "integer":
                mount = parse_amount(raw)
                if field.key == "amount" and mount == 0:
                    errors.append(f"{field.label}: debe ser distinto de cero")
        except ImportFormatError as error:
            errors.append(f"{field.label}: {error}")
    return errors
