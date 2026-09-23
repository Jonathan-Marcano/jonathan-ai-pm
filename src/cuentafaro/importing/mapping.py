"""Asociación de columnas del archivo al contrato (CF2-05, CF4-Itaú)."""

from __future__ import annotations

import re
import unicodedata

from cuentafaro.importing.contract import FIELD_BY_KEY, IMPORT_FIELDS, ImportFormatError

ALIAS_BY_FIELD: dict[str, tuple[str, ...]] = {
    "date": ("fecha", "date", "fechamovimiento", "fechaoperacion"),
    "description": (
        "descripcion",
        "detalle",
        "glosa",
        "concepto",
        "comercio",
        "movimiento",
        "description",
    ),
    "amount": ("monto", "amount", "valor", "importe", "monto clp"),
    "balance": ("saldo", "balance", "saldoacumulado"),
    "external_id": (
        "codigo",
        "referencia",
        "folio",
        "nrooperacion",
        "externalid",
        "numerooperacion",
        "ndeoperacion",
        "operacion",
    ),
    "cargos": ("cargo", "cargos", "debito", "debitos", "retiro", "retiros"),
    "abonos": ("abono", "abonos", "credito", "creditos", "deposito", "depositos"),
}


def _normalize(value: str) -> str:
    text = value.strip().lower()
    text = "".join(c for c in unicodedata.normalize("NFD", text) if not unicodedata.combining(c))
    return re.sub(r"\W+", "", text)


def _alias_match(header: str, aliases: tuple[str, ...]) -> bool:
    name = _normalize(header)
    return (
        bool(name)
        and any(a == name for a in aliases)
        or any(a and (name.endswith(a) or a in name) for a in aliases)
    )


def locate_column(headers: list[str], aliases: tuple[str, ...]) -> str | None:
    hits = [header for header in headers if _alias_match(header, aliases)]
    return hits[0] if hits else None


def auto_mapping(headers: list[str]) -> dict[str, str]:
    """Mapea columnas al contrato por alias (fecha, movimientos, cargos, abonos…)."""
    mapping: dict[str, str] = {}
    for key in FIELD_BY_KEY:
        column = locate_column(headers, ALIAS_BY_FIELD.get(key, ()))
        if column:
            mapping[key] = column
    return mapping


def normalize_mapping(column_mapping: dict[str, str], headers: list[str]) -> dict[str, str]:
    """Valida el mapeo {campo del contrato -> columna del archivo} y lo completa.

    - Solo acepta claves del contrato y columnas que existen en el archivo.
    - Si el archivo no trae mapeo (cartolas Excel/PDF), localiza las columnas
      por alias en los encabezados; un mapeo proporcionado se respeta tal cual.
    - El monto puede venir de la columna ``amount`` o bien derivarse de las
      columnas ``cargos``/``abonos`` (cartolas con dos columnas de signo).
    """
    unknown = sorted(set(column_mapping) - set(FIELD_BY_KEY))
    if unknown:
        raise ImportFormatError(f"campos de mapeo desconocidos: {', '.join(unknown)}")
    explicit: dict[str, str] = {}
    for key, source in column_mapping.items():
        if source:
            explicit[key] = source
    if explicit:
        for source in explicit.values():
            if source not in headers:
                raise ImportFormatError(f"la columna '{source}' no existe en el archivo")
    normalized: dict[str, str] = {}
    for key in FIELD_BY_KEY:
        source = explicit.get(key)
        if source is None and not explicit:
            source = locate_column(headers, ALIAS_BY_FIELD.get(key, ()))
        if source:
            normalized[key] = source
    missing_keys = [
        field.key for field in IMPORT_FIELDS if field.required and field.key not in normalized
    ]
    if "amount" in missing_keys and ("cargos" in normalized or "abonos" in normalized):
        missing_keys.remove("amount")
    if missing_keys:
        labels = ", ".join(FIELD_BY_KEY[key].label for key in missing_keys)
        raise ImportFormatError(f"faltan campos obligatorios: {labels}")
    return normalized
