"""Carga y validación del seed ficticio (CF1-01)."""

from cuentafaro.seed import load_seed_document, seed_summary, validate_seed_document


def test_seed_loads_and_validates() -> None:
    document = load_seed_document()
    validate_seed_document(document)
    summary = seed_summary(document)
    assert summary["counts"]["households"] == 1
    assert summary["counts"]["accounts"] >= 3
    assert summary["counts"]["debts"] >= 2


def test_cli_seed_demo_persists_on_temporary_db(tmp_path, monkeypatch) -> None:
    from cuentafaro.cli import main
    from cuentafaro.db import create_engine_and_session
    from cuentafaro.models import Base, Household

    engine, session_factory = create_engine_and_session(f"sqlite:///{tmp_path / 'cli-seed.db'}")
    Base.metadata.create_all(engine)
    monkeypatch.setattr("cuentafaro.db.get_session_factory", lambda: session_factory)

    assert main(["seed-demo"]) == 0
    with session_factory() as session:
        assert session.get(Household, "hh_demo_faro") is not None
    assert main(["seed-demo"]) == 0
    engine.dispose()


def test_cli_version_reports_successful() -> None:
    from cuentafaro.cli import main

    assert main(["version"]) == 0
