"""API de importación de estados de cuenta (Franja A, CF2-02..CF2-05)."""

import io
import json
from datetime import date

import pytest
import xlwt
from fastapi.testclient import TestClient
from openpyxl import Workbook

from cuentafaro.api import create_app
from cuentafaro.db import create_engine_and_session
from cuentafaro.deps import get_session
from cuentafaro.importing.contract import ImportFormatError, parse_date
from cuentafaro.importing.extract import extract_table
from cuentafaro.importing.mapping import normalize_mapping
from cuentafaro.models import Base

CSV_BODY = (
    b"fecha,descripcion,monto,saldo\n"
    b"01/09/2026,Sueldo,1.500.000,1.500.000\n"
    b"02/09/2026,Supermercado,-45.890,1.454.110\n"
    b"03/09/2026,movimiento,mucho,1.454.110\n"
)


@pytest.fixture()
def client(tmp_path):
    engine, session_factory = create_engine_and_session(f"sqlite:///{tmp_path / 'api_imports.db'}")
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


def _household(client, status="active"):
    return client.post(
        "/api/v1/households",
        json={"name": "Hogar Import", "timezone": "America/Santiago", "status": status},
    ).json()


def _account(client, household_id):
    return client.post(
        "/api/v1/accounts",
        json={"household_id": household_id, "name": "Corriente", "type": "checking"},
    ).json()


def _mapping(**overrides):
    mapping = {"date": "fecha", "description": "descripcion", "amount": "monto", "balance": "saldo"}
    mapping.update(overrides)
    return json.dumps(mapping)


def _upload(client, household_id, account_id, *, content=CSV_BODY, filename="mov.csv", **form):
    payload = {
        "account_id": account_id,
        "column_mapping": _mapping(),
        "header_row": str(form.pop("header_row", 1)),
        "source_kind": form.pop("source_kind", ""),
        "separator": form.pop("separator", ""),
    }
    payload.update({key: str(value) for key, value in form.items()})
    return client.post(
        f"/api/v1/households/{household_id}/import-batches",
        data=payload,
        files={"file": (filename, content, "application/octet-stream")},
    )


def test_upload_csv_creates_batch_with_counts(client) -> None:
    household = _household(client)
    account = _account(client, household["id"])
    response = _upload(client, household["id"], account["id"])
    assert response.status_code == 201
    batch = response.json()
    assert batch["id"].startswith("imp_")
    assert batch["account_id"] == account["id"]
    assert batch["source_kind"] == "csv"
    assert batch["status"] == "parsed"
    assert batch["total_rows"] == 3
    assert batch["valid_rows"] == 2
    assert batch["invalid_rows"] == 1
    assert batch["column_mapping"]["amount"] == "monto"
    assert batch["separator"] == ","
    assert "rows" not in batch


def test_upload_excel_creates_batch(client, tmp_path) -> None:
    household = _household(client)
    account = _account(client, household["id"])
    path = tmp_path / "mov.xlsx"
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["fecha", "descripcion", "monto", "saldo"])
    sheet.append(["01/09/2026", "Sueldo", 1500000, 1500000])
    sheet.append(["02/09/2026", "Supermercado", -45890, 1454110])
    workbook.save(path)

    response = _upload(
        client, household["id"], account["id"], content=path.read_bytes(), filename="mov.xlsx"
    )
    assert response.status_code == 201
    batch = response.json()
    assert batch["source_kind"] == "excel"
    assert batch["total_rows"] == 2
    assert batch["valid_rows"] == 2
    assert batch["invalid_rows"] == 0


def test_upload_rejects_missing_required_column(client) -> None:
    household = _household(client)
    account = _account(client, household["id"])
    response = _upload(
        client,
        household["id"],
        account["id"],
        column_mapping=json.dumps({"amount": "monto"}),
    )
    assert response.status_code == 422
    assert "obligatorios" in response.json()["detail"]


def test_upload_rejects_account_from_other_household(client) -> None:
    household_a = _household(client)
    other = _household(client, status="paused")
    account = _account(client, other["id"])
    response = _upload(client, household_a["id"], account["id"])
    assert response.status_code == 422
    assert "no pertenece" in response.json()["detail"]


