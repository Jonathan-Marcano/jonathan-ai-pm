"""Contrato, mapeo, extracción y parser de importación (CF2-01..CF2-05)."""

from datetime import date

import pytest

from cuentafaro.importing import (
    ImportFormatError,
    attach_duplicates,
    build_movement_previews,
    detect_card_statement,
    extract_table,
    normalize_mapping,
    parse_amount,
    parse_batch,
    reconcile_balances,
    suggest_category,
)
from cuentafaro.importing.contract import parse_date
from cuentafaro.importing.extract import ExtractedTable
from cuentafaro.importing.mapping import FIELD_BY_KEY


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("1500000", 1_500_000),
        ("1.500.000", 1_500_000),
        ("1.500.000,50", 1_500_001),
        ("$1.234", 1_234),
        ("CLP 2.500", 2_500),
        ("1,234", 1_234),
        ("1234,56", 1_235),
        ("1,234.56", 1_235),
        ("1234.56", 1_235),
        ("-45.890", -45_890),
        ("12,345", 12_345),
        ("1.234.567", 1_234_567),
        ("0", 0),
    ],
)
def test_parse_amount(raw: str, expected: int) -> None:
    assert parse_amount(raw) == expected


@pytest.mark.parametrize("raw", ["", "  ", "abc", "1.2.3,4,5", "monto"])
def test_parse_amount_rejects_invalid(raw: str) -> None:
    with pytest.raises(ImportFormatError):
        parse_amount(raw)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("01/09/2026", "2026-09-01"),
        ("2026-09-01", "2026-09-01"),
        ("2026/09/01", "2026-09-01"),
        ("01-09-2026", "2026-09-01"),
        ("01.09.2026", "2026-09-01"),
    ],
)
def test_parse_date(raw: str, expected: str) -> None:
    assert parse_date(raw).isoformat() == expected


def test_parse_date_rejects_invalid() -> None:
    with pytest.raises(ImportFormatError):
        parse_date("nunca 2026")


CSV_FECHA = "fecha,descripcion,monto,saldo"


def _csv(*rows: str, sep: str = ",") -> str:
    return "\n".join([CSV_FECHA.replace(",", sep), *rows])


def test_extract_csv_autodetect_semicolon() -> None:
    content = _csv(
        "01/09/2026;Sueldo;1.500.000;1.500.000",
        "02/09/2026;Supermercado;-45.890;1.454.110",
        sep=";",
    ).encode()
    table = extract_table(content, source_kind="csv")
    assert table.headers == ["fecha", "descripcion", "monto", "saldo"]
    assert table.separator == ";"
    assert [row["monto"] for row in table.rows] == ["1.500.000", "-45.890"]
    assert table.first_row_number == 2


def test_extract_csv_header_row_offset() -> None:
    content = (
        b"Banco Demo\nEstado de cuenta\n"
        b"fecha,descripcion,monto,saldo\n"
        b"01/09/2026,Sueldo,1.500.000,1.500.000\n"
    )
    table = extract_table(content, source_kind="csv", header_row=3)
    assert table.first_row_number == 4
    assert table.rows[0]["descripcion"] == "Sueldo"


def test_extract_csv_duplicated_headers_rejected() -> None:
    content = b"fecha,fecha,monto\n01/09/2026,01/09/2026,100\n"
    with pytest.raises(ImportFormatError, match="duplicados"):
        extract_table(content, source_kind="csv")


def test_extract_excel(tmp_path) -> None:
    from openpyxl import Workbook

    path = tmp_path / "mov.xlsx"
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["fecha", "descripcion", "monto", "saldo"])
    sheet.append([__import__("datetime").date(2026, 9, 1), "Sueldo", 1500000, 1500000])
    sheet.append(["02/09/2026", "Supermercado", -45890, 1454110])
    workbook.save(path)

    table = extract_table(path.read_bytes(), source_kind="excel")
    assert table.headers == ["fecha", "descripcion", "monto", "saldo"]
    assert table.separator is None
    assert [row["monto"] for row in table.rows] == ["1500000", "-45890"]
    assert table.rows[0]["fecha"] == "2026-09-01"


def test_extract_excel_corrupt(tmp_path) -> None:
    with pytest.raises(ImportFormatError, match="Excel"):
        extract_table(b"garbage", source_kind="excel")


