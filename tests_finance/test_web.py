"""Interfaz web (franja CF1-22 a CF1-29): la app sirve el HTML y los estáticos."""

from fastapi.testclient import TestClient

from cuentafaro.api import create_app


def test_index_serves_shell() -> None:
    client = TestClient(create_app())
    response = client.get("/")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    body = response.text
    assert "CuentaFaro" in body
    assert "cdn.tailwindcss.com" in body
    assert "/static/app.js" in body


def test_app_js_is_served() -> None:
    client = TestClient(create_app())
    response = client.get("/static/app.js")
    assert response.status_code == 200
    assert "javascript" in response.headers["content-type"]
    body = response.text
    assert "renderDashboard" in body
    assert "renderAccounts" in body
    assert "renderTransactions" in body
    assert "renderDebts" in body
    assert "renderBudget" in body
    assert "renderPayments" in body
    assert "renderProjections" in body


def test_app_js_includes_import_views() -> None:
    client = TestClient(create_app())
    body = client.get("/static/app.js").text
    for fn in (
        "renderImports",
        "renderImportList",
        "renderBatchPreview",
        "renderReviewQueue",
        "onImportSubmit",
        "confirmBatch",
        "resolveReview",
        "onReviewCorrectSubmit",
    ):
        assert f"function {fn}(" in body


def test_app_js_includes_ai_assistant() -> None:
    client = TestClient(create_app())
    body = client.get("/static/app.js").text
    assert 'hash: "#/ai"' in body
    for fn in (
        "renderAi",
        "aiAnalyze",
        "aiReloadProposals",
        "aiResolve",
        "aiSuggest",
        "suggestTxnCategory",
    ):
        assert f"function {fn}(" in body


def test_app_js_includes_egresos_captures_and_notifications() -> None:
    client = TestClient(create_app())
    body = client.get("/static/app.js").text
    for hash_ in ('hash: "#/egresos"', 'hash: "#/notifications"'):
        assert hash_ in body
    for fn in (
        "renderEgresos",
        "renderCaptures",
        "processCapture",
        "openCaptureConfirm",
        "confirmCapture",
        "openCaptureEdit",
        "onCaptureEdit",
        "discardCapture",
        "renderNotifications",
        "runNotifications",
        "toggleNotification",
    ):
        assert f"function {fn}(" in body


def test_app_js_includes_income_period_registration() -> None:
    client = TestClient(create_app())
    body = client.get("/static/app.js").text
    for needle in (
        "Registrar ingreso por mes",
        "openRecordIncome(",
        "incomePeriodDate()",
        "income-month",
        "income-year",
        "Registrado · ${esc(monthLabel)}",
        'modal("income-record-modal", "Registrar ingreso del mes"',
    ):
        assert needle in body
    assert "Descripción" in body
    assert 'field("Descripción", "description", "text", "", { placeholder:' in body


def test_app_js_includes_reports_tabs_and_periods() -> None:
    client = TestClient(create_app())
    body = client.get("/static/app.js").text
    for needle in (
        '["3m", "3 meses"]',
        '["6m", "6 meses"]',
        '["12m", "12 meses"]',
        '["year", "Año"]',
        '["custom", "Personalizado"]',
        'data-range="${val}"',
        'data-tab="${val}"',
        'data-tab="gastos"',
        "function reportMonths()",
        "function reportDebtData(",
        "function reportMonthlyTotals(",
        "Deuda cero estimada",
        "Composición de activos",
        "Último mes vs anterior por categoría",
        "Evolución de la deuda",
    ):
        assert needle in body


def test_app_js_includes_simulator_comparison() -> None:
    client = TestClient(create_app())
    body = client.get("/static/app.js").text
    for needle in (
        "function lineChart(",
        "Bola de nieve vs Avalancha",
        "Meses a deuda cero",
        "run(\"snowball\")",
        "run(\"avalanche\")",
        "months_series",
        "sample(snow.months_series)",
        "sample(ava.months_series)",
    ):
        assert needle in body


def test_app_js_includes_card_tabs_and_statement() -> None:
    client = TestClient(create_app())
    body = client.get("/static/app.js").text
    for needle in (
        '"estado-cuenta"',
        '"cuotas"',
        '"pagos"',
        "function cardDetailData(",
        "function cardStatementWindow(",
        "function cardAlertLevel(",
        "function cardUsage(",
        "function estadoCuentaBody(",
        "function cuotasBody(",
        "function pagosBody(",
        "function openAccEdit(",
        "function onAccEdit(",
        'Día de cierre — corte',
        'Día de vencimiento — pago',
        "Editar tarjeta",
        "Saludable",
        "Crítico",
    ):
        assert needle in body


def test_app_js_includes_card_statement_import_ui() -> None:
    client = TestClient(create_app())
    body = client.get("/static/app.js").text
    for needle in (
        "function cardStatementMetaBlock(",
        "import-card-hint",
        "toggleCardHint",
        "Estado de cuenta de tarjeta detectado",
        "Se aplica al confirmar",
        "sincroniza la deuda vinculada",
        "Total a pagar",
        "Pago mínimo",
        "Deuda total",
    ):
        assert needle in body


def test_app_js_includes_budget_modal_config_quick_actions_and_stepper() -> None:
    client = TestClient(create_app())
    body = client.get("/static/app.js").text
    for needle in (
        'modal("budget-alloc-modal", "Asignar monto por categoría"',
        'closeModal("budget-alloc-modal")',
        "function openBudgetAlloc(",
        "function importStepper(",
        '["1", "Subir"]',
        "id=\"import-dropzone\"",
        "Arrastra aquí tu estado de cuenta o haz clic para elegir",
        "dropzone.classList.add(\"dropzone\")",
        "Aplicar ajuste",
        "AI_KIND_LABEL",
        "AI_STATUS_LABEL",
        "En revisión",
        "Ver Reportes",
        "Asignar presupuesto",
        "Preferencias de avisos",
        'hash: "#/notifications"',
    ):
        assert needle in body


def test_index_serves_manifest_and_sw() -> None:
    client = TestClient(create_app())
    manifest = client.get("/static/manifest.webmanifest")
    assert manifest.status_code == 200
    assert '"short_name": "CuentaFaro"' in manifest.text
    sw = client.get("/static/sw.js")
    assert sw.status_code == 200
    assert "serviceWorker" in client.get("/").text
    assert "/static/sw.js" in client.get("/").text


def test_index_serves_on_fragment_paths() -> None:
    client = TestClient(create_app())
    response = client.get("/#/dashboard")
    assert response.status_code == 200
    assert "CuentaFaro" in response.text


def test_api_still_available_under_same_app(tmp_path) -> None:
    from fastapi.testclient import TestClient

    from cuentafaro.db import create_engine_and_session
    from cuentafaro.deps import get_session
    from cuentafaro.models import Base

    engine, session_factory = create_engine_and_session(f"sqlite:///{tmp_path / 'web.db'}")
    Base.metadata.create_all(engine)
    app = create_app()

    def override_session():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_session] = override_session
    client = TestClient(app)
    response = client.get("/api/v1/households")
    assert response.status_code == 200
    assert response.json() == []
    app.dependency_overrides.clear()
    engine.dispose()