def test_upload_rejects_unknown_filename_format(client, tmp_path) -> None:
    household = _household(client)
    account = _account(client, household["id"])
    path = tmp_path / "mov.txt"
    path.write_bytes(CSV_BODY)
    response = _upload(
        client, household["id"], account["id"], content=path.read_bytes(), filename="mov.txt"
    )
    assert response.status_code == 422
    assert "formato no soportado" in response.json()["detail"]


def test_list_and_detail_import_batches(client) -> None:
    household = _household(client)
    account = _account(client, household["id"])
    created = _upload(client, household["id"], account["id"]).json()

    listed = client.get(f"/api/v1/households/{household['id']}/import-batches")
    assert listed.status_code == 200
    assert [batch["id"] for batch in listed.json()] == [created["id"]]

    detail = client.get(f"/api/v1/import-batches/{created['id']}")
    assert detail.status_code == 200
    rows = detail.json()["rows"]
    assert len(rows) == 3
    assert rows[0]["row"] == 2
    assert rows[0]["valid"] is True
    assert rows[2]["valid"] is False
    assert any("monto" in error for error in rows[2]["errors"])

    missing = client.get("/api/v1/import-batches/nope")
    assert missing.status_code == 404


# ---------------- Vista previa, duplicados y confirmación (CF2-06..CF2-09) ----------------

CSV_IDENTIDAD = (
    b"fecha,descripcion,monto,saldo,id\n"
    b"01/09/2026,Sueldo,1.500.000,1.500.000,mov-001\n"
    b"02/09/2026,Supermercado,-45.890,1.454.110,mov-002\n"
)

CSV_SOLO_GASTO = b"fecha,descripcion,monto,saldo\n02/09/2026,Supermercado,-45.890,0\n"

CSV_TODO_INVALIDO = b"fecha,descripcion,monto,saldo\nsin fecha,un movimiento,mucho,0\n"


def _account_with_balance(client, household_id, balance=1_000_000):
    return client.post(
        "/api/v1/accounts",
        json={
            "household_id": household_id,
            "name": "Corriente",
            "type": "checking",
            "balance_reported": balance,
        },
    ).json()


def _upload_identidad(client, household_id, account_id, content=CSV_IDENTIDAD):
    return client.post(
        f"/api/v1/households/{household_id}/import-batches",
        data={
            "account_id": account_id,
            "column_mapping": json.dumps(
                {
                    "date": "fecha",
                    "description": "descripcion",
                    "amount": "monto",
                    "balance": "saldo",
                    "external_id": "id",
                }
            ),
            "header_row": "1",
            "source_kind": "",
            "separator": "",
        },
        files={"file": ("estado.csv", content, "application/octet-stream")},
    )


def test_preview_reports_duplicates_and_balance(client) -> None:
    household = _household(client)
    account = _account_with_balance(client, household["id"])
    batch = _upload(client, household["id"], account["id"]).json()
    preview = client.get(f"/api/v1/import-batches/{batch['id']}/preview")
    assert preview.status_code == 200
    rows = preview.json()["rows"]
    assert rows[0]["date"] == "2026-09-01"
    assert rows[0]["kind"] == "income"
    assert rows[0]["amount"] == 1_500_000
    assert rows[0]["duplicate"] is False
    assert preview.json()["duplicate_rows"] == 0
    assert preview.json()["reconciliation_mismatches"] == 0
    assert rows[1]["balance_ok"] is True
    assert rows[2]["valid"] is False


def test_confirm_creates_transactions_and_updates_balance(client) -> None:
    household = _household(client)
    account = _account_with_balance(client, household["id"])
    batch = _upload(client, household["id"], account["id"]).json()
    response = client.post(f"/api/v1/import-batches/{batch['id']}/confirm")
    assert response.status_code == 200
    result = response.json()
    assert result["status"] == "confirmed"
    assert result["created"] == 2
    assert result["queued_for_review"] == 1
    assert result["skipped_duplicates"] == 0

    updated = client.get(f"/api/v1/accounts/{account['id']}").json()
    assert updated["balance_calculated"] == 2_454_110

    listed = client.get("/api/v1/transactions")
    transactions = [tx for tx in listed.json() if tx["account_id"] == account["id"]]
    assert len(transactions) == 2
    assert all(tx["import_batch_id"] == batch["id"] for tx in transactions)
    assert {tx["type"] for tx in transactions} == {"income", "expense"}