def test_normalize_mapping_valid() -> None:
    mapping = normalize_mapping(
        {"date": "fecha", "amount": "monto", "description": "descripcion"},
        ["fecha", "descripcion", "monto", "saldo"],
    )
    assert mapping == {"date": "fecha", "description": "descripcion", "amount": "monto"}


def test_normalize_mapping_missing_required() -> None:
    with pytest.raises(ImportFormatError, match="obligatorios"):
        normalize_mapping({"amount": "monto"}, ["fecha", "monto"])


def test_normalize_mapping_unknown_key() -> None:
    with pytest.raises(ImportFormatError, match="desconocidos"):
        normalize_mapping({"date": "fecha", "nope": "x"}, ["fecha", "x"])


def test_normalize_mapping_column_not_found() -> None:
    with pytest.raises(ImportFormatError, match="no existe"):
        normalize_mapping({"date": "ausente"}, ["fecha"])


def test_parse_batch_counts_valid_and_invalid() -> None:
    content = _csv(
        "01/09/2026,Sueldo,1.500.000,1.500.000",
        "02/09/2026,Supermercado,-45.890,1.454.110",
        "03/09/2026,movimiento,mucho,1.454.110",
        "04/09/2026,sin monto,,1.454.110",
        "30/02/2026,sin fecha valida,-1.000,1.453.110",
    ).encode()
    table = extract_table(content, source_kind="csv")
    mapping = normalize_mapping(
        {"date": "fecha", "amount": "monto", "description": "descripcion"}, table.headers
    )
    parsed = parse_batch(table, mapping)
    assert parsed.total_rows == 5
    assert parsed.valid_rows == 2
    assert parsed.invalid_rows == 3
    invalid = {row.row_number: row.errors for row in parsed.rows if not row.valid}
    assert any("monto" in "".join(errors) for errors in invalid.values())
    assert parsed.rows[0].row_number == 2


def test_parse_batch_unmapped_optional_field_is_none() -> None:
    content = _csv("01/09/2026,Sueldo,1.500.000,1.500.000").encode()
    table = extract_table(content, source_kind="csv")
    mapping = normalize_mapping({"date": "fecha", "amount": "monto"}, table.headers)
    parsed = parse_batch(table, mapping)
    assert parsed.rows[0].values["external_id"] is None
    assert parsed.rows[0].values["balance"] is None
    assert set(parsed.rows[0].values) == set(FIELD_BY_KEY)


def test_parse_batch_zero_amount_invalid() -> None:
    content = _csv("01/09/2026,sin costo,0,0").encode()
    table = extract_table(content, source_kind="csv")
    mapping = normalize_mapping({"date": "fecha", "amount": "monto"}, table.headers)
    parsed = parse_batch(table, mapping)
    assert parsed.invalid_rows == 1
    assert "distinto de cero" in parsed.rows[0].errors[0]


# ---------------- Vista previa, duplicados y conciliación (CF2-06..CF2-08) ----------------


def _stored_row(row_number: int, values: dict, valid: bool = True, errors: list | None = None):
    return {"row": row_number, "values": values, "valid": valid, "errors": errors or []}


def _rows(*specs):
    return [
        {"row": number, "values": values, "valid": valid, "errors": errors}
        for number, values, valid, errors in specs
    ]


def test_build_movement_previews_kind_and_parsing() -> None:
    rows = [
        _stored_row(2, {"date": "01/09/2026", "amount": "1.500.000", "balance": "1.500.000"}),
        _stored_row(3, {"date": "02/09/2026", "amount": "-45.890", "description": "Mercado"}),
        _stored_row(
            4,
            {"date": "03/09/2026", "amount": "mucho"},
            valid=False,
            errors=["Monto (CLP): monto inválido"],
        ),
    ]
    movements = build_movement_previews(rows)
    assert movements[0].kind == "income"
    assert movements[0].amount == 1_500_000
    assert movements[0].date.isoformat() == "2026-09-01"
    assert movements[1].kind == "expense"
    assert movements[1].amount == -45_890
    assert movements[1].description == "Mercado"
    assert movements[2].valid is False
    assert movements[2].kind is None


