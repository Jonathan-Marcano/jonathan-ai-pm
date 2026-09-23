from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import jsonschema
from sqlalchemy.orm import Session

from cuentafaro.models import (
    Budget,
    BudgetCategory,
    Category,
    Debt,
    DebtPayment,
    FinancialAccount,
    FinancialInstitution,
    Household,
    HouseholdMember,
    IncomeSource,
    Installment,
    Transaction,
)

ROOT = Path(__file__).resolve().parents[2]
SEED_PATH = ROOT / "data" / "seed" / "demo-household.json"
_SCHEMA_CANDIDATES = (
    ROOT / "schemas" / "cuentafaro-domain-model.schema.json",
    ROOT / "schemas" / "domain-model.schema.json",
)
SCHEMA_PATH = next(
    (candidate for candidate in _SCHEMA_CANDIDATES if candidate.exists()),
    _SCHEMA_CANDIDATES[0],
)

DEBT_TYPE_ALIASES = {"personal": "loan"}
INTEREST_NORMALIZE_MIN = 100.0


def load_seed_document(seed_path: Path = SEED_PATH) -> dict:
    return json.loads(seed_path.read_text(encoding="utf-8"))


def validate_seed_document(document: dict, schema_path: Path = SCHEMA_PATH) -> None:
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    jsonschema.validate(instance=document, schema=schema)


def seed_summary(document: dict) -> dict:
    counts = {key: len(items) for key, items in document.items() if isinstance(items, list)}
    return {"schema_version": document["schema_version"], "counts": counts}


def _as_date(value: str) -> date:
    return date.fromisoformat(value)


def persist_demo_seed(session: Session, document: dict) -> dict:
    """Persiste el dataset ficticio en la base. Lanzar sin duplicados: si el
    hogar de demostración ya existe, se aborta para no romper unicidad."""
    demo_home_id = document["households"][0]["id"]
    if session.get(Household, demo_home_id) is not None:
        raise ValueError(
            f"El hogar de demostración '{demo_home_id}' ya existe; "
            "utilice restore o una base vacía para volver a cargarlo."
        )

    for item in document.get("households", []):
        session.add(
            Household(
                id=item["id"], name=item["name"], status=item["status"], timezone=item["timezone"]
            )
        )
    session.flush()
    for item in document.get("members", []):
        session.add(
            HouseholdMember(
                id=item["id"],
                household_id=item["household_id"],
                name=item["name"],
                role=item["role"],
                status=item["status"],
            )
        )
    for item in document.get("institutions", []):
        session.add(
            FinancialInstitution(
                id=item["id"], name=item["name"], type=item["type"], status=item["status"]
            )
        )
    session.flush()
    for item in document.get("accounts", []):
        session.add(
            FinancialAccount(
                id=item["id"],
                household_id=item["household_id"],
                institution_id=item.get("institution_id"),
                name=item["name"],
                type=item["type"],
                currency=item.get("currency", "CLP"),
                balance_reported=item["balance_reported"],
                balance_calculated=item["balance_calculated"],
                original_amount=item.get("original_amount"),
                status=item.get("status", "active"),
            )
        )
    session.flush()
    for item in document.get("categories", []):
        session.add(
            Category(
                id=item["id"],
                household_id=item["household_id"],
                name=item["name"],
                kind=item["kind"],
                status=item.get("status", "active"),
            )
        )
    for item in document.get("income_sources", []):
        session.add(
            IncomeSource(
                id=item["id"],
                household_id=item["household_id"],
                member_id=item.get("member_id"),
                name=item["name"],
                type=item.get("type", "salary"),
                expected_amount=item.get("expected_amount", 0),
                frequency=item.get("frequency", "monthly"),
                status=item.get("status", "active"),
            )
        )
    session.flush()
    for item in document.get("transactions", []):
        session.add(
            Transaction(
                id=item["id"],
                account_id=item["account_id"],
                to_account_id=item.get("transfer_account_id") if item.get("is_transfer") else None,
                category_id=item.get("category_id"),
                recorded_by=item.get("member_id"),
                type=item["type"],
                amount=item["amount"],
                date=_as_date(item["date"]),
                description=item.get("description"),
                status=item.get("status", "posted"),
            )
        )
    for item in document.get("budgets", []):
        year, month = item["year_month"].split("-")
        session.add(
            Budget(
                id=item["id"],
                household_id=item["household_id"],
                year=int(year),
                month=int(month),
                status=item.get("status", "active"),
            )
        )
    session.flush()
    for item in document.get("budget_categories", []):
        session.add(
            BudgetCategory(
                id=item["id"],
                budget_id=item["budget_id"],
                category_id=item["category_id"],
                planned_amount=item["planned_amount"],
                actual_amount=item["actual_amount"],
            )
        )
    for item in document.get("debts", []):
        rate = float(item.get("interest_rate", 0))
        if rate >= INTEREST_NORMALIZE_MIN:
            rate /= 100
        session.add(
            Debt(
                id=item["id"],
                household_id=item["household_id"],
                account_id=item.get("account_id"),
                name=item["name"],
                type=DEBT_TYPE_ALIASES.get(item["type"], item["type"]),
                original_amount=item["original_amount"],
                current_balance=item["current_balance"],
                interest_rate=rate,
                minimum_payment=item.get("minimum_payment", 0),
                due_day=item.get("due_day", 1),
                status=item.get("status", "active"),
            )
        )
    session.flush()
    for item in document.get("installments", []):
        session.add(
            Installment(
                id=item["id"],
                debt_id=item["debt_id"],
                due_date=_as_date(item["due_date"]),
                principal_amount=item.get("principal_amount", 0),
                interest_amount=item.get("interest_amount", 0),
                fee_amount=item.get("fee_amount", 0),
                total_amount=item["total_amount"],
                status=item.get("status", "pending"),
            )
        )
    for item in document.get("debt_payments", []):
        payment_type = "extraordinary" if item.get("type") == "extraordinary" else "ordinary"
        session.add(
            DebtPayment(
                id=item["id"],
                debt_id=item["debt_id"],
                amount=item["amount"],
                type=payment_type,
                payment_date=_as_date(item["payment_date"]),
            )
        )

    session.flush()
    session.commit()

    loaded = seed_summary(document)
    skipped = [key for key in ("financial_goals",) if key in document]
    return {
        "schema_version": loaded["schema_version"],
        "counts": loaded["counts"],
        "skipped": skipped,
    }