def test_confirm_twice_is_rejected(client) -> None:
    household = _household(client)
    account = _account_with_balance(client, household["id"])
    batch = _upload(client, household["id"], account["id"]).json()
    assert client.post(f"/api/v1/import-batches/{batch['id']}/confirm").status_code == 200
    second = client.post(f"/api/v1/import-batches/{batch['id']}/confirm")
    assert second.status_code == 422
    assert "ya fue procesado" in second.json()["detail"]


def test_reimport_same_file_skips_identity_duplicates(client) -> None:
    household = _household(client)
    account = _account_with_balance(client, household["id"])
    first = _upload_identidad(client, household["id"], account["id"]).json()
    client.post(f"/api/v1/import-batches/{first['id']}/confirm")

    second = _upload_identidad(client, household["id"], account["id"]).json()
    preview = client.get(f"/api/v1/import-batches/{second['id']}/preview").json()
    assert preview["duplicate_rows"] == 2
    result = client.post(f"/api/v1/import-batches/{second['id']}/confirm").json()
    assert result["created"] == 0
    assert result["skipped_duplicates"] == 2
    assert result["queued_for_review"] == 0
    assert result["status"] == "confirmed"

    reviews = client.get("/api/v1/import-reviews", params={"household_id": household["id"]}).json()
    assert reviews == []

    listed = client.get("/api/v1/transactions")
    count = sum(1 for tx in listed.json() if tx["account_id"] == account["id"])
    assert count == 2


def test_confirm_heuristic_duplicates_go_to_review_queue(client) -> None:
    household = _household(client)
    account = _account_with_balance(client, household["id"])
    manual = client.post(
        "/api/v1/transactions",
        json={
            "account_id": account["id"],
            "type": "expense",
            "amount": 45890,
            "date": "2026-09-02",
            "description": "Supermercado",
        },
    )
    assert manual.status_code == 201

    batch = _upload(client, household["id"], account["id"]).json()
    preview = client.get(f"/api/v1/import-batches/{batch['id']}/preview").json()
    gasto = [row for row in preview["rows"] if row["kind"] == "expense"][0]
    assert gasto["duplicate"] is True
    assert gasto["duplicate_type"] == "heuristic"

    result = client.post(f"/api/v1/import-batches/{batch['id']}/confirm").json()
    assert result["created"] == 1
    assert result["queued_for_review"] == 2
    assert result["skipped_duplicates"] == 0

    reviews = client.get("/api/v1/import-reviews", params={"household_id": household["id"]}).json()
    assert len(reviews) == 2
    assert {item["kind"] for item in reviews} == {"duplicate", "invalid"}
    duplicate = next(item for item in reviews if item["kind"] == "duplicate")
    assert duplicate["status"] == "pending"
    assert duplicate["source_filename"] == "mov.csv"
    assert duplicate["row_number"] == 3


def test_confirm_all_invalid_rows_are_queued_for_review(client) -> None:
    household = _household(client)
    account = _account_with_balance(client, household["id"])
    batch = _upload(client, household["id"], account["id"], content=CSV_TODO_INVALIDO).json()
    assert batch["valid_rows"] == 0
    response = client.post(f"/api/v1/import-batches/{batch['id']}/confirm")
    assert response.status_code == 200
    result = response.json()
    assert result["status"] == "confirmed"
    assert result["created"] == 0
    assert result["queued_for_review"] == 1


# ---------------- Cola de revisión (CF2-10, CF2-11) ----------------