def test_reconcile_balances_consistent() -> None:
    rows = [
        _stored_row(2, {"date": "01/09/2026", "amount": "1.500.000", "balance": "1.500.000"}),
        _stored_row(3, {"date": "02/09/2026", "amount": "-45.890", "balance": "1.454.110"}),
    ]
    movements = build_movement_previews(rows)
    mismatches, balance_ok = reconcile_balances(movements)
    assert mismatches == []
    assert balance_ok == {3: True}


def test_reconcile_balances_detects_mismatch() -> None:
    rows = [
        _stored_row(2, {"date": "01/09/2026", "amount": "1.500.000", "balance": "1.500.000"}),
        _stored_row(3, {"date": "02/09/2026", "amount": "-45.890", "balance": "1.500.000"}),
    ]
    movements = build_movement_previews(rows)
    mismatches, balance_ok = reconcile_balances(movements)
    assert mismatches == [3]
    assert balance_ok[3] is False


def test_attach_duplicates_by_identity() -> None:
    rows = [
        _stored_row(2, {"date": "01/09/2026", "amount": "1.500.000", "external_id": "mov-001"}),
    ]
    movements = build_movement_previews(rows)
    existing = [
        {
            "id": "txn_old",
            "date": None,
            "amount": 0,
            "description": None,
            "type": "income",
            "external_id": "mov-001",
            "external_source": "estado.csv",
        },
    ]
    attach_duplicates(movements, existing, account_id="fac_a", source="estado.csv")
    assert movements[0].duplicate is True
    assert movements[0].duplicate_type == "identity"
    assert movements[0].duplicate_of == "txn_old"


def test_attach_duplicates_skips_identity_from_other_source() -> None:
    rows = [_stored_row(2, {"date": "01/09/2026", "amount": "1.500.000", "external_id": "mov-001"})]
    movements = build_movement_previews(rows)
    existing = [
        {
            "id": "txn_old",
            "date": None,
            "amount": 0,
            "description": None,
            "type": "income",
            "external_id": "mov-001",
            "external_source": "otro.csv",
        },
    ]
    attach_duplicates(movements, existing, account_id="fac_a", source="estado.csv")
    assert movements[0].duplicate is False


def test_attach_duplicates_within_batch_identity() -> None:
    rows = [
        _stored_row(2, {"date": "01/09/2026", "amount": "1.500.000", "external_id": "mov-001"}),
        _stored_row(3, {"date": "01/09/2026", "amount": "1.500.000", "external_id": "mov-001"}),
    ]
    movements = build_movement_previews(rows)
    attach_duplicates(movements, [], account_id="fac_a", source="estado.csv")
    assert movements[0].duplicate is False
    assert movements[1].duplicate is True
    assert movements[1].duplicate_type == "identity"
    assert movements[1].duplicate_of is None


def test_placeholder_all_zero_external_id_is_ignored() -> None:
    rows = [
        _stored_row(2, {"date": "01/09/2026", "amount": "-45.890", "external_id": "000000000"}),
        _stored_row(3, {"date": "02/09/2026", "amount": "-12.300", "external_id": "000000000"}),
    ]
    movements = build_movement_previews(rows)
    attach_duplicates(movements, [], account_id="fac_a", source="estado.csv")
    assert [m.external_id for m in movements] == [None, None]
    assert all(m.duplicate is False for m in movements)


def test_attach_duplicates_does_not_match_existing_placeholder_id() -> None:
    rows = [_stored_row(2, {"date": "01/09/2026", "amount": "-45.890", "external_id": "000000000"})]
    movements = build_movement_previews(rows)
    existing = [
        {
            "id": "txn_old",
            "date": None,
            "amount": 0,
            "description": None,
            "type": "income",
            "external_id": "000000000",
            "external_source": "estado.csv",
        },
    ]
    attach_duplicates(movements, existing, account_id="fac_a", source="estado.csv")
    assert movements[0].duplicate is False


def test_attach_duplicates_by_heuristic_signed_amount() -> None:
    rows = [
        _stored_row(2, {"date": "02/09/2026", "amount": "-45.890", "description": "Mercado"}),
    ]
    movements = build_movement_previews(rows)
    existing = [
        {
            "id": "txn_manual",
            "date": __import__("datetime").date(2026, 9, 2),
            "amount": 45890,
            "description": "Mercado",
            "type": "expense",
            "external_id": None,
            "external_source": None,
        },
    ]
    attach_duplicates(movements, existing, account_id="fac_a", source="estado.csv")
    assert movements[0].duplicate is True
    assert movements[0].duplicate_type == "heuristic"
    assert movements[0].duplicate_of == "txn_manual"


