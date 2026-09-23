"""Integridad referencial y restricciones de entidades base (CF1-02)."""

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from cuentafaro.db import create_engine_and_session
from cuentafaro.models import (
    FinancialAccount,
    FinancialInstitution,
    Household,
    HouseholdMember,
)


@pytest.fixture()
def session(tmp_path):
    engine, session_factory = create_engine_and_session(f"sqlite:///{tmp_path / 'test.db'}")
    from cuentafaro.models import Base

    Base.metadata.create_all(engine)
    db_session = session_factory()
    try:
        yield db_session
    finally:
        db_session.close()
        engine.dispose()


def test_create_household(session) -> None:
    household = Household(
        id="hh_test", name="Hogar prueba", status="active", timezone="America/Santiago"
    )
    session.add(household)
    session.commit()

    found = session.get(Household, "hh_test")
    assert found.name == "Hogar prueba"
    assert found.status == "active"
    assert found.created_at is not None
    assert found.updated_at is not None


def test_household_status_restricted(session) -> None:
    bad = Household(id="hh_bad", name="Hogar malo", status="exploded", timezone="America/Santiago")
    session.add(bad)
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_create_and_read_member(session) -> None:
    session.add(Household(id="hh_m1", name="H", timezone="America/Santiago"))
    session.commit()
    session.add(
        HouseholdMember(
            id="mem_m1", household_id="hh_m1", name="Ana", role="admin", status="active"
        )
    )
    session.commit()

    member = session.get(HouseholdMember, "mem_m1")
    assert member.household_id == "hh_m1"
    assert member.role == "admin"


def test_member_requires_existing_household(session) -> None:
    session.add(HouseholdMember(id="mem_orphan", household_id="hh_inexistente", name="X"))
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_cannot_delete_household_with_members(session) -> None:
    session.add(Household(id="hh_del", name="H", timezone="America/Santiago"))
    session.add(HouseholdMember(id="mem_del", household_id="hh_del", name="B"))
    session.commit()

    session.delete(session.get(Household, "hh_del"))
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_create_institution_unique_name(session) -> None:
    session.add(FinancialInstitution(id="fin_b1", name="Banco Uno", type="bank"))
    session.commit()
    session.add(FinancialInstitution(id="fin_b2", name="Banco Uno", type="bank"))
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_create_account_with_household_and_institution(session) -> None:
    session.add(Household(id="hh_a", name="H", timezone="America/Santiago"))
    session.add(FinancialInstitution(id="fin_a", name="Banco A", type="bank"))
    session.commit()
    session.add(
        FinancialAccount(
            id="fac_a",
            household_id="hh_a",
            institution_id="fin_a",
            name="Cuenta corriente",
            type="checking",
            currency="CLP",
            balance_reported=1000,
            balance_calculated=1000,
            status="active",
        )
    )
    session.commit()

    account = session.get(FinancialAccount, "fac_a")
    assert account.type == "checking"
    assert account.currency == "CLP"
    assert isinstance(account.balance_reported, int)


def test_account_type_restricted(session) -> None:
    session.add(Household(id="hh_t", name="H", timezone="America/Santiago"))
    session.commit()
    bad = FinancialAccount(
        id="fac_bad", household_id="hh_t", name="Cuenta", type="mystery", currency="CLP"
    )
    session.add(bad)
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_account_money_never_float(session) -> None:
    session.add(Household(id="hh_f", name="H", timezone="America/Santiago"))
    session.commit()
    account = FinancialAccount(
        id="fac_f",
        household_id="hh_f",
        name="Efectivo",
        type="cash",
        currency="CLP",
        balance_reported=123456,
        balance_calculated=123456,
    )
    session.add(account)
    session.commit()
    stored = session.scalar(
        select(FinancialAccount.balance_reported).where(FinancialAccount.id == "fac_f")
    )
    assert isinstance(stored, int)
    assert stored == 123456


def test_list_all_entities(session) -> None:
    session.add(Household(id="hh_l", name="H", timezone="America/Santiago"))
    session.add(FinancialInstitution(id="fin_l", name="Banco L", type="bank"))
    session.commit()
    session.add(HouseholdMember(id="mem_l", household_id="hh_l", name="M"))
    session.add(FinancialAccount(id="fac_l", household_id="hh_l", name="C", type="cash"))
    session.commit()

    assert len(list(session.scalars(select(Household)))) == 1
    assert len(list(session.scalars(select(HouseholdMember)))) == 1
    assert len(list(session.scalars(select(FinancialInstitution)))) == 1
    assert len(list(session.scalars(select(FinancialAccount)))) == 1