def test_review_resolve_confirm_duplicate_creates_transaction(client) -> None:
    household = _household(client)
    account = _account_with_balance(client, household["id"])
    client.post(
        "/api/v1/transactions",
        json={
            "account_id": account["id"],
            "type": "expense",
            "amount": 45890,
            "date": "2026-09-02",
            "description": "Supermercado",
        },
    )

    batch = _upload(client, household["id"], account["id"], content=CSV_SOLO_GASTO).json()
    result = client.post(f"/api/v1/import-batches/{batch['id']}/confirm").json()
    assert result["created"] == 0
    assert result["queued_for_review"] == 1

    reviews = client.get("/api/v1/import-reviews", params={"household_id": household["id"]}).json()
    assert len(reviews) == 1
    review = reviews[0]
    assert review["kind"] == "duplicate"
    assert review["status"] == "pending"
    assert review["account_id"] == account["id"]

    resolved = client.post(
        f"/api/v1/import-reviews/{review['id']}/resolve", json={"action": "confirm"}
    )
    assert resolved.status_code == 200
    assert resolved.json()["status"] == "resolved"
    transaction_id = resolved.json()["transaction_id"]
    assert transaction_id.startswith("txn_")

    updated = client.get(f"/api/v1/accounts/{account['id']}").json()
    assert updated["balance_calculated"] == 908_220
    listed = client.get("/api/v1/transactions")
    count = sum(1 for tx in listed.json() if tx["account_id"] == account["id"])
    assert count == 2

    second = client.post(
        f"/api/v1/import-reviews/{review['id']}/resolve", json={"action": "discard"}
    )
    assert second.status_code == 422
    assert "ya fue procesado" in second.json()["detail"]


def test_review_resolve_correct_invalid_and_discard(client) -> None:
    household = _household(client)
    account = _account_with_balance(client, household["id"])
    batch = _upload(client, household["id"], account["id"], content=CSV_TODO_INVALIDO).json()
    client.post(f"/api/v1/import-batches/{batch['id']}/confirm")

    reviews = client.get("/api/v1/import-reviews", params={"household_id": household["id"]}).json()
    review = reviews[0]
    assert review["kind"] == "invalid"

    without_values = client.post(
        f"/api/v1/import-reviews/{review['id']}/resolve", json={"action": "confirm"}
    )
    assert without_values.status_code == 422
    assert "Corrija" in without_values.json()["detail"]

    bad_values = client.post(
        f"/api/v1/import-reviews/{review['id']}/resolve",
        json={"action": "correct", "values": {"date": "03/09/2026", "amount": "mucho"}},
    )
    assert bad_values.status_code == 422
    assert "inválidos" in bad_values.json()["detail"]

    correct = client.post(
        f"/api/v1/import-reviews/{review['id']}/resolve",
        json={
            "action": "correct",
            "values": {
                "date": "03/09/2026",
                "amount": "-1.000",
                "description": "Movimiento incompleto",
            },
        },
    )
    assert correct.status_code == 200
    assert correct.json()["status"] == "resolved"
    transaction_id = correct.json()["transaction_id"]

    listed = client.get("/api/v1/transactions")
    created = [tx for tx in listed.json() if tx["id"] == transaction_id]
    assert len(created) == 1
    assert created[0]["amount"] == 1000
    assert created[0]["type"] == "expense"


def test_review_resolve_discard_does_not_create_transaction(client) -> None:
    household = _household(client)
    account = _account_with_balance(client, household["id"])
    client.post(
        "/api/v1/transactions",
        json={
            "account_id": account["id"],
            "type": "expense",
            "amount": 45890,
            "date": "2026-09-02",
            "description": "Supermercado",
        },
    )
    batch = _upload(client, household["id"], account["id"], content=CSV_SOLO_GASTO).json()
    client.post(f"/api/v1/import-batches/{batch['id']}/confirm")
    review = client.get("/api/v1/import-reviews", params={"household_id": household["id"]}).json()[
        0
    ]

    response = client.post(
        f"/api/v1/import-reviews/{review['id']}/resolve", json={"action": "discard"}
    )
    assert response.status_code == 200
    assert response.json()["status"] == "discarded"
    assert response.json()["transaction_id"] is None

    listed = client.get("/api/v1/transactions")
    count = sum(1 for tx in listed.json() if tx["account_id"] == account["id"])
    assert count == 1


def test_review_resolve_applies_category(client) -> None:
    household = _household(client)
    account = _account_with_balance(client, household["id"])
    categories = client.get(f"/api/v1/households/{household['id']}/categories").json()
    food = next(cat for cat in categories if cat["name"] == "Alimentación")
    client.post(
        "/api/v1/transactions",
        json={
            "account_id": account["id"],
            "type": "expense",
            "amount": 45890,
            "date": "2026-09-02",
            "description": "Supermercado",
        },
    )

    batch = _upload(client, household["id"], account["id"], content=CSV_SOLO_GASTO).json()
    client.post(f"/api/v1/import-batches/{batch['id']}/confirm")
    review = client.get("/api/v1/import-reviews", params={"household_id": household["id"]}).json()[
        0
    ]

    resolved = client.post(
        f"/api/v1/import-reviews/{review['id']}/resolve",
        json={"action": "confirm", "category_id": food["id"]},
    ).json()
    transaction_id = resolved["transaction_id"]
    listed = client.get("/api/v1/transactions")
    created = [tx for tx in listed.json() if tx["id"] == transaction_id]
    assert created[0]["category_id"] == food["id"]