def test_attach_duplicates_heuristic_does_not_match_opposite_sign() -> None:
    rows = [
        _stored_row(2, {"date": "02/09/2026", "amount": "45.890", "description": "Mercado"}),
    ]
    movements = build_movement_previews(rows)
    existing = [
        {
            "id": "txn_manual",
            "date": __import__("datetime").date(2026, 9, 2),
            "amount": 45890,
            "description": "Mercado",
            "type": "expense",
            "external_id": None,
            "external_source": None,
        },
    ]
    attach_duplicates(movements, existing, account_id="fac_a", source="estado.csv")
    assert movements[0].duplicate is False


def test_suggest_category_first_rule_wins() -> None:
    rules = [
        {"column": "description", "pattern": "super", "category_id": "cat_market", "enabled": True},
        {
            "column": "description",
            "pattern": "mercado",
            "category_id": "cat_mercado",
            "enabled": True,
        },
    ]
    values = {"description": "SUPERMERCADO LIDER"}
    assert suggest_category(rules, values) == "cat_market"


def test_suggest_category_case_insensitive_and_empty_pattern() -> None:
    rules = [
        {
            "column": "description",
            "pattern": "sueldo",
            "category_id": "cat_salary",
            "enabled": True,
        },
        {"column": "description", "pattern": "", "category_id": "cat_empty", "enabled": True},
    ]
    assert suggest_category(rules, {"description": "Sueldo de septiembre"}) == "cat_salary"
    assert suggest_category(rules, {"description": "OTRA COSA"}) is None


def test_suggest_category_disabled_rules_are_skipped() -> None:
    rules = [
        {
            "column": "description",
            "pattern": "sueldo",
            "category_id": "cat_salary",
            "enabled": False,
        },
        {"column": "description", "pattern": "sueldo", "category_id": "cat_other", "enabled": True},
    ]
    assert suggest_category(rules, {"description": "sueldo"}) == "cat_other"


def test_parse_batch_drops_rows_outside_data_block() -> None:
    """Filas fuera del bloque de transacciones (resumen, pie) se descartan."""
    from cuentafaro.importing.extract import ExtractedTable

    headers = ["Fecha", "N° de operación", "Movimientos", "Cargos", "Abonos", "Saldo"]
    rows = [
        # 3 transacciones válidas
        {"Fecha": "03/08", "N° de operación": "585771651", "Movimientos": "Transferencia",
         "Cargos": "0", "Abonos": "1900000", "Saldo": "1948640"},
        {"Fecha": "05/08", "N° de operación": "585772300", "Movimientos": "Pago supermercado",
         "Cargos": "19000", "Abonos": "0", "Saldo": "1929640"},
        {"Fecha": "10/08", "N° de operación": "585773100", "Movimientos": "Abono",
         "Cargos": "0", "Abonos": "500000", "Saldo": "2429640"},
        # Bloque footer / resumen — debe descartarse
        {"Fecha": "Resumen de Movimientos", "N° de operación": "Cheques",
         "Movimientos": "Giros cajeros automáticos", "Cargos": "Pagos productos mismo banco",
         "Abonos": "Pago automático de cuentas", "Saldo": ""},
        {"Fecha": "0", "N° de operación": "0", "Movimientos": "2700000",
         "Cargos": "0", "Abonos": "", "Saldo": ""},
        {"Fecha": "Impuestos", "N° de operación": "Otros cargos", "Movimientos": "Depósitos",
         "Cargos": "Otros abonos", "Abonos": "", "Saldo": ""},
        {"Fecha": "2856", "N° de operación": "2916792", "Movimientos": "0",
         "Cargos": "5597979", "Abonos": "", "Saldo": ""},
        {"Fecha": "Resumen de Saldos", "N° de operación": "Saldo final",
         "Movimientos": "Saldo disponible", "Cargos": "", "Abonos": "", "Saldo": ""},
        {"Fecha": "26971", "N° de operación": "26971", "Movimientos": "429324",
         "Cargos": "0", "Abonos": "0", "Saldo": ""},
        {"Fecha": "", "N° de operación": "(600) 686 0888 Itaú Phone y Emergencias Bancarias",
         "Movimientos": "", "Cargos": "", "Abonos": "", "Saldo": ""},
        {"Fecha": "", "N° de operación": "Infórmese sobre la garantía de los depósitos "
         "en su banco o en www.cmfchile.cl", "Movimientos": "", "Cargos": "", "Abonos": "",
         "Saldo": ""},
    ]

    table = ExtractedTable(
        headers=headers,
        rows=rows,
        first_row_number=26,
        default_year=2026,
        separator=None,
    )
    mapping = normalize_mapping({}, headers)
    batch = parse_batch(table, mapping)

    assert batch.total_rows == 3
    assert batch.valid_rows == 3
    assert batch.invalid_rows == 0
    assert [row.row_number for row in batch.rows] == [26, 27, 28]


