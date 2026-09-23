"""Vista previa y conciliación de movimientos importados (CF2-07, CF2-08)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from cuentafaro.importing.contract import ImportFormatError, parse_amount, parse_date


@dataclass
class MovementPreview:
    row_number: int
    date: date | None = None
    description: str | None = None
    amount: int | None = None
    balance: int | None = None
    external_id: str | None = None
    kind: str | None = None
    valid: bool = True
    errors: list[str] = field(default_factory=list)
    balance_ok: bool | None = None
    duplicate: bool = False
    duplicate_type: str | None = None
    duplicate_of: str | None = None


def _clean_text(value: str | None, limit: int = 500) -> str | None:
    text = (value or "").strip()
    return text[:limit] or None


def meaningful_external_id(value: str | None) -> str | None:
    """ID externo real: ignora vacíos y placeholders tipo ``"000000000"`` (Itaú)."""
    text = _clean_text(value, limit=120)
    if text and not text.strip("0"):
        return None
    return text


def build_movement_previews(rows: list[dict]) -> list[MovementPreview]:
    """Reinterpreta las filas almacenadas de un ImportBatch como movimientos."""
    movements: list[MovementPreview] = []
    for row in rows:
        values = row.get("values") or {}
        valid = bool(row.get("valid"))
        errors = list(row.get("errors") or [])
        movement = MovementPreview(
            row_number=int(row.get("row", 0)),
            description=_clean_text(values.get("description")),
            external_id=meaningful_external_id(values.get("external_id")),
            valid=valid,
            errors=errors,
        )
        if valid:
            try:
                movement.date = parse_date(values.get("date"))
                movement.amount = parse_amount(values.get("amount"))
                balance = parse_amount(values.get("balance")) if values.get("balance") else None
                movement.balance = balance
            except ImportFormatError:  # no debería ocurrir si la fila era válida
                movement.valid = False
                movement.errors = ["no se pudo reinterpretar la fila"]
            if movement.valid and movement.amount is not None:
                if movement.amount > 0:
                    movement.kind = "income"
                else:
                    movement.kind = "expense"
        movements.append(movement)
    return movements


def reconcile_balances(movements: list[MovementPreview]) -> tuple[list[int], dict[int, bool]]:
    """Verifica saldo[k] == saldo[k-1] + monto[k] en orden de archivo.

    Devuelve (filas con desajuste, {fila: saldo_ok}).
    """
    mismatches: list[int] = []
    balance_ok: dict[int, bool] = {}
    expected: int | None = None
    for movement in movements:
        if not movement.valid or movement.amount is None:
            continue
        if expected is None:
            if movement.balance is not None:
                expected = movement.balance
            continue
        expected += movement.amount
        if movement.balance is not None:
            balance_ok[movement.row_number] = expected == movement.balance
            if expected != movement.balance:
                mismatches.append(movement.row_number)
                expected = movement.balance
    return mismatches, balance_ok


def attach_duplicates(
    movements: list[MovementPreview],
    existing: list[dict],
    *,
    account_id: str,
    source: str,
) -> None:
    """Marca duplicados por identidad externa y por heurística (monto/fecha/descripción)."""
    identity_hits: dict[str, str] = {}
    heuristic_hits: dict[tuple, list[str]] = {}
    for txn in existing:
        external = meaningful_external_id(txn.get("external_id"))
        if external and txn.get("external_source") == source:
            identity_hits.setdefault(external, txn["id"])
        signed = txn["amount"] if txn.get("type") == "income" else -txn["amount"]
        key = (txn.get("date"), signed, txn.get("description"))
        heuristic_hits.setdefault(key, []).append(txn["id"])

    seen_identity: set[str] = set()
    seen_heuristic: set[tuple] = set()
    for movement in movements:
        if not movement.valid:
            continue
        if movement.external_id:
            identity = movement.external_id
            if identity in seen_identity:
                movement.duplicate = True
                movement.duplicate_type = "identity"
            elif identity in identity_hits:
                movement.duplicate = True
                movement.duplicate_type = "identity"
                movement.duplicate_of = identity_hits[identity]
            seen_identity.add(identity)
            continue
        key = (movement.date, movement.amount, movement.description)
        if key in seen_heuristic:
            movement.duplicate = True
            movement.duplicate_type = "heuristic"
        elif key in heuristic_hits:
            movement.duplicate = True
            movement.duplicate_type = "heuristic"
            movement.duplicate_of = heuristic_hits[key][0]
        else:
            seen_heuristic.add(key)


def suggest_category(rules: list[dict], values: dict) -> str | None:
    """Primera regla (en orden) cuya columna contenga el patrón, sin distinguir mayúsculas."""
    for rule in rules:
        if not rule.get("enabled", True):
            continue
        needle = (rule.get("pattern") or "").strip().lower()
        if not needle:
            continue
        haystack = str(values.get(rule.get("column")) or "").strip().lower()
        if needle in haystack:
            return rule.get("category_id")
    return None