# ---------------- Reglas de categoría (CF2-12) ----------------


def _food_category(client, household_id):
    categories = client.get(f"/api/v1/households/{household_id}/categories").json()
    return next(cat for cat in categories if cat["name"] == "Alimentación")


def _create_rule(client, household_id, category_id, pattern="super", column="description"):
    return client.post(
        f"/api/v1/households/{household_id}/import-category-rules",
        json={"column": column, "pattern": pattern, "category_id": category_id},
    )


def test_category_rule_crud_and_suggestion_in_preview_and_confirm(client) -> None:
    household = _household(client)
    account = _account_with_balance(client, household["id"])
    food = _food_category(client, household["id"])

    created = _create_rule(client, household["id"], food["id"])
    assert created.status_code == 201
    rule = created.json()
    assert rule["column"] == "description"
    assert rule["enabled"] is True

    listed = client.get(f"/api/v1/households/{household['id']}/import-category-rules")
    assert [item["id"] for item in listed.json()] == [rule["id"]]

    batch = _upload(client, household["id"], account["id"], content=CSV_SOLO_GASTO).json()
    preview = client.get(f"/api/v1/import-batches/{batch['id']}/preview").json()
    assert preview["rows"][0]["suggested_category_id"] == food["id"]

    result = client.post(f"/api/v1/import-batches/{batch['id']}/confirm").json()
    assert result["created"] == 1
    listed = client.get("/api/v1/transactions")
    created_tx = [tx for tx in listed.json() if tx["account_id"] == account["id"]][0]
    assert created_tx["category_id"] == food["id"]

    disabled = client.patch(f"/api/v1/import-category-rules/{rule['id']}", json={"enabled": False})
    assert disabled.json()["enabled"] is False

    second = _upload(client, household["id"], account["id"], content=CSV_SOLO_GASTO).json()
    preview = client.get(f"/api/v1/import-batches/{second['id']}/preview").json()
    assert preview["rows"][0]["suggested_category_id"] is None

    deleted = client.delete(f"/api/v1/import-category-rules/{rule['id']}")
    assert deleted.status_code == 204
    listed = client.get(f"/api/v1/households/{household['id']}/import-category-rules")
    assert listed.json() == []


def test_category_rule_validations(client) -> None:
    household = _household(client)
    other = _household(client, status="paused")
    food = _food_category(client, household["id"])

    unknown_column = _create_rule(client, household["id"], food["id"], column="sin_columna")
    assert unknown_column.status_code == 422
    assert "no existe en el contrato" in unknown_column.json()["detail"]

    other_categories = client.get(f"/api/v1/households/{other['id']}/categories").json()
    other_food = next(cat for cat in other_categories if cat["name"] == "Alimentación")
    foreign_category = _create_rule(client, household["id"], other_food["id"])
    assert foreign_category.status_code == 422
    assert "no pertenece al hogar" in foreign_category.json()["detail"]


def test_category_rule_kind_mismatch_is_not_applied(client) -> None:
    household = _household(client)
    account = _account_with_balance(client, household["id"])
    categories = client.get(f"/api/v1/households/{household['id']}/categories").json()
    income = next(cat for cat in categories if cat["name"] == "Ingreso del trabajo")

    _create_rule(client, household["id"], income["id"])
    batch = _upload(client, household["id"], account["id"], content=CSV_SOLO_GASTO).json()
    preview = client.get(f"/api/v1/import-batches/{batch['id']}/preview").json()
    assert preview["rows"][0]["suggested_category_id"] is None

    client.post(f"/api/v1/import-batches/{batch['id']}/confirm")
    listed = client.get("/api/v1/transactions")
    created_tx = [tx for tx in listed.json() if tx["account_id"] == account["id"]][0]
    assert created_tx["category_id"] is None