def _card_table(
    *,
    summary: list[dict[str, str]] | None = None,
    data: list[dict[str, str]] | None = None,
) -> ExtractedTable:
    return ExtractedTable(
        headers=["columna_1", "columna_2", "columna_3", "columna_4", "columna_5"],
        rows=data or [
            {
                "columna_1": "01/08/2026",
                "columna_2": "Supermercado La Polar",
                "columna_3": "150000",
                "columna_4": "",
                "columna_5": "2350000",
            },
        ],
        first_row_number=1,
        default_year=2026,
        preamble=summary or [
            {"columna_1": "Período", "columna_2": "01-Ago-2026 - 31-Ago-2026"},
            {"columna_1": "Fecha de vencimiento", "columna_2": "28/09/2026"},
            {"columna_1": "Total a Pagar", "columna_2": "1.234.567"},
            {"columna_1": "Pago Mínimo", "columna_2": "150.000"},
            {"columna_1": "Saldo Deudor del Estado de Cuenta", "columna_2": "2.345.678"},
            {"columna_1": "Cupo Total", "columna_2": "3.000.000"},
            {"columna_1": "Cupo Disponible", "columna_2": "654.322"},
        ],
    )


def test_detect_card_statement_from_excel_style_key_value_pairs() -> None:
    detected = detect_card_statement(_card_table())
    assert detected["statement_period"] == "01-Ago-2026 - 31-Ago-2026"
    assert detected["due_date"] == date(2026, 9, 28).isoformat()
    assert detected["total_to_pay"] == 1_234_567
    assert detected["minimum_payment"] == 150_000
    assert detected["total_debt"] == 2_345_678
    assert detected["credit_limit"] == 3_000_000
    assert detected["available_credit"] == 654_322


def test_detect_card_statement_ignores_label_only_cells_and_data_rows() -> None:
    table = _card_table(
        summary=[
            {"columna_1": "Total a Pagar", "columna_2": "1.234.567"},
            {"columna_1": "Vencimiento", "columna_2": "28/09/2026"},
        ],
        data=[
            {
                "columna_1": "05/08/2026",
                "columna_2": "Compra con cuotas",
                "columna_3": "90.000",
                "columna_4": "3 de 12",
                "columna_5": "2.345.678",
            }
        ],
    )
    detected = detect_card_statement(table)
    assert detected["total_to_pay"] == 1_234_567
    assert detected["due_date"] == date(2026, 9, 28).isoformat()
    # Las filas de datos (más de 4 celdas) no se confunden con el resumen.
    assert "minimum_payment" not in detected
    assert "credit_limit" not in detected


def test_detect_card_statement_from_pdf_style_rows_and_inline_values() -> None:
    table = ExtractedTable(
        headers=["columna_1", "columna_2", "columna_3"],
        rows=[
            {"columna_1": "TOTAL A PAGAR", "columna_2": "$", "columna_3": "1.234.567"},
            {"columna_1": "PAGO MINIMO", "columna_2": "$", "columna_3": "150.000"},
            {"columna_1": "FECHA DE VENCIMIENTO", "columna_2": "28/09/2026"},
            {"columna_1": "Cupo total", "columna_2": "3.000.000"},
            {"columna_1": "Total a Pagar: 345.678", "columna_2": ""},
        ],
        first_row_number=1,
        default_year=2026,
    )
    detected = detect_card_statement(table)
    assert detected["total_to_pay"] == 1_234_567
    assert detected["minimum_payment"] == 150_000
    assert detected["due_date"] == date(2026, 9, 28).isoformat()
    assert detected["credit_limit"] == 3_000_000
