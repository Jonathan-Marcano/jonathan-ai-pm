"""Persistencia del seed demo (CLI seed-demo)."""

import pytest

from cuentafaro.db import create_engine_and_session
from cuentafaro.models import Base, Budget, Household, Transaction
from cuentafaro.seed import load_seed_document, persist_demo_seed


@pytest.fixture()
def session(tmp_path):
    engine, session_factory = create_engine_and_session(f"sqlite:///{tmp_path / 'seed.db'}")
    Base.metadata.create_all(engine)
    with session_factory() as session:
        yield session
    engine.dispose()


def test_persists_demo_dataset(session) -> None:
    document = load_seed_document()
    result = persist_demo_seed(session, document)
    assert result["counts"]["households"] == 1
    assert session.get(Household, "hh_demo_faro") is not None
    assert session.query(Transaction).count() == len(document["transactions"])
    assert session.query(Budget).count() == len(document["budgets"])


def test_rejects_duplicate_demo_household(session) -> None:
    persist_demo_seed(session, load_seed_document())
    with pytest.raises(ValueError, match="ya existe"):
        persist_demo_seed(session, load_seed_document())


def test_demo_balances_and_relationships_are_coherent(session) -> None:
    persist_demo_seed(session, load_seed_document())
    transaction = session.query(Transaction).filter_by(id="txn_demo_transferencia").one()
    assert transaction.to_account_id == "fac_demo_ahorro"
    assert transaction.recorded_by == "mem_demo_jonathan"
    debt = session.query(Household).first()
    assert debt is not None

    from cuentafaro.models import Category, Debt, IncomeSource

    assert session.query(Category).filter_by(kind="transfer").count() == 1
    assert session.query(Debt).filter_by(type="loan").count() == 1
    assert session.query(IncomeSource).count() == 3