def _cartola_xls_bytes() -> bytes:
    """Cartola sintética (estilo Itaú, .xls OLE2): bloque de datos del cliente,
    cabecera de movimientos en la fila 6 y tres filas de movimientos."""
    workbook = xlwt.Workbook()
    sheet = workbook.add_sheet("Sheet1")
    rows = [
        ["Detalle de Cartola Histórica"],
        [""],
        ["Nombre", "CLIENTE DE PRUEBA"],
        ["Período", "01-Ago-2026 - 31-Ago-2026"],
        [""],
        ["Fecha", "N° de operación", "Movimientos", "Cargos", "Abonos", "Saldo"],
        ["03/08", "585771651", "Transferencia A Toku Spa", 360837.0, 0.0, 1587803.0],
        ["04/08", "585773800", "Transferencia De Marcano Perez", 0.0, 1900000.0, 1948640.0],
        ["05/08", "000000000", "movimiento de cero", 0.0, 0.0, 0.0],
    ]
    for row_index, row in enumerate(rows):
        for col_index, value in enumerate(row):
            sheet.write(row_index, col_index, value)
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def test_parse_date_completes_year_from_period() -> None:
    assert parse_date("03/08", default_year=2026) == date(2026, 8, 3)
    assert parse_date("03-08", default_year=2026) == date(2026, 8, 3)
    assert parse_date("03/08/2026", default_year=2026) == date(2026, 8, 3)
    with pytest.raises(ImportFormatError):
        parse_date("03/08")


def test_extract_legacy_xls_auto_detects_table_and_period_year() -> None:
    table = extract_table(_cartola_xls_bytes(), source_kind="excel", header_row=1)
    assert table.headers == ["Fecha", "N° de operación", "Movimientos", "Cargos", "Abonos", "Saldo"]
    assert table.first_row_number == 7
    assert table.default_year == 2026
    assert len(table.rows) == 3


def test_normalize_mapping_auto_fills_cartola_by_alias() -> None:
    mapping = normalize_mapping(
        {}, ["Fecha", "N° de operación", "Movimientos", "Cargos", "Abonos", "Saldo"]
    )
    assert mapping["date"] == "Fecha"
    assert mapping["description"] == "Movimientos"
    assert mapping["cargos"] == "Cargos"
    assert mapping["abonos"] == "Abonos"
    assert "amount" not in mapping


def test_upload_legacy_xls_cartola_parses_signed_amounts(client) -> None:
    household = _household(client)
    account = _account(client, household["id"])
    response = _upload(
        client,
        household["id"],
        account["id"],
        content=_cartola_xls_bytes(),
        filename="cartola.xls",
        column_mapping=json.dumps({}),
    )
    assert response.status_code == 201
    batch = response.json()
    assert batch["source_kind"] == "excel"
    assert batch["header_row"] == 6
    assert batch["total_rows"] == 3
    assert batch["valid_rows"] == 2
    assert batch["invalid_rows"] == 1

    preview = client.get(f"/api/v1/import-batches/{batch['id']}/preview").json()
    movements = {row["row"]: row for row in preview["rows"]}
    expense = movements[7]
    income = movements[8]
    assert expense["kind"] == "expense"
    assert expense["amount"] == -360837
    assert income["kind"] == "income"
    assert income["amount"] == 1900000


def _card_account(client, household_id):
    return client.post(
        "/api/v1/accounts",
        json={
            "household_id": household_id,
            "name": "Visa Itaú",
            "type": "credit_card",
            "credit_limit": 2000000,
            "balance_reported": 0,
            "statement_day": 31,
            "due_day": 10,
        },
    ).json()


