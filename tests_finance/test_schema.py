"""Validación del contrato de dominio contra el seed ficticio."""

import json
from pathlib import Path

import jsonschema
import pytest

ROOT = Path(__file__).resolve().parents[1]
SEED_PATH = ROOT / "data" / "seed" / "demo-household.json"
SCHEMA_PATH = ROOT / "schemas" / "cuentafaro-domain-model.schema.json"


@pytest.fixture(scope="module")
def seed_document() -> dict:
    return json.loads(SEED_PATH.read_text())


@pytest.fixture(scope="module")
def schema_document() -> dict:
    return json.loads(SCHEMA_PATH.read_text())


def test_seed_is_valid_json(seed_document: dict) -> None:
    assert seed_document["schema_version"] == "1.0"
    assert seed_document["currency"] == "CLP"
    assert seed_document["timezone"] == "America/Santiago"


def test_seed_matches_schema(seed_document: dict, schema_document: dict) -> None:
    jsonschema.validate(  # raises ValidationError on failure
        instance=seed_document, schema=schema_document
    )


def test_required_collections_present(seed_document: dict) -> None:
    required = {
        "households",
        "members",
        "institutions",
        "accounts",
        "categories",
        "income_sources",
        "transactions",
    }
    assert required.issubset(seed_document.keys())


def test_amounts_not_float(seed_document: dict) -> None:
    money_fields = ("amount", "expected_amount", "balance_reported", "balance_calculated")
    records = [
        *seed_document["transactions"],
        *seed_document["income_sources"],
        *seed_document["accounts"],
        *seed_document["debts"],
        *seed_document["installments"],
        *seed_document["debt_payments"],
        *seed_document["budget_categories"],
        *seed_document["financial_goals"],
    ]
    for record in records:
        for field in money_fields:
            if field in record:
                assert isinstance(record[field], int), f"{field} en {record['id']}"
                assert not isinstance(record[field], bool)


def test_ids_are_unique_across_seed(seed_document: dict) -> None:
    seen: dict[str, str] = {}
    for collection, records in seed_document.items():
        if not isinstance(records, list):
            continue
        for record in records:
            record_id = record["id"]
            assert record_id not in seen, f"Duplicado {record_id}"
            seen[record_id] = collection