def _card_cartola_xls_bytes() -> bytes:
    """Cartola de tarjeta sintética (estilo Itaú): resumen sobre la cabecera y
    dos compras en la tabla de movimientos."""
    workbook = xlwt.Workbook()
    sheet = workbook.add_sheet("Sheet1")
    rows = [
        ["ESTADO DE CUENTA", "TARJETA DE CREDITO"],
        ["Nombre", "CLIENTE DE PRUEBA"],
        ["Período", "01-Ago-2026 - 31-Ago-2026"],
        ["Fecha de vencimiento", "28/09/2026"],
        ["Total a Pagar", 1234567.0],
        ["Pago Mínimo", 150000.0],
        ["Saldo Deudor del Estado de Cuenta", 2345678.0],
        ["Cupo Total", 3000000.0],
        [""],
        ["Fecha", "N° de operación", "Comercio", "Cargos", "Abonos", "Saldo"],
        ["03/08", "585771651", "Supermercado La Polar", 150000.0, 0.0, 2345678.0],
        ["04/08", "585773800", "Farmacia Ahumada", 45000.0, 0.0, 2300678.0],
    ]
    for row_index, row in enumerate(rows):
        for col_index, value in enumerate(row):
            if value == "":
                continue
            sheet.write(row_index, col_index, value)
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def test_upload_card_cartola_detects_statement_and_links_debt(client) -> None:
    household = _household(client)
    account = _card_account(client, household["id"])
    response = _upload(
        client,
        household["id"],
        account["id"],
        content=_card_cartola_xls_bytes(),
        filename="tarjeta.xls",
        column_mapping=json.dumps({}),
    )
    assert response.status_code == 201
    batch = response.json()
    assert batch["source_kind"] == "excel"
    assert batch["total_rows"] == 2
    assert batch["statement_meta"]["total_to_pay"] == 1_234_567
    assert batch["statement_meta"]["minimum_payment"] == 150_000
    assert batch["statement_meta"]["total_debt"] == 2_345_678
    assert batch["statement_meta"]["due_date"] == "2026-09-28"
    assert batch["statement_meta"]["credit_limit"] == 3_000_000

    preview = client.get(f"/api/v1/import-batches/{batch['id']}/preview").json()
    assert preview["account_type"] == "credit_card"
    assert preview["statement_meta"]["minimum_payment"] == 150_000

    assert client.get(f"/api/v1/households/{household['id']}/debts").json() == []

    confirmed = client.post(f"/api/v1/import-batches/{batch['id']}/confirm").json()
    assert confirmed["status"] == "confirmed"
    assert confirmed["created"] == 2
    card = confirmed["card_statement"]
    assert card["debt_created"] is True
    assert card["total_debt"] == 2_345_678
    assert card["due_day"] == 28

    account_view = client.get(f"/api/v1/accounts/{account['id']}").json()
    assert account_view["balance_reported"] == 2_345_678
    assert account_view["due_day"] == 28
    assert account_view["credit_limit"] == 3_000_000

    debts = client.get(f"/api/v1/households/{household['id']}/debts").json()
    assert len(debts) == 1
    debt = debts[0]
    assert debt["account_id"] == account["id"]
    assert debt["type"] == "credit_card"
    assert debt["current_balance"] == 2_345_678
    assert debt["minimum_payment"] == 150_000
    assert debt["due_day"] == 28

    # Las compras de la cartola quedan asociadas a la tarjeta (gastos del mes).
    card_only = [
        txn
        for txn in client.get("/api/v1/transactions").json()
        if txn["account_id"] == account["id"]
    ]
    assert len(card_only) == 2
    assert {txn["type"] for txn in card_only} == {"expense"}


def test_confirm_card_cartola_updates_existing_linked_debt(client) -> None:
    household = _household(client)
    account = _card_account(client, household["id"])
    debt = client.post(
        f"/api/v1/households/{household['id']}/debts",
        json={
            "account_id": account["id"],
            "name": "Visa Itaú",
            "type": "credit_card",
            "original_amount": 1000000,
            "minimum_payment": 0,
            "interest_rate": 2.0,
            "due_day": 10,
            "status": "active",
        },
    ).json()

    batch = _upload(
        client,
        household["id"],
        account["id"],
        content=_card_cartola_xls_bytes(),
        filename="tarjeta.xls",
        column_mapping=json.dumps({}),
    ).json()
    confirmed = client.post(f"/api/v1/import-batches/{batch['id']}/confirm").json()
    card = confirmed["card_statement"]
    assert card["debt_created"] is False
    assert card["debt_id"] == debt["id"]

    updated = client.get(f"/api/v1/debts/{debt['id']}").json()
    assert updated["current_balance"] == 2_345_678
    assert updated["minimum_payment"] == 150_000
    assert updated["due_day"] == 28
