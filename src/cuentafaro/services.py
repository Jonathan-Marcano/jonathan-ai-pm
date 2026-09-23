from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

if TYPE_CHECKING:
    from cuentafaro.ai import MonthFacts

from cuentafaro.importing import (
    FIELD_BY_KEY,
    ImportFormatError,
    MovementPreview,
    attach_duplicates,
    build_movement_previews,
    detect_card_statement,
    extract_table,
    normalize_mapping,
    parse_batch,
    reconcile_balances,
    suggest_category,
)
from cuentafaro.importing.contract import validate_values
from cuentafaro.models import (
    NOTIFICATION_KINDS,
    AiProposal,
    AuditEvent,
    Budget,
    BudgetCategory,
    Capture,
    Category,
    Debt,
    DebtPayment,
    FinancialAccount,
    FinancialGoal,
    FinancialInstitution,
    Household,
    HouseholdMember,
    ImportBatch,
    ImportCategoryRule,
    ImportReview,
    IncomeSource,
    Installment,
    Notification,
    NotificationPreference,
    NotificationSend,
    PaymentPlan,
    ProjectionScenario,
    Transaction,
    utc_now,
)

DEFAULT_CATEGORIES = {
    "expense": [
        "Alimentación",
        "Transporte",
        "Vivienda",
        "Servicios básicos",
        "Salud",
        "Educación",
        "Ocio",
        "Ropa",
        "Otros gastos",
    ],
    "income": ["Ingreso del trabajo", "Ingreso adicional", "Otros ingresos"],
    "transfer": ["Transferencia interna"],
}


class DomainRuleError(ValueError):
    pass


class DomainStore:
    """Transacción atómica para las reglas del dominio financiero."""

    def __init__(self, session: Session):
        self.session = session

    @staticmethod
    def _new_id(prefix: str) -> str:
        return f"{prefix}_{uuid4().hex}"

    # ---- Household ----

    def create_household(self, *, name: str, timezone: str, status: str = "active") -> Household:
        name = name.strip()
        if not name:
            raise DomainRuleError("El hogar requiere un nombre")
        active_exists = self.session.scalar(
            select(Household.id).where(Household.status == "active").limit(1)
        )
        if status == "active" and active_exists:
            self.session.execute(
                update(Household).where(Household.status == "active").values(status="paused")
            )
        household = Household(
            id=self._new_id("hh"),
            name=name,
            timezone=timezone,
            status=status,
        )
        self.session.add(household)
        self.session.flush()
        for kind, names in DEFAULT_CATEGORIES.items():
            for category_name in names:
                self.session.add(
                    Category(
                        id=self._new_id("cat"),
                        household_id=household.id,
                        name=category_name,
                        kind=kind,
                        status="active",
                    )
                )
        self.session.commit()
        self.session.refresh(household)
        return household

    def get_household(self, household_id: str) -> Household:
        return self._required("household", household_id)

    def list_households(self) -> list[Household]:
        return list(self.session.scalars(select(Household).order_by(Household.id)))

    def update_household(
        self, household_id: str, *, name: str | None, timezone: str | None, status: str | None
    ) -> Household:
        household = self._required("household", household_id)
        if name is not None:
            normalized = name.strip()
            if not normalized:
                raise DomainRuleError("El nombre del hogar no puede quedar vacío")
            household.name = normalized
        if timezone is not None:
            household.timezone = timezone
        if status is not None:
            if status == "active":
                self.session.execute(
                    update(Household)
                    .where(Household.status == "active", Household.id != household_id)
                    .values(status="paused")
                )
            household.status = status
        self.session.commit()
        self.session.refresh(household)
        return household

    def delete_household(self, household_id: str) -> None:
        """Elimina el hogar y toda su cascada de datos en orden seguro (hijos antes que padres)."""
        self._required("household", household_id)
        account_ids = select(FinancialAccount.id).where(
            FinancialAccount.household_id == household_id
        )
        plan_ids = select(PaymentPlan.id).where(PaymentPlan.household_id == household_id)
        budget_ids = select(Budget.id).where(Budget.household_id == household_id)
        debt_ids = select(Debt.id).where(Debt.household_id == household_id)

        self.session.execute(delete(Capture).where(Capture.household_id == household_id))
        self.session.execute(delete(AiProposal).where(AiProposal.household_id == household_id))
        self.session.execute(delete(Notification).where(Notification.household_id == household_id))
        self.session.execute(
            delete(NotificationPreference).where(
                NotificationPreference.household_id == household_id
            )
        )
        self.session.execute(
            delete(ImportCategoryRule).where(ImportCategoryRule.household_id == household_id)
        )
        self.session.execute(
            delete(ProjectionScenario).where(ProjectionScenario.plan_id.in_(plan_ids))
        )
        self.session.execute(delete(PaymentPlan).where(PaymentPlan.household_id == household_id))
        self.session.execute(delete(BudgetCategory).where(BudgetCategory.budget_id.in_(budget_ids)))
        self.session.execute(delete(Budget).where(Budget.household_id == household_id))
        self.session.execute(delete(Installment).where(Installment.debt_id.in_(debt_ids)))
        self.session.execute(delete(DebtPayment).where(DebtPayment.debt_id.in_(debt_ids)))
        self.session.execute(delete(ImportReview).where(ImportReview.household_id == household_id))
        self.session.execute(delete(ImportBatch).where(ImportBatch.household_id == household_id))
        self.session.execute(delete(Transaction).where(Transaction.account_id.in_(account_ids)))
        self.session.execute(delete(Debt).where(Debt.household_id == household_id))
        self.session.execute(delete(IncomeSource).where(IncomeSource.household_id == household_id))
        self.session.execute(delete(Category).where(Category.household_id == household_id))
        self.session.execute(
            delete(HouseholdMember).where(HouseholdMember.household_id == household_id)
        )
        self.session.execute(
            delete(FinancialAccount).where(FinancialAccount.household_id == household_id)
        )
        self.session.execute(delete(Household).where(Household.id == household_id))
        self.session.commit()

    # ---- Members ----

    def create_member(
        self, household_id: str, *, name: str, role: str = "member", status: str = "active"
    ) -> HouseholdMember:
        self._required("household", household_id)
        name = name.strip()
        if not name:
            raise DomainRuleError("El integrante requiere un nombre")
        member = HouseholdMember(
            id=self._new_id("mem"),
            household_id=household_id,
            name=name,
            role=role,
            status=status,
        )
        self.session.add(member)
        self.session.commit()
        self.session.refresh(member)
        return member

    def list_members(self, household_id: str | None = None) -> list[HouseholdMember]:
        statement = select(HouseholdMember).order_by(HouseholdMember.id)
        if household_id:
            statement = statement.where(HouseholdMember.household_id == household_id)
        return list(self.session.scalars(statement))

    def get_member(self, member_id: str) -> HouseholdMember:
        return self._required("member", member_id)

    def update_member(
        self, member_id: str, *, name: str | None, role: str | None, status: str | None
    ) -> HouseholdMember:
        member = self._required("member", member_id)
        if name is not None:
            normalized = name.strip()
            if not normalized:
                raise DomainRuleError("El nombre del integrante no puede quedar vacío")
            member.name = normalized
        if role is not None:
            member.role = role
        if status is not None:
            member.status = status
        self.session.commit()
        self.session.refresh(member)
        return member

    def delete_member(self, member_id: str) -> None:
        member = self._required("member", member_id)
        self.session.delete(member)
        self.session.commit()

    # ---- Institutions ----

    def create_institution(
        self, *, name: str, type: str = "other", status: str = "active"
    ) -> FinancialInstitution:
        name = name.strip()
        if not name:
            raise DomainRuleError("La institución requiere un nombre")
        institution = FinancialInstitution(
            id=self._new_id("fin"), name=name, type=type, status=status
        )
        self.session.add(institution)
        self.session.commit()
        self.session.refresh(institution)
        return institution

    def list_institutions(self) -> list[FinancialInstitution]:
        return list(
            self.session.scalars(select(FinancialInstitution).order_by(FinancialInstitution.id))
        )

    def get_institution(self, institution_id: str) -> FinancialInstitution:
        return self._required("institution", institution_id)

    def institution_name(self, institution_id: str | None) -> str | None:
        if not institution_id:
            return None
        institution = self.session.get(FinancialInstitution, institution_id)
        return institution.name if institution else None

    def update_institution(
        self, institution_id: str, *, name: str | None, type: str | None, status: str | None
    ) -> FinancialInstitution:
        institution = self._required("institution", institution_id)
        if name is not None:
            normalized = name.strip()
            if not normalized:
                raise DomainRuleError("El nombre de la institución no puede quedar vacío")
            institution.name = normalized
        if type is not None:
            institution.type = type
        if status is not None:
            institution.status = status
        self.session.commit()
        self.session.refresh(institution)
        return institution

    def delete_institution(self, institution_id: str) -> None:
        """Elimina una institución y desliga sus cuentas (campo opcional)."""
        institution = self._required("institution", institution_id)
        self.session.execute(
            update(FinancialAccount)
            .where(FinancialAccount.institution_id == institution_id)
            .values(institution_id=None)
        )
        self.session.delete(institution)
        self.session.commit()

    # ---- Accounts ----

    def create_account(
        self,
        *,
        household_id: str,
        institution_id: str | None,
        name: str,
        type: str,
        currency: str,
        balance_reported: int,
        balance_calculated: int,
        original_amount: int | None,
        credit_limit: int | None,
        statement_day: int | None,
        due_day: int | None,
        status: str,
    ) -> FinancialAccount:
        self._required("household", household_id)
        if institution_id:
            self._required("institution", institution_id)
        name = name.strip()
        if not name:
            raise DomainRuleError("La cuenta requiere un nombre")
        self._validate_account_days(statement_day, due_day)
        account = FinancialAccount(
            id=self._new_id("fac"),
            household_id=household_id,
            institution_id=institution_id,
            name=name,
            type=type,
            currency=currency,
            balance_reported=balance_reported,
            balance_calculated=balance_calculated,
            original_amount=original_amount,
            credit_limit=credit_limit,
            statement_day=statement_day,
            due_day=due_day,
            status=status,
        )
        self.session.add(account)
        self.session.commit()
        self.session.refresh(account)
        return account

    def list_accounts(self, household_id: str | None = None) -> list[FinancialAccount]:
        statement = select(FinancialAccount).order_by(FinancialAccount.id)
        if household_id:
            statement = statement.where(FinancialAccount.household_id == household_id)
        return list(self.session.scalars(statement))

    def get_account(self, account_id: str) -> FinancialAccount:
        return self._required("account", account_id)

    def update_account(
        self,
        account_id: str,
        *,
        institution_id: str | None,
        name: str | None,
        type: str | None,
        balance_reported: int | None,
        credit_limit: int | None,
        status: str | None,
        statement_day: int | None = None,
        due_day: int | None = None,
    ) -> FinancialAccount:
        account = self._required("account", account_id)
        if institution_id is not None:
            self._required("institution", institution_id)
            account.institution_id = institution_id
        if name is not None:
            normalized = name.strip()
            if not normalized:
                raise DomainRuleError("El nombre de la cuenta no puede quedar vacío")
            account.name = normalized
        if type is not None:
            account.type = type
        if balance_reported is not None:
            account.balance_reported = balance_reported
        if credit_limit is not None:
            account.credit_limit = credit_limit
        if statement_day is not None:
            if statement_day < 1 or statement_day > 31:
                raise DomainRuleError("El día de cierre debe estar entre 1 y 31")
            account.statement_day = statement_day
        if due_day is not None:
            if due_day < 1 or due_day > 31:
                raise DomainRuleError("El día de vencimiento debe estar entre 1 y 31")
            account.due_day = due_day
        if status is not None:
            account.status = status
        self.session.commit()
        self.session.refresh(account)
        return account

    @staticmethod
    def _validate_account_days(statement_day: int | None, due_day: int | None) -> None:
        for label, value in (("día de cierre", statement_day), ("día de vencimiento", due_day)):
            if value is not None and (value < 1 or value > 31):
                raise DomainRuleError(f"El {label} debe estar entre 1 y 31")

    # ---- Categories ----

    def create_category(
        self, household_id: str, *, name: str, kind: str = "expense", status: str = "active"
    ) -> Category:
        self._required("household", household_id)
        name = name.strip()
        if not name:
            raise DomainRuleError("La categoría requiere un nombre")
        category = Category(
            id=self._new_id("cat"),
            household_id=household_id,
            name=name,
            kind=kind,
            status=status,
        )
        self.session.add(category)
        self.session.commit()
        self.session.refresh(category)
        return category

    def list_categories(self, household_id: str) -> list[Category]:
        self._required("household", household_id)
        statement = (
            select(Category)
            .where(Category.household_id == household_id)
            .order_by(Category.kind, Category.name)
        )
        return list(self.session.scalars(statement))

    def get_category(self, category_id: str) -> Category:
        return self._required("category", category_id)

    def update_category(
        self, category_id: str, *, name: str | None, kind: str | None, status: str | None
    ) -> Category:
        category = self._required("category", category_id)
        if name is not None:
            normalized = name.strip()
            if not normalized:
                raise DomainRuleError("El nombre de la categoría no puede quedar vacío")
            category.name = normalized
        if kind is not None:
            category.kind = kind
        if status is not None:
            category.status = status
        self.session.commit()
        self.session.refresh(category)
        return category

    # ---- Income sources ----

    def create_income_source(
        self,
        household_id: str,
        *,
        member_id: str | None,
        name: str,
        type: str,
        expected_amount: int,
        frequency: str,
        status: str = "active",
    ) -> IncomeSource:
        self._required("household", household_id)
        if member_id:
            member = self._required("member", member_id)
            if member.household_id != household_id:
                raise DomainRuleError("El integrante no pertenece al hogar")
        name = name.strip()
        if not name:
            raise DomainRuleError("La fuente de ingreso requiere un nombre")
        source = IncomeSource(
            id=self._new_id("inc"),
            household_id=household_id,
            member_id=member_id,
            name=name,
            type=type,
            expected_amount=expected_amount,
            frequency=frequency,
            status=status,
        )
        self.session.add(source)
        self.session.commit()
        self.session.refresh(source)
        return source

    def list_income_sources(self, household_id: str) -> list[IncomeSource]:
        self._required("household", household_id)
        statement = (
            select(IncomeSource)
            .where(IncomeSource.household_id == household_id)
            .order_by(IncomeSource.name)
        )
        return list(self.session.scalars(statement))

    def get_income_source(self, source_id: str) -> IncomeSource:
        return self._required("income_source", source_id)

    def update_income_source(
        self,
        source_id: str,
        *,
        member_id: str | None,
        name: str | None,
        type: str | None,
        expected_amount: int | None,
        frequency: str | None,
        status: str | None,
    ) -> IncomeSource:
        source = self._required("income_source", source_id)
        if member_id is not None:
            if member_id:
                member = self._required("member", member_id)
                if member.household_id != source.household_id:
                    raise DomainRuleError("El integrante no pertenece al hogar")
            source.member_id = member_id or None
        if name is not None:
            normalized = name.strip()
            if not normalized:
                raise DomainRuleError("El nombre de la fuente no puede quedar vacío")
            source.name = normalized
        if type is not None:
            source.type = type
        if expected_amount is not None:
            source.expected_amount = expected_amount
        if frequency is not None:
            source.frequency = frequency
        if status is not None:
            source.status = status
        self.session.commit()
        self.session.refresh(source)
        return source

    def delete_income_source(self, source_id: str) -> None:
        source = self._required("income_source", source_id)
        self.session.delete(source)
        self.session.commit()

    # ---- Financial goals (Fase UI-6) ----

    def create_goal(
        self,
        household_id: str,
        *,
        name: str,
        category: str,
        target_amount: int,
        current_amount: int,
        monthly_contribution: int,
        target_date: date | None,
        status: str = "active",
    ) -> FinancialGoal:
        self._required("household", household_id)
        name = name.strip()
        if not name:
            raise DomainRuleError("La meta requiere un nombre")
        if target_amount <= 0:
            raise DomainRuleError("El monto objetivo debe ser positivo")
        if current_amount < 0:
            raise DomainRuleError("El avance no puede ser negativo")
        if current_amount >= target_amount:
            status = "achieved"
        goal = FinancialGoal(
            id=self._new_id("goal"),
            household_id=household_id,
            name=name,
            category=category,
            target_amount=target_amount,
            current_amount=current_amount,
            monthly_contribution=monthly_contribution,
            target_date=target_date,
            status=status,
        )
        self.session.add(goal)
        self.session.commit()
        self.session.refresh(goal)
        return goal

    def list_goals(self, household_id: str) -> list[FinancialGoal]:
        self._required("household", household_id)
        statement = (
            select(FinancialGoal)
            .where(FinancialGoal.household_id == household_id)
            .order_by(FinancialGoal.status, FinancialGoal.name)
        )
        return list(self.session.scalars(statement))

    def get_goal(self, goal_id: str) -> FinancialGoal:
        return self._required("goal", goal_id)

    def update_goal(
        self,
        goal_id: str,
        *,
        name: str | None,
        category: str | None,
        target_amount: int | None,
        current_amount: int | None,
        monthly_contribution: int | None,
        target_date: date | None,
        status: str | None,
    ) -> FinancialGoal:
        goal = self._required("goal", goal_id)
        if name is not None:
            normalized = name.strip()
            if not normalized:
                raise DomainRuleError("El nombre de la meta no puede quedar vacío")
            goal.name = normalized
        if category is not None:
            goal.category = category
        if target_amount is not None:
            if target_amount <= 0:
                raise DomainRuleError("El monto objetivo debe ser positivo")
            goal.target_amount = target_amount
        if current_amount is not None:
            if current_amount < 0:
                raise DomainRuleError("El avance no puede ser negativo")
            goal.current_amount = current_amount
        if monthly_contribution is not None:
            if monthly_contribution < 0:
                raise DomainRuleError("El aporte mensual no puede ser negativo")
            goal.monthly_contribution = monthly_contribution
        if target_date is not None:
            goal.target_date = target_date
        if status is not None:
            goal.status = status
        if goal.current_amount >= goal.target_amount and goal.status != "archived":
            goal.status = "achieved"
        self.session.commit()
        self.session.refresh(goal)
        return goal

    def contribute_goal(self, goal_id: str, *, amount: int) -> FinancialGoal:
        """Registra un aporte a la meta. No mueve dinero real entre cuentas:
        es el avance declarado por el hogar hacia el objetivo."""
        goal = self._required("goal", goal_id)
        if amount <= 0:
            raise DomainRuleError("El aporte debe ser positivo")
        goal.current_amount += amount
        if goal.current_amount >= goal.target_amount:
            goal.status = "achieved"
        self.session.commit()
        self.session.refresh(goal)
        return goal

    def delete_goal(self, goal_id: str) -> None:
        goal = self._required("goal", goal_id)
        self.session.delete(goal)
        self.session.commit()

    # ---- Transactions ----

    def create_transaction(
        self,
        *,
        account_id: str,
        to_account_id: str | None,
        category_id: str | None,
        recorded_by: str | None,
        type: str,
        amount: int,
        date: date,
        description: str | None,
    ) -> Transaction:
        to_account_id = self._validate_transaction(
            account_id=account_id,
            to_account_id=to_account_id,
            category_id=category_id,
            recorded_by=recorded_by,
            type=type,
            amount=amount,
        )
        account = self._required("account", account_id)

        transaction = Transaction(
            id=self._new_id("txn"),
            account_id=account_id,
            to_account_id=to_account_id,
            category_id=category_id,
            recorded_by=recorded_by,
            type=type,
            amount=amount,
            date=date,
            description=description.strip() if description else None,
            status="posted",
        )
        self.session.add(transaction)
        self._apply_transaction(transaction, reverse=False)
        if transaction.type == "expense":
            self._track_expense_in_budget(account, category_id, amount, date, increment=True)
        self.session.commit()
        self.session.refresh(transaction)
        return transaction

    def list_transactions(
        self,
        *,
        household_id: str | None = None,
        account_id: str | None = None,
        year: int | None = None,
        month: int | None = None,
        q: str | None = None,
    ) -> list[Transaction]:
        statement = select(Transaction).order_by(Transaction.date.desc(), Transaction.id.desc())
        if q:
            statement = statement.where(Transaction.description.ilike(f"%{q.strip()}%"))
        if account_id:
            self._required("account", account_id)
            statement = statement.where(
                (Transaction.account_id == account_id) | (Transaction.to_account_id == account_id)
            )
        if household_id:
            accounts = list(
                self.session.scalars(
                    select(FinancialAccount.id).where(FinancialAccount.household_id == household_id)
                )
            )
            if not accounts:
                raise KeyError(household_id)
            statement = statement.where(
                (Transaction.account_id.in_(accounts)) | (Transaction.to_account_id.in_(accounts))
            )
        if year is not None and month is not None:
            statement = statement.where(
                func.strftime("%Y-%m", Transaction.date) == f"{year:04d}-{month:02d}"
            )
        return list(self.session.scalars(statement))

    def get_transaction(self, transaction_id: str) -> Transaction:
        return self._required("transaction", transaction_id)

    def void_transaction(self, transaction_id: str) -> Transaction:
        transaction = self._required("transaction", transaction_id)
        if transaction.status == "voided":
            raise DomainRuleError("La transacción ya está anulada")
        self._apply_transaction(transaction, reverse=True)
        if transaction.type == "expense" and transaction.category_id:
            account = self._required("account", transaction.account_id)
            self._track_expense_in_budget(
                account,
                transaction.category_id,
                transaction.amount,
                transaction.date,
                increment=False,
            )
        transaction.status = "voided"
        self.session.commit()
        self.session.refresh(transaction)
        return transaction

    def update_transaction(
        self,
        transaction_id: str,
        *,
        account_id: str | None = None,
        to_account_id: str | None = None,
        category_id: str | None = None,
        type: str | None = None,
        amount: int | None = None,
        date: date | None = None,
        description: str | None = None,
    ) -> Transaction:
        transaction = self._required("transaction", transaction_id)
        if transaction.status != "posted":
            raise DomainRuleError("Solo se pueden editar movimientos vigentes (no anulados)")

        next_account_id = account_id if account_id is not None else transaction.account_id
        next_to_account_id = (
            to_account_id if to_account_id is not None else transaction.to_account_id
        )
        next_category_id = category_id if category_id is not None else transaction.category_id
        next_recorded_by = transaction.recorded_by
        next_type = type if type is not None else transaction.type
        next_amount = amount if amount is not None else transaction.amount
        next_date = date if date is not None else transaction.date
        next_description = description if description is not None else transaction.description

        validated_to = self._validate_transaction(
            account_id=next_account_id,
            to_account_id=next_to_account_id,
            category_id=next_category_id,
            recorded_by=next_recorded_by,
            type=next_type,
            amount=next_amount,
        )

        prev_account = self._required("account", transaction.account_id)
        if transaction.type == "expense" and transaction.category_id:
            self._track_expense_in_budget(
                prev_account,
                transaction.category_id,
                transaction.amount,
                transaction.date,
                increment=False,
            )
        self._apply_transaction(transaction, reverse=True)

        transaction.account_id = next_account_id
        transaction.to_account_id = validated_to
        transaction.category_id = next_category_id
        transaction.type = next_type
        transaction.amount = next_amount
        transaction.date = next_date
        transaction.description = next_description.strip() if next_description else None

        account = self._required("account", next_account_id)
        self._apply_transaction(transaction, reverse=False)
        if next_type == "expense" and next_category_id:
            self._track_expense_in_budget(
                account, next_category_id, next_amount, next_date, increment=True
            )
        self.session.commit()
        self.session.refresh(transaction)
        return transaction

    def _validate_category_for_type(self, category: Category, type: str) -> None:
        if type in {"expense", "income"} and category.kind != type:
            raise DomainRuleError(
                f"La categoría '{category.name}' es de tipo {category.kind}, "
                f"no se puede usar para {type}"
            )
        if type == "transfer" and category.kind != "transfer":
            raise DomainRuleError("Una transferencia requiere categoría de tipo transfer")

    def _apply_transaction(self, transaction: Transaction, *, reverse: bool) -> None:
        sign = -1 if reverse else 1
        source: FinancialAccount = self._required("account", transaction.account_id)
        if transaction.type in {"expense", "payment"}:
            self._apply_balance_delta(source, transaction.amount, -1 * sign, transaction)
        elif transaction.type == "income":
            self._apply_balance_delta(source, transaction.amount, 1 * sign, transaction)
        elif transaction.type == "transfer":
            destination: FinancialAccount = self._required("account", transaction.to_account_id)
            self._apply_balance_delta(source, transaction.amount, -1 * sign, transaction)
            self._apply_balance_delta(destination, transaction.amount, 1 * sign, transaction)
        elif transaction.type == "adjustment":
            self._apply_balance_delta(source, transaction.amount, sign, transaction)

    def _apply_balance_delta(
        self, account: FinancialAccount, amount: int, sign: int, transaction: Transaction
    ) -> None:
        account.balance_calculated = account.balance_calculated + sign * amount

    # ---- Debts ----

    def create_debt(
        self,
        household_id: str,
        *,
        account_id: str | None,
        name: str,
        type: str,
        original_amount: int,
        minimum_payment: int,
        interest_rate: float,
        due_day: int,
        status: str = "active",
    ) -> Debt:
        self._required("household", household_id)
        if account_id:
            account = self._required("account", account_id)
            if account.household_id != household_id:
                raise DomainRuleError("La cuenta asociada no pertenece al hogar")
        name = name.strip()
        if not name:
            raise DomainRuleError("La deuda requiere un nombre")
        debt = Debt(
            id=self._new_id("dbt"),
            household_id=household_id,
            account_id=account_id,
            name=name,
            type=type,
            original_amount=original_amount,
            current_balance=original_amount,
            minimum_payment=minimum_payment,
            interest_rate=interest_rate,
            due_day=due_day,
            status=status,
        )
        self.session.add(debt)
        self.session.commit()
        self.session.refresh(debt)
        return debt

    def list_debts(self, household_id: str) -> list[Debt]:
        self._required("household", household_id)
        statement = select(Debt).where(Debt.household_id == household_id).order_by(Debt.name)
        return list(self.session.scalars(statement))

    def get_debt(self, debt_id: str) -> Debt:
        return self._required("debt", debt_id)

    def update_debt(
        self,
        debt_id: str,
        *,
        account_id: str | None,
        name: str | None,
        type: str | None,
        current_balance: int | None,
        minimum_payment: int | None,
        interest_rate: float | None,
        due_day: int | None,
        status: str | None,
    ) -> Debt:
        debt = self._required("debt", debt_id)
        if account_id is not None:
            if account_id:
                account = self._required("account", account_id)
                if account.household_id != debt.household_id:
                    raise DomainRuleError("La cuenta asociada no pertenece al hogar")
            debt.account_id = account_id or None
        if name is not None:
            normalized = name.strip()
            if not normalized:
                raise DomainRuleError("El nombre de la deuda no puede quedar vacío")
            debt.name = normalized
        if type is not None:
            debt.type = type
        if current_balance is not None:
            debt.current_balance = current_balance
        if minimum_payment is not None:
            debt.minimum_payment = minimum_payment
        if interest_rate is not None:
            debt.interest_rate = interest_rate
        if due_day is not None:
            debt.due_day = due_day
        if status is not None:
            debt.status = status
        self.session.commit()
        self.session.refresh(debt)
        return debt

    # ---- Debt payments (CF1-09) ----

    def pay_debt(
        self,
        debt_id: str,
        *,
        account_id: str | None,
        recorded_by: str | None,
        amount: int,
        type: str,
        payment_date: date,
    ) -> DebtPayment:
        debt = self._required("debt", debt_id)
        if debt.status not in {"active"}:
            raise DomainRuleError("Solo se pueden pagar deudas activas")
        if amount <= 0:
            raise DomainRuleError("El pago debe ser un monto positivo")
        if account_id:
            account = self._required("account", account_id)
            if account.household_id != debt.household_id:
                raise DomainRuleError("La cuenta de pago no pertenece al hogar de la deuda")
        if recorded_by:
            author = self._required("member", recorded_by)
            if author.household_id != debt.household_id:
                raise DomainRuleError("El autor no pertenece al hogar de la deuda")

        transaction = None
        if account_id:
            transaction = Transaction(
                id=self._new_id("txn"),
                account_id=account_id,
                to_account_id=None,
                category_id=None,
                recorded_by=recorded_by,
                type="payment",
                amount=amount,
                date=payment_date,
                description=f"Pago de deuda: {debt.name}",
                status="posted",
            )
            self.session.add(transaction)
            self.session.flush()
            self._apply_balance_delta(account, amount, -1, transaction)
        if debt.current_balance - amount < 0:
            raise DomainRuleError("El pago excede el saldo actual de la deuda")
        debt.current_balance -= amount
        if debt.current_balance == 0:
            debt.status = "paid_off"

        payment = DebtPayment(
            id=self._new_id("dpay"),
            debt_id=debt_id,
            account_id=account_id,
            transaction_id=transaction.id if transaction else None,
            recorded_by=recorded_by,
            amount=amount,
            type=type,
            payment_date=payment_date,
        )
        self.session.add(payment)
        self.session.commit()
        self.session.refresh(payment)
        return payment

    def list_debt_payments(self, debt_id: str) -> list[DebtPayment]:
        self._required("debt", debt_id)
        statement = (
            select(DebtPayment)
            .where(DebtPayment.debt_id == debt_id)
            .order_by(DebtPayment.payment_date)
        )
        return list(self.session.scalars(statement))

    # ---- Installments ----

    def create_installment(
        self,
        debt_id: str,
        *,
        due_date: date,
        principal_amount: int,
        interest_amount: int,
        fee_amount: int,
    ) -> Installment:
        self._required("debt", debt_id)
        installment = Installment(
            id=self._new_id("ins"),
            debt_id=debt_id,
            due_date=due_date,
            principal_amount=principal_amount,
            interest_amount=interest_amount,
            fee_amount=fee_amount,
            total_amount=principal_amount + interest_amount + fee_amount,
            status="pending",
        )
        self.session.add(installment)
        self.session.commit()
        self.session.refresh(installment)
        return installment

    def list_installments(self, debt_id: str) -> list[Installment]:
        self._required("debt", debt_id)
        statement = (
            select(Installment).where(Installment.debt_id == debt_id).order_by(Installment.due_date)
        )
        return list(self.session.scalars(statement))

    def get_installment(self, installment_id: str) -> Installment:
        return self._required("installment", installment_id)

    def update_installment(
        self,
        installment_id: str,
        *,
        status: str | None,
    ) -> Installment:
        installment = self._required("installment", installment_id)
        if status is not None:
            installment.status = status
        self.session.commit()
        self.session.refresh(installment)
        return installment

    # ---- Budgets ----

    def create_budget(
        self, household_id: str, *, year: int, month: int, status: str = "draft"
    ) -> Budget:
        self._required("household", household_id)
        existing = self.session.scalar(
            select(Budget.id).where(
                Budget.household_id == household_id,
                Budget.year == year,
                Budget.month == month,
            )
        )
        if existing:
            raise DomainRuleError("Ya existe un presupuesto para ese periodo")
        budget = Budget(
            id=self._new_id("bud"),
            household_id=household_id,
            year=year,
            month=month,
            status=status,
        )
        self.session.add(budget)
        self.session.commit()
        self.session.refresh(budget)
        return budget

    def list_budgets(self, household_id: str) -> list[Budget]:
        self._required("household", household_id)
        statement = (
            select(Budget)
            .where(Budget.household_id == household_id)
            .order_by(Budget.year, Budget.month)
        )
        return list(self.session.scalars(statement))

    def get_budget(self, budget_id: str) -> Budget:
        return self._required("budget", budget_id)

    def update_budget(self, budget_id: str, *, status: str | None) -> Budget:
        budget = self._required("budget", budget_id)
        if status is not None:
            budget.status = status
        self.session.commit()
        self.session.refresh(budget)
        return budget

    def set_budget_category(
        self,
        budget_id: str,
        *,
        category_id: str,
        planned_amount: int,
    ) -> BudgetCategory:
        budget = self._required("budget", budget_id)
        category = self._required("category", category_id)
        if category.household_id != budget.household_id:
            raise DomainRuleError("La categoría no pertenece al hogar del presupuesto")
        if category.kind != "expense":
            raise DomainRuleError("El presupuesto solo planifica categorías de gasto")
        budget_category = self.session.scalar(
            select(BudgetCategory).where(
                BudgetCategory.budget_id == budget_id,
                BudgetCategory.category_id == category_id,
            )
        )
        if budget_category is None:
            budget_category = BudgetCategory(
                id=self._new_id("bcat"),
                budget_id=budget_id,
                category_id=category_id,
                planned_amount=planned_amount,
                actual_amount=0,
            )
            self.session.add(budget_category)
        else:
            budget_category.planned_amount = planned_amount
        self.session.commit()
        self.session.refresh(budget_category)
        return budget_category

    def list_budget_categories(self, budget_id: str) -> list[BudgetCategory]:
        self._required("budget", budget_id)
        statement = (
            select(BudgetCategory)
            .where(BudgetCategory.budget_id == budget_id)
            .order_by(BudgetCategory.id)
        )
        return list(self.session.scalars(statement))

    def _validate_transaction(
        self,
        *,
        account_id: str,
        to_account_id: str | None,
        category_id: str | None,
        recorded_by: str | None,
        type: str,
        amount: int,
    ) -> str | None:
        account = self._required("account", account_id)
        if type == "transfer":
            if not to_account_id:
                raise DomainRuleError("Una transferencia requiere cuenta destino")
            if to_account_id == account_id:
                raise DomainRuleError("La cuenta destino debe ser distinta de la origen")
            destination = self._required("account", to_account_id)
            if destination.household_id != account.household_id:
                raise DomainRuleError(
                    "Solo se permiten transferencias entre cuentas del mismo hogar"
                )
            if amount < 0:
                raise DomainRuleError("El monto de la transferencia debe ser positivo")
        else:
            to_account_id = None
            if amount <= 0 and type in {"expense", "income", "payment"}:
                raise DomainRuleError("El monto debe ser positivo")
            if type == "adjustment" and amount == 0:
                raise DomainRuleError("Un ajuste no puede ser de monto cero")
        if category_id:
            category = self._required("category", category_id)
            if category.household_id != account.household_id:
                raise DomainRuleError("La categoría no pertenece al hogar de la cuenta")
            self._validate_category_for_type(category, type)
        if recorded_by:
            author = self._required("member", recorded_by)
            if author.household_id != account.household_id:
                raise DomainRuleError("El autor no pertenece al hogar de la cuenta")
        return to_account_id

    def _track_expense_in_budget(
        self,
        account: FinancialAccount,
        category_id: str | None,
        amount: int,
        date: date,
        increment: bool,
    ) -> None:
        if category_id is None:
            return
        budget = self.session.scalar(
            select(Budget).where(
                Budget.household_id == account.household_id,
                Budget.year == date.year,
                Budget.month == date.month,
                Budget.status == "active",
            )
        )
        if budget is None:
            return
        budget_category = self.session.scalar(
            select(BudgetCategory).where(
                BudgetCategory.budget_id == budget.id,
                BudgetCategory.category_id == category_id,
            )
        )
        if budget_category is None:
            return
        if increment:
            budget_category.actual_amount += amount
        else:
            budget_category.actual_amount = max(0, budget_category.actual_amount - amount)

    # ---- Reports ----

    @staticmethod
    def _month_filter(column, year: int, month: int):
        return func.strftime("%Y-%m", column) == f"{year:04d}-{month:02d}"

    def dashboard(self, household_id: str, *, year: int, month: int) -> dict:
        self._required("household", household_id)
        account_ids = list(
            self.session.scalars(
                select(FinancialAccount.id).where(FinancialAccount.household_id == household_id)
            )
        )
        statements = [
            Transaction.account_id.in_(account_ids) | Transaction.to_account_id.in_(account_ids)
        ]
        income = int(
            self.session.scalar(
                select(func.coalesce(func.sum(Transaction.amount), 0)).where(
                    *statements,
                    Transaction.type == "income",
                    self._month_filter(Transaction.date, year, month),
                )
            )
            or 0
        )
        expenses = int(
            self.session.scalar(
                select(func.coalesce(func.sum(Transaction.amount), 0)).where(
                    *statements,
                    Transaction.type == "expense",
                    self._month_filter(Transaction.date, year, month),
                )
            )
            or 0
        )
        budget = self.session.scalar(
            select(Budget).where(
                Budget.household_id == household_id,
                Budget.year == year,
                Budget.month == month,
            )
        )
        budget_rows = []
        if budget is not None:
            rows = list(
                self.session.scalars(
                    select(BudgetCategory).where(BudgetCategory.budget_id == budget.id)
                )
            )
            for row in rows:
                category = self.session.get(Category, row.category_id)
                budget_rows.append(
                    {
                        "category_id": row.category_id,
                        "category_name": category.name if category else None,
                        "planned": row.planned_amount,
                        "actual": row.actual_amount,
                    }
                )
        debt_info = self.debt_summary(household_id)
        worth_info = self.net_worth(household_id)
        expected_sources = list(
            self.session.scalars(
                select(IncomeSource).where(
                    IncomeSource.household_id == household_id,
                    IncomeSource.status == "active",
                )
            )
        )
        expected_income = sum((s.expected_amount or 0) for s in expected_sources)
        monthly_rows = self.session.execute(
            select(
                func.strftime("%m", Transaction.date),
                Transaction.type,
                func.coalesce(func.sum(Transaction.amount), 0),
            )
            .where(
                *statements,
                Transaction.type.in_(("income", "expense")),
                func.strftime("%Y", Transaction.date) == f"{year:04d}",
            )
            .group_by(func.strftime("%m", Transaction.date), Transaction.type)
        )
        by_month: dict[int, dict[str, int]] = {}
        for m_label, ttype, total in monthly_rows:
            by_month.setdefault(int(m_label), {})[ttype] = int(total)
        series = [
            {
                "month": i,
                "income": by_month.get(i, {}).get("income", 0),
                "expenses": by_month.get(i, {}).get("expense", 0),
                "balance": by_month.get(i, {}).get("income", 0)
                - by_month.get(i, {}).get("expense", 0),
            }
            for i in range(1, 13)
        ]
        category_rows = self.session.execute(
            select(Category.name, func.coalesce(func.sum(Transaction.amount), 0))
            .join(Transaction, Transaction.category_id == Category.id)
            .where(
                *statements,
                Transaction.type == "expense",
                Transaction.category_id.is_not(None),
                self._month_filter(Transaction.date, year, month),
            )
            .group_by(Category.name)
            .order_by(func.sum(Transaction.amount).desc())
        )
        expense_categories = [
            {"name": name, "amount": int(total)} for name, total in category_rows
        ]
        return {
            "household_id": household_id,
            "period": f"{year:04d}-{month:02d}",
            "income": income,
            "expenses": expenses,
            "balance": income - expenses,
            "budget": budget_rows,
            "total_debt": debt_info["total_current_balance"],
            "net_worth": worth_info["net_worth"],
            "series": series,
            "expense_categories": expense_categories,
            "expected_income": expected_income,
        }

    def upcoming_payments(self, household_id: str, *, days: int, today: date | None = None) -> dict:
        self._required("household", household_id)
        today = today or date.today()
        horizon = today + timedelta(days=days)
        installments = list(
            self.session.scalars(
                select(Installment)
                .join(Debt, Installment.debt_id == Debt.id)
                .where(
                    Debt.household_id == household_id,
                    Installment.status == "pending",
                    Installment.due_date >= today,
                    Installment.due_date <= horizon,
                )
                .order_by(Installment.due_date)
            )
        )
        pending_installments = [
            {
                "id": i.id,
                "debt_id": i.debt_id,
                "due_date": i.due_date,
                "total_amount": i.total_amount,
                "days_left": (i.due_date - today).days,
            }
            for i in installments
        ]
        recurring = list(
            self.session.scalars(
                select(Debt).where(
                    Debt.household_id == household_id,
                    Debt.status == "active",
                    Debt.minimum_payment > 0,
                )
            )
        )
        recurring_minimums = []
        month_cursor = today.replace(day=1)
        for _ in range(2):
            for debt in recurring:
                due = self._due_date_in_month(debt.due_day, month_cursor)
                if today <= due <= horizon:
                    recurring_minimums.append(
                        {
                            "debt_id": debt.id,
                            "debt_name": debt.name,
                            "due_date": due,
                            "minimum_payment": debt.minimum_payment,
                        }
                    )
            next_month = (month_cursor + timedelta(days=32)).replace(day=1)
            month_cursor = next_month
        return {
            "as_of": today.isoformat(),
            "pending_installments": pending_installments,
            "recurring_minimums": recurring_minimums,
        }

    @staticmethod
    def _due_date_in_month(due_day: int, month: date) -> date:
        try:
            return month.replace(day=due_day)
        except ValueError:
            return month.replace(day=28)

    def weekly_summary(self, household_id: str, *, today: date) -> dict:
        """Resumen de la semana ISO actual (de lunes a hoy) — CF4-06/07."""
        self._required("household", household_id)
        week_start = today - timedelta(days=today.weekday())
        account_ids = list(
            self.session.scalars(
                select(FinancialAccount.id).where(FinancialAccount.household_id == household_id)
            )
        )
        statements = [
            Transaction.account_id.in_(account_ids) | Transaction.to_account_id.in_(account_ids)
        ]
        window = Transaction.date.between(week_start, today)
        income = int(
            self.session.scalar(
                select(func.coalesce(func.sum(Transaction.amount), 0)).where(
                    *statements, Transaction.type == "income", window
                )
            )
            or 0
        )
        expenses = int(
            self.session.scalar(
                select(func.coalesce(func.sum(Transaction.amount), 0)).where(
                    *statements, Transaction.type == "expense", window
                )
            )
            or 0
        )
        return {
            "week_start": week_start,
            "week_end": today,
            "income": income,
            "expenses": expenses,
            "balance": income - expenses,
        }

    def debt_summary(self, household_id: str) -> dict:
        self._required("household", household_id)
        rows = list(self.session.scalars(select(Debt).where(Debt.household_id == household_id)))
        by_status: dict[str, dict] = {}
        for row in rows:
            bucket = by_status.setdefault(row.status, {"current_balance": 0, "count": 0})
            bucket["current_balance"] += row.current_balance
            bucket["count"] += 1
        return {
            "household_id": household_id,
            "total_current_balance": sum(row.current_balance for row in rows),
            "total_original_amount": sum(row.original_amount for row in rows),
            "count": len(rows),
            "by_status": by_status,
        }

    def net_worth(self, household_id: str) -> dict:
        self._required("household", household_id)
        assets = int(
            self.session.scalar(
                select(func.coalesce(func.sum(FinancialAccount.balance_calculated), 0)).where(
                    FinancialAccount.household_id == household_id,
                    FinancialAccount.status == "active",
                )
            )
            or 0
        )
        liabilities = int(
            self.session.scalar(
                select(func.coalesce(func.sum(Debt.current_balance), 0)).where(
                    Debt.household_id == household_id,
                    Debt.status == "active",
                )
            )
            or 0
        )
        return {
            "household_id": household_id,
            "assets": assets,
            "liabilities": liabilities,
            "net_worth": assets - liabilities,
            "currency": "CLP",
        }

    def monthly_close(self, household_id: str, *, year: int, month: int) -> dict:
        self._required("household", household_id)
        budget = self.session.scalar(
            select(Budget).where(
                Budget.household_id == household_id,
                Budget.year == year,
                Budget.month == month,
            )
        )
        if budget is None:
            raise DomainRuleError("No existe un presupuesto para el periodo")
        if budget.status == "closed":
            raise DomainRuleError("El periodo ya está cerrado")
        budget.status = "closed"

        period_start = date(year, month, 1)
        period_end = (period_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
        installments = list(
            self.session.scalars(
                select(Installment)
                .join(Debt, Installment.debt_id == Debt.id)
                .where(
                    Debt.household_id == household_id,
                    Installment.due_date >= period_start,
                    Installment.due_date <= period_end,
                )
            )
        )
        marked: dict[str, str] = {}
        for installment in installments:
            debt_id = installment.debt_id
            if debt_id not in marked:
                has_payment = self.session.scalar(
                    select(DebtPayment.id)
                    .where(
                        DebtPayment.debt_id == debt_id,
                        self._month_filter(DebtPayment.payment_date, year, month),
                    )
                    .limit(1)
                )
                marked[debt_id] = "paid" if has_payment else "overdue"
            installment.status = marked[debt_id]

        summary = self.dashboard(household_id, year=year, month=month)
        self.session.commit()
        return {
            "household_id": household_id,
            "period": f"{year:04d}-{month:02d}",
            "budget_status": "closed",
            "installments_in_period": len(installments),
            "overdue_installments": sum(1 for s in marked.values() if s == "overdue"),
            "summary": summary,
        }

    @staticmethod
    def _compile_payment_schedule(
        debts: list[Debt], monthly_payment: int, extra_by_month: dict[int, int]
    ) -> dict:
        balance = {debt.id: debt.current_balance for debt in debts}
        minimum_payment = {debt.id: debt.minimum_payment for debt in debts}
        rate_monthly = {debt.id: debt.interest_rate / 100 / 12 for debt in debts}
        total_interest = 0
        total_paid = 0
        month = 0
        converged = True
        series: list[dict] = []
        while any(amount > 0 for amount in balance.values()):
            month += 1
            if month > 720:
                converged = False
                break
            interests = {
                debt_id: int(round(saldo * rate_monthly[debt_id]))
                for debt_id, saldo in balance.items()
                if saldo > 0
            }
            for debt_id, interest in interests.items():
                balance[debt_id] += interest
                total_interest += interest

            available = monthly_payment + extra_by_month.get(month, 0)
            payments = {debt_id: 0 for debt_id in balance}

            for debt_id in minimum_payment:
                pay = min(minimum_payment[debt_id], balance[debt_id])
                payments[debt_id] += pay

            if sum(payments.values()) > available:
                converged = False
                break
            available -= sum(payments.values())

            for debt_id in balance:
                if balance[debt_id] > 0 and available > 0:
                    pay = min(available, balance[debt_id])
                    payments[debt_id] += pay
                    available -= pay
            for debt_id, pay in payments.items():
                balance[debt_id] = max(0, balance[debt_id] - pay)
                total_paid += pay

            series.append(
                {
                    "month": month,
                    "balance": sum(max(0, amount) for amount in balance.values()),
                    "interest": total_interest,
                }
            )

        return {
            "months": month if converged else None,
            "converged": converged,
            "total_interest": total_interest,
            "total_paid": total_paid,
            "series": series,
        }

    def simulate_strategy(self, household_id: str, *, strategy: str, monthly_payment: int) -> dict:
        if strategy not in {"snowball", "avalanche"}:
            raise DomainRuleError("Estrategia desconocida")
        debts = list(
            self.session.scalars(
                select(Debt)
                .where(Debt.household_id == household_id, Debt.status == "active")
                .order_by(Debt.name)
            )
        )
        if not debts:
            raise DomainRuleError("No hay deudas activas para simular")
        if monthly_payment <= 0:
            raise DomainRuleError("El pago mensual debe ser positivo")

        if strategy == "snowball":
            ordered = sorted(debts, key=lambda d: (d.current_balance, d.name))
        else:
            ordered = sorted(debts, key=lambda d: (-d.interest_rate, d.name))

        result = self._compile_payment_schedule(ordered, monthly_payment, {})
        assumptions = {
            "interest": "tasas mensuales = interés anual / 12, interés simple",
            "constraints": "se asume pago de mínimos; excedente a la deuda objetivo",
        }
        return {
            "household_id": household_id,
            "strategy": strategy,
            "monthly_payment": monthly_payment,
            "months_to_freedom": result["months"],
            "converged": result["converged"],
            "total_interest": result["total_interest"],
            "total_paid": result["total_paid"],
            "months_series": result["series"],
            "payoff_order": [
                {
                    "debt_id": debt.id,
                    "name": debt.name,
                    "current_balance": debt.current_balance,
                    "interest_rate": debt.interest_rate,
                    "minimum_payment": debt.minimum_payment,
                }
                for debt in ordered
            ],
            "assumptions": assumptions,
        }

    # ---- Payment plans and scenarios ----

    def create_payment_plan(self, household_id: str, *, strategy: str, name: str) -> PaymentPlan:
        self._required("household", household_id)
        if strategy not in {"snowball", "avalanche"}:
            raise DomainRuleError("Estrategia desconocida")
        name = name.strip()
        if not name:
            raise DomainRuleError("El plan requiere un nombre")
        plan = PaymentPlan(
            id=self._new_id("pln"),
            household_id=household_id,
            strategy=strategy,
            name=name,
            status="draft",
        )
        self.session.add(plan)
        self.session.commit()
        self.session.refresh(plan)
        return plan

    def list_payment_plans(self, household_id: str) -> list[PaymentPlan]:
        self._required("household", household_id)
        statement = (
            select(PaymentPlan)
            .where(PaymentPlan.household_id == household_id)
            .order_by(PaymentPlan.id)
        )
        return list(self.session.scalars(statement))

    def get_payment_plan(self, plan_id: str) -> PaymentPlan:
        return self._required("payment_plan", plan_id)

    def update_payment_plan(self, plan_id: str, *, status: str | None) -> PaymentPlan:
        plan = self._required("payment_plan", plan_id)
        if status is not None:
            plan.status = status
        self.session.commit()
        self.session.refresh(plan)
        return plan

    def run_scenario(
        self,
        plan_id: str,
        *,
        name: str,
        monthly_payment: int,
        extra_income: list[dict],
    ) -> ProjectionScenario:
        plan = self._required("payment_plan", plan_id)
        if monthly_payment <= 0:
            raise DomainRuleError("El pago mensual debe ser positivo")
        name = name.strip()
        if not name:
            raise DomainRuleError("El escenario requiere un nombre")
        extra_by_month = {}
        for item in extra_income:
            offset = item.get("month_offset")
            amount = item.get("amount")
            if not offset or not amount:
                raise DomainRuleError("Cada ingreso extraordinario requiere month_offset y amount")
            extra_by_month[int(offset)] = extra_by_month.get(int(offset), 0) + int(amount)
        debts = list(
            self.session.scalars(
                select(Debt).where(Debt.household_id == plan.household_id, Debt.status == "active")
            )
        )
        if not debts:
            raise DomainRuleError("No hay deudas activas para simular")
        if plan.strategy == "snowball":
            ordered = sorted(debts, key=lambda d: (d.current_balance, d.name))
        else:
            ordered = sorted(debts, key=lambda d: (-d.interest_rate, d.name))
        result = self._compile_payment_schedule(ordered, monthly_payment, extra_by_month)
        assumptions = {
            "strategy": plan.strategy,
            "interest": "tasas mensuales = interés anual / 12, interés simple",
            "note": "la simulación no modifica saldos ni cuotas reales",
        }
        summary = {
            "months_to_freedom": result["months"],
            "converged": result["converged"],
            "total_interest": result["total_interest"],
            "total_paid": result["total_paid"],
            "payoff_order": [
                {
                    "debt_id": d.id,
                    "name": d.name,
                    "current_balance": d.current_balance,
                    "interest_rate": d.interest_rate,
                    "minimum_payment": d.minimum_payment,
                }
                for d in ordered
            ],
        }
        scenario = ProjectionScenario(
            id=self._new_id("sce"),
            plan_id=plan_id,
            name=name,
            monthly_payment=monthly_payment,
            extra_income=extra_income,
            assumptions=assumptions,
            result_summary=summary,
        )
        self.session.add(scenario)
        self.session.commit()
        self.session.refresh(scenario)
        return scenario

    def list_scenarios(self, plan_id: str) -> list[ProjectionScenario]:
        plan = self._required("payment_plan", plan_id)
        statement = (
            select(ProjectionScenario)
            .where(ProjectionScenario.plan_id == plan.id)
            .order_by(ProjectionScenario.id)
        )
        return list(self.session.scalars(statement))

    def get_scenario(self, scenario_id: str) -> ProjectionScenario:
        return self._required("projection_scenario", scenario_id)

    # ---- Import batches (Fase 2, CF2-02) ----

    def create_import_batch(
        self,
        *,
        household_id: str,
        account_id: str,
        source_filename: str,
        source_kind: str,
        content: bytes,
        column_mapping: dict[str, str],
        header_row: int = 1,
        separator: str | None = None,
    ) -> ImportBatch:
        self._required("household", household_id)
        account = self._required("account", account_id)
        if account.household_id != household_id:
            raise DomainRuleError("La cuenta no pertenece al hogar")
        try:
            table = extract_table(
                content,
                source_kind=source_kind,
                header_row=header_row,
                separator=separator,
            )
            mapping = normalize_mapping(column_mapping, table.headers)
            parsed = parse_batch(table, mapping)
        except ImportFormatError as error:
            raise DomainRuleError(f"No se pudo importar el archivo: {error}") from error
        statement_meta: dict = {}
        if account.type == "credit_card":
            statement_meta = detect_card_statement(table)
        batch = ImportBatch(
            id=self._new_id("imp"),
            household_id=household_id,
            account_id=account_id,
            source_filename=Path(source_filename).name,
            source_kind=source_kind,
            status="parsed",
            column_mapping=mapping,
            header_row=table.first_row_number - 1,
            separator=table.separator,
            total_rows=parsed.total_rows,
            valid_rows=parsed.valid_rows,
            invalid_rows=parsed.invalid_rows,
            statement_meta=statement_meta or None,
            rows=[
                {
                    "row": row.row_number,
                    "values": row.values,
                    "valid": row.valid,
                    "errors": row.errors,
                }
                for row in parsed.rows
            ],
        )
        self.session.add(batch)
        self.session.commit()
        self.session.refresh(batch)
        return batch

    def list_import_batches(self, household_id: str) -> list[ImportBatch]:
        self._required("household", household_id)
        statement = (
            select(ImportBatch)
            .where(ImportBatch.household_id == household_id)
            .order_by(ImportBatch.created_at.desc())
        )
        return list(self.session.scalars(statement))

    def get_import_batch(self, batch_id: str) -> ImportBatch:
        return self._required("import_batch", batch_id)

    def _existing_posted(self, account_id: str) -> list[dict]:
        rows = list(
            self.session.scalars(
                select(Transaction).where(
                    Transaction.account_id == account_id, Transaction.status == "posted"
                )
            )
        )
        return [
            {
                "id": txn.id,
                "date": txn.date,
                "amount": txn.amount,
                "description": txn.description,
                "type": txn.type,
                "external_id": txn.external_id,
                "external_source": txn.external_source,
            }
            for txn in rows
        ]

    def _category_rules_for(self, household_id: str) -> list[dict]:
        rows = list(
            self.session.scalars(
                select(ImportCategoryRule)
                .where(ImportCategoryRule.household_id == household_id)
                .order_by(ImportCategoryRule.created_at)
            )
        )
        return [
            {
                "column": rule.column,
                "pattern": rule.pattern,
                "category_id": rule.category_id,
                "enabled": bool(rule.enabled),
            }
            for rule in rows
        ]

    def preview_import_batch(self, batch_id: str) -> dict:
        batch = self._required("import_batch", batch_id)
        account = self._required("account", batch.account_id)
        rules = self._category_rules_for(account.household_id)
        kind_by_category = {
            category.id: category.kind
            for category in self.session.scalars(
                select(Category).where(Category.household_id == account.household_id)
            )
        }
        values_by_row = {int(row.get("row", 0)): row.get("values") or {} for row in batch.rows}
        movements = build_movement_previews(batch.rows)
        existing = self._existing_posted(batch.account_id)
        attach_duplicates(
            movements, existing, account_id=batch.account_id, source=batch.source_filename
        )
        mismatches, balance_ok = reconcile_balances(movements)
        for movement in movements:
            movement.balance_ok = balance_ok.get(movement.row_number)
        return {
            "id": batch.id,
            "status": batch.status,
            "account_type": account.type,
            "statement_meta": batch.statement_meta or {},
            "total_rows": batch.total_rows,
            "valid_rows": batch.valid_rows,
            "invalid_rows": batch.invalid_rows,
            "duplicate_rows": sum(1 for m in movements if m.duplicate),
            "reconciliation_mismatches": len(mismatches),
            "rows": [
                {
                    "row": m.row_number,
                    "date": m.date,
                    "description": m.description,
                    "amount": m.amount,
                    "balance": m.balance,
                    "external_id": m.external_id,
                    "kind": m.kind,
                    "valid": m.valid,
                    "errors": m.errors,
                    "balance_ok": m.balance_ok,
                    "duplicate": m.duplicate,
                    "duplicate_type": m.duplicate_type,
                    "duplicate_of": m.duplicate_of,
                    "suggested_category_id": self._suggest_category_for_movement(
                        rules, values_by_row, m, kind_by_category
                    ),
                }
                for m in movements
            ],
        }

    @staticmethod
    def _suggest_category_for_movement(
        rules: list[dict],
        values_by_row: dict[int, dict],
        movement,
        kind_by_category: dict[str, str],
    ) -> str | None:
        suggested = suggest_category(rules, values_by_row.get(movement.row_number) or {})
        if suggested and kind_by_category.get(suggested) == movement.kind:
            return suggested
        return None

    def _add_review_item(
        self,
        batch: ImportBatch,
        account: FinancialAccount,
        *,
        row_number: int,
        values: dict,
        kind: str,
        reason: str,
    ) -> None:
        self.session.add(
            ImportReview(
                id=self._new_id("rev"),
                batch_id=batch.id,
                household_id=batch.household_id,
                account_id=account.id,
                source_filename=batch.source_filename,
                row_number=row_number,
                values=values,
                kind=kind,
                reason=reason,
                status="pending",
            )
        )

    def _create_imported_transaction(
        self,
        batch: ImportBatch,
        account: FinancialAccount,
        movement,
        category_id: str | None,
    ) -> Transaction:
        if movement.kind not in {"income", "expense"} or movement.amount is None:
            raise DomainRuleError(
                f"Filas {movement.row_number}: no se pudo determinar el tipo de movimiento"
            )
        resolved_category: str | None = None
        if category_id:
            category = self._required("category", category_id)
            if category.household_id == account.household_id and category.kind == movement.kind:
                resolved_category = category.id
        transaction = Transaction(
            id=self._new_id("txn"),
            account_id=account.id,
            to_account_id=None,
            category_id=resolved_category,
            recorded_by=None,
            import_batch_id=batch.id,
            type=movement.kind,
            amount=abs(movement.amount),
            date=movement.date,
            description=movement.description,
            external_id=movement.external_id,
            external_source=batch.source_filename,
            status="posted",
        )
        self.session.add(transaction)
        sign = 1 if movement.kind == "income" else -1
        self._apply_balance_delta(account, abs(movement.amount), sign, transaction)
        return transaction

    def _apply_card_statement(
        self, batch: ImportBatch, account: FinancialAccount, meta: dict
    ) -> dict:
        """Aplica el resumen detectado de una cartola a la cuenta y su deuda.

        - Empareja (o crea si no existe) la deuda ligada a la cuenta de tarjeta
          y sincroniza saldo, pago mínimo y día de vencimiento.
        - Actualiza en la cuenta el saldo informado, el cupo y el vencimiento.
        """
        total_debt = meta.get("total_debt")
        total_to_pay = meta.get("total_to_pay")
        minimum_payment = meta.get("minimum_payment")
        due_day: int | None = None
        if meta.get("due_date"):
            try:
                due_day = date.fromisoformat(meta["due_date"]).day
            except ValueError:
                due_day = None
        balance = int(total_debt) if total_debt is not None else (
            int(total_to_pay) if total_to_pay is not None else None
        )

        debt = self.session.scalar(
            select(Debt)
            .where(
                Debt.household_id == account.household_id,
                Debt.account_id == account.id,
            )
            .order_by(Debt.created_at, Debt.id)
            .limit(1)
        )
        debt_id: str | None = None
        created_debt = False
        updated: list[str] = []
        if debt is None:
            if balance is not None:
                debt = Debt(
                    id=self._new_id("dbt"),
                    household_id=account.household_id,
                    account_id=account.id,
                    name=account.name,
                    type="credit_card",
                    original_amount=balance,
                    current_balance=balance,
                    minimum_payment=int(minimum_payment) if minimum_payment is not None else 0,
                    interest_rate=0.0,
                    due_day=due_day or account.due_day or 1,
                    status="active",
                )
                self.session.add(debt)
                self.session.flush()
                created_debt = True
                debt_id = debt.id
                updated = ["current_balance", "minimum_payment", "due_day"]
        else:
            debt_id = debt.id
            if balance is not None:
                debt.current_balance = balance
                if debt.status != "active":
                    debt.status = "active"
                updated.append("current_balance")
            if minimum_payment is not None:
                debt.minimum_payment = int(minimum_payment)
                updated.append("minimum_payment")
            if due_day is not None:
                debt.due_day = due_day
                updated.append("due_day")

        if balance is not None:
            account.balance_reported = balance
        if due_day is not None:
            account.due_day = due_day
        if meta.get("credit_limit") is not None:
            account.credit_limit = int(meta["credit_limit"])

        return {
            "account_type": "credit_card",
            "debt_id": debt_id,
            "debt_created": created_debt,
            "updated": sorted(set(updated)),
            "total_debt": balance,
            "minimum_payment": int(minimum_payment) if minimum_payment is not None else None,
            "due_day": due_day,
            "credit_limit": (
                int(meta["credit_limit"]) if meta.get("credit_limit") is not None else None
            ),
        }

    def confirm_import_batch(self, batch_id: str) -> tuple[ImportBatch, dict]:
        batch = self._required("import_batch", batch_id)
        if batch.status != "parsed":
            raise DomainRuleError(
                f"El lote ya fue procesado (estado: {batch.status}); no se puede confirmar otra vez"
            )
        account = self._required("account", batch.account_id)
        rules = self._category_rules_for(account.household_id)
        movements = build_movement_previews(batch.rows)
        by_row = {m.row_number: m for m in movements}
        existing = self._existing_posted(batch.account_id)
        attach_duplicates(
            movements, existing, account_id=batch.account_id, source=batch.source_filename
        )

        created = 0
        queued = 0
        skipped_duplicates = 0
        for row in batch.rows:
            row_number = int(row.get("row", 0))
            movement = by_row.get(row_number)
            if movement is None:
                continue
            values = row.get("values") or {}
            if not movement.valid:
                self._add_review_item(
                    batch,
                    account,
                    row_number=row_number,
                    values=values,
                    kind="invalid",
                    reason="; ".join(movement.errors),
                )
                queued += 1
                continue
            if movement.duplicate:
                if movement.duplicate_type == "identity":
                    skipped_duplicates += 1
                    continue
                reason = "posible duplicado por fecha, monto y descripción"
                if movement.duplicate_of:
                    reason += f" (ya existe la transacción {movement.duplicate_of})"
                self._add_review_item(
                    batch,
                    account,
                    row_number=row_number,
                    values=values,
                    kind="duplicate",
                    reason=reason,
                )
                queued += 1
                continue
            category_id = suggest_category(rules, values)
            self._create_imported_transaction(batch, account, movement, category_id)
            created += 1

        summary = {
            "created": created,
            "queued_for_review": queued,
            "skipped_duplicates": skipped_duplicates,
            "total_rows": batch.total_rows,
        }
        if account.type == "credit_card" and batch.statement_meta:
            summary["card_statement"] = self._apply_card_statement(
                batch, account, batch.statement_meta
            )
        batch.status = "confirmed"
        batch.confirm_summary = summary
        self.session.commit()
        self.session.refresh(batch)
        return batch, summary

    # ---- Import review queue (CF2-10, CF2-11) ----

    def list_import_reviews(
        self,
        *,
        household_id: str | None = None,
        account_id: str | None = None,
        status: str | None = None,
    ) -> list[ImportReview]:
        statement = select(ImportReview).order_by(ImportReview.created_at.desc(), ImportReview.id)
        if household_id:
            self._required("household", household_id)
            statement = statement.where(ImportReview.household_id == household_id)
        if account_id:
            self._required("account", account_id)
            statement = statement.where(ImportReview.account_id == account_id)
        if status:
            statement = statement.where(ImportReview.status == status)
        return list(self.session.scalars(statement))

    def get_import_review(self, review_id: str) -> ImportReview:
        return self._required("import_review", review_id)

    def _movement_from_values(self, row_number: int, values: dict) -> MovementPreview:
        movement = build_movement_previews(
            [{"row": row_number, "values": values, "valid": True, "errors": []}]
        )[0]
        if not movement.valid or movement.kind not in {"income", "expense"}:
            detail = "; ".join(movement.errors) or "no se pudo interpretar la fila"
            raise DomainRuleError(f"Valores corregidos inválidos: {detail}")
        return movement

    def resolve_import_review(
        self, review_id: str, *, action: str, values: dict | None, category_id: str | None
    ) -> ImportReview:
        review = self._required("import_review", review_id)
        if review.status != "pending":
            raise DomainRuleError(f"El ítem de revisión ya fue procesado (estado: {review.status})")
        if action == "discard":
            review.status = "discarded"
            review.resolved_at = utc_now()
            self.session.commit()
            self.session.refresh(review)
            return review

        batch = self._required("import_batch", review.batch_id)
        account = self._required("account", review.account_id)
        merged = {**review.values, **(values or {})}
        if review.kind == "invalid" and not values:
            raise DomainRuleError("Corrija los valores de la fila antes de confirmarla")
        if not merged.get("date") or not merged.get("amount"):
            raise DomainRuleError("Corrija fecha y monto antes de confirmar la fila")
        errors = validate_values(merged)
        if errors:
            raise DomainRuleError(f"Valores corregidos inválidos: {'; '.join(errors)}")
        movement = self._movement_from_values(review.row_number, merged)
        if movement.external_id:
            collision = self.session.scalar(
                select(Transaction).where(
                    Transaction.account_id == account.id,
                    Transaction.external_id == movement.external_id,
                    Transaction.external_source == batch.source_filename,
                )
            )
            if collision is not None:
                raise DomainRuleError(
                    "Ya existe un movimiento con ese ID externo en este lote; descárte el ítem"
                )

        rules = self._category_rules_for(account.household_id)
        suggested = category_id or suggest_category(rules, merged)
        review.values = merged
        transaction = self._create_imported_transaction(batch, account, movement, suggested)
        self.session.flush()
        review.status = "resolved"
        review.transaction_id = transaction.id
        review.resolved_at = utc_now()
        self.session.commit()
        self.session.refresh(review)
        return review

    # ---- Import category rules (CF2-12) ----

    def list_import_category_rules(self, household_id: str) -> list[ImportCategoryRule]:
        self._required("household", household_id)
        statement = (
            select(ImportCategoryRule)
            .where(ImportCategoryRule.household_id == household_id)
            .order_by(ImportCategoryRule.created_at, ImportCategoryRule.id)
        )
        return list(self.session.scalars(statement))

    def create_import_category_rule(
        self, household_id: str, *, column: str, pattern: str, category_id: str
    ) -> ImportCategoryRule:
        self._required("household", household_id)
        if column not in FIELD_BY_KEY:
            raise DomainRuleError(f"La columna '{column}' no existe en el contrato de importación")
        pattern = pattern.strip()
        if not pattern:
            raise DomainRuleError("La regla requiere un patrón de búsqueda")
        category = self._required("category", category_id)
        if category.household_id != household_id:
            raise DomainRuleError("La categoría no pertenece al hogar")
        rule = ImportCategoryRule(
            id=self._new_id("icr"),
            household_id=household_id,
            column=column,
            pattern=pattern,
            category_id=category.id,
            enabled=True,
        )
        self.session.add(rule)
        self.session.commit()
        self.session.refresh(rule)
        return rule

    def update_import_category_rule(
        self,
        rule_id: str,
        *,
        column: str | None,
        pattern: str | None,
        category_id: str | None,
        enabled: bool | None,
    ) -> ImportCategoryRule:
        rule = self._required("import_category_rule", rule_id)
        if column is not None:
            if column not in FIELD_BY_KEY:
                raise DomainRuleError(
                    f"La columna '{column}' no existe en el contrato de importación"
                )
            rule.column = column
        if pattern is not None:
            pattern = pattern.strip()
            if not pattern:
                raise DomainRuleError("La regla requiere un patrón de búsqueda")
            rule.pattern = pattern
        if category_id is not None:
            category = self._required("category", category_id)
            if category.household_id != rule.household_id:
                raise DomainRuleError("La categoría no pertenece al hogar")
            rule.category_id = category.id
        if enabled is not None:
            rule.enabled = enabled
        self.session.commit()
        self.session.refresh(rule)
        return rule

    def delete_import_category_rule(self, rule_id: str) -> None:
        rule = self._required("import_category_rule", rule_id)
        self.session.delete(rule)
        self.session.commit()

    # ---- Asistente con IA (Fase 3, CF3-01..CF3-05) ----

    def _ai_categories(self, household_id: str) -> list[dict]:
        rows = list(
            self.session.scalars(select(Category).where(Category.household_id == household_id))
        )
        return [
            {"id": category.id, "name": category.name, "kind": category.kind} for category in rows
        ]

    def _description_category_history(self, household_id: str, *, months: int = 12) -> list[dict]:
        accounts = list(
            self.session.scalars(
                select(FinancialAccount.id).where(FinancialAccount.household_id == household_id)
            )
        )
        if not accounts:
            return []
        cutoff = date.today() - timedelta(days=months * 31)
        statement = (
            select(
                Transaction.description,
                Transaction.category_id,
                func.count(Transaction.id),
            )
            .where(
                Transaction.account_id.in_(accounts),
                Transaction.type == "expense",
                Transaction.category_id.is_not(None),
                Transaction.status == "posted",
                Transaction.date >= cutoff,
            )
            .group_by(Transaction.description, Transaction.category_id)
        )
        return [
            {"description": description or "", "category_id": category_id, "count": int(count)}
            for description, category_id, count in self.session.execute(statement)
            if category_id
        ]

    def ai_suggest_category(
        self, household_id: str, *, description: str, amount: int | None = None
    ) -> tuple[list[dict], AiProposal]:
        """Sugiere categorías y registra la propuesta como pendiente (nunca aplica)."""
        from cuentafaro.ai import CategorySuggestionContext, get_provider

        self._required("household", household_id)
        provider = get_provider()
        context = CategorySuggestionContext(
            household_id=household_id,
            description=description,
            amount=amount,
            kind="expense",
            rules=self._category_rules_for(household_id),
            categories=self._ai_categories(household_id),
            history=self._description_category_history(household_id),
        )
        suggestions = [
            {
                "category_id": item.category_id,
                "category_name": item.category_name,
                "reason": item.reason,
                "rank": item.rank,
                "confidence": item.confidence,
            }
            for item in provider.suggest_category(context)
        ]
        proposal = self.create_ai_proposal(
            household_id,
            kind="category_suggestion",
            payload={
                "description": description,
                "amount": amount,
                "suggestions": suggestions,
            },
        )
        view = [
            {
                "category_id": item["category_id"],
                "category_name": item["category_name"],
                "reason": item["reason"],
                "rank": item["rank"],
                "confidence": item["confidence"],
            }
            for item in suggestions
        ]
        return view, proposal

    def _ai_month_facts(self, household_id: str, *, year: int, month: int) -> MonthFacts:
        from cuentafaro.ai import MonthFacts

        account_ids = list(
            self.session.scalars(
                select(FinancialAccount.id).where(FinancialAccount.household_id == household_id)
            )
        )
        statements = [
            Transaction.account_id.in_(account_ids) | Transaction.to_account_id.in_(account_ids)
        ]
        income = int(
            self.session.scalar(
                select(func.coalesce(func.sum(Transaction.amount), 0)).where(
                    *statements,
                    Transaction.type == "income",
                    self._month_filter(Transaction.date, year, month),
                )
            )
            or 0
        )
        expenses = int(
            self.session.scalar(
                select(func.coalesce(func.sum(Transaction.amount), 0)).where(
                    *statements,
                    Transaction.type == "expense",
                    self._month_filter(Transaction.date, year, month),
                )
            )
            or 0
        )
        budget_rows: list[dict] = []
        budget = self.session.scalar(
            select(Budget).where(
                Budget.household_id == household_id,
                Budget.year == year,
                Budget.month == month,
            )
        )
        if budget is not None:
            for row in self.session.scalars(
                select(BudgetCategory).where(BudgetCategory.budget_id == budget.id)
            ):
                category = self.session.get(Category, row.category_id)
                budget_rows.append(
                    {
                        "category_id": row.category_id,
                        "name": category.name if category else "Categoría",
                        "planned_amount": row.planned_amount,
                        "actual_amount": row.actual_amount,
                        "budget_id": budget.id,
                    }
                )
        history = self._category_history(account_ids, year, month)
        current_rows = list(
            self.session.execute(
                select(
                    Transaction.category_id,
                    func.sum(Transaction.amount),
                )
                .where(
                    Transaction.account_id.in_(account_ids),
                    Transaction.type == "expense",
                    Transaction.category_id.is_not(None),
                    Transaction.status == "posted",
                    self._month_filter(Transaction.date, year, month),
                )
                .group_by(Transaction.category_id)
            )
        )
        for category_id, total in current_rows:
            entry = history.setdefault(
                category_id, {"name": self._category_name(category_id), "avg": 0}
            )
            entry["current"] = int(total)
        for row in budget_rows:
            entry = history.get(row["category_id"])
            if entry is not None:
                entry["budget_id"] = row["budget_id"]
        return MonthFacts(
            household_id=household_id,
            year=year,
            month=month,
            period=f"{year:04d}-{month:02d}",
            income=income,
            expenses=expenses,
            budget_rows=budget_rows,
            history=history,
        )

    def _category_history(self, account_ids: list[str], year: int, month: int) -> dict[str, dict]:
        """Promedio de gasto de los 12 meses anteriores por categoría (CF3-07)."""
        if not account_ids:
            return {}
        start = date(year, month, 1) - timedelta(days=380)
        end = date(year, month, 1) - timedelta(days=1)
        rows = list(
            self.session.execute(
                select(
                    Transaction.category_id,
                    func.strftime("%Y-%m", Transaction.date),
                    func.sum(Transaction.amount),
                )
                .where(
                    Transaction.account_id.in_(account_ids),
                    Transaction.type == "expense",
                    Transaction.category_id.is_not(None),
                    Transaction.status == "posted",
                    Transaction.date >= start,
                    Transaction.date <= end,
                )
                .group_by(Transaction.category_id, func.strftime("%Y-%m", Transaction.date))
            )
        )
        totals: dict[str, list[tuple[str, int]]] = {}
        months_set: set[str] = set()
        for category_id, period, total in rows:
            totals.setdefault(category_id, []).append((period, int(total)))
            months_set.add(period)
        history: dict[str, dict] = {}
        for category_id, entries in totals.items():
            per_month = dict(entries)
            months_sample = sorted(months_set)
            values = [per_month.get(period, 0) for period in months_sample]
            average = round(sum(values) / len(values)) if values else 0
            history[category_id] = {
                "name": self._category_name(category_id),
                "avg": average,
            }
        return history

    def _category_name(self, category_id: str) -> str:
        category = self.session.get(Category, category_id)
        return category.name if category else "Sin categoría"

    def ai_insights(self, household_id: str, *, year: int, month: int) -> dict:
        from cuentafaro.ai import get_provider

        self._required("household", household_id)
        facts = self._ai_month_facts(household_id, year=year, month=month)
        provider = get_provider()
        insights = [
            {
                "severity": item.severity,
                "title": item.title,
                "detail": item.detail,
                "category_id": item.category_id,
            }
            for item in provider.explain_month(facts)
        ]
        anomalies = [
            {
                "category_id": item.category_id,
                "title": item.title,
                "detail": item.detail,
                "severity": item.severity,
                "budget_id": item.budget_id,
                "suggested_planned_amount": item.suggested_planned_amount,
            }
            for item in provider.detect_anomalies(facts)
        ]
        for anomaly in anomalies:
            period = facts.period
            category_id = anomaly.get("category_id")
            if category_id:
                duplicate = self.session.scalar(
                    select(AiProposal.id).where(
                        AiProposal.household_id == household_id,
                        AiProposal.kind == "anomaly",
                        AiProposal.status == "pending",
                        AiProposal.payload["period"].as_string() == period,
                        AiProposal.payload["category_id"].as_string() == category_id,
                    )
                )
            else:
                duplicate = None
            if duplicate:
                continue
            payload = dict(anomaly)
            payload["period"] = period
            self.create_ai_proposal(household_id, kind="anomaly", payload=payload)
            if anomaly.get("budget_id"):
                adjust_duplicate = self.session.scalar(
                    select(AiProposal.id).where(
                        AiProposal.household_id == household_id,
                        AiProposal.kind == "budget_adjust",
                        AiProposal.status == "pending",
                        AiProposal.payload["period"].as_string() == period,
                        AiProposal.payload["category_id"].as_string() == category_id,
                    )
                )
                if not adjust_duplicate:
                    self.create_ai_proposal(
                        household_id, kind="budget_adjust", payload=dict(payload)
                    )
        if insights:
            period = facts.period
            has_insight = self.session.scalar(
                select(AiProposal.id).where(
                    AiProposal.household_id == household_id,
                    AiProposal.kind == "insight",
                    AiProposal.status == "pending",
                    AiProposal.payload["period"].as_string() == period,
                )
            )
            if not has_insight:
                self.create_ai_proposal(
                    household_id, kind="insight", payload={**insights[0], "period": period}
                )
        return {
            "provider": provider.name,
            "period": facts.period,
            "insights": insights,
            "anomalies": anomalies,
        }

    def create_ai_proposal(self, household_id: str, *, kind: str, payload: dict) -> AiProposal:
        self._required("household", household_id)
        proposal = AiProposal(
            id=self._new_id("prp"),
            household_id=household_id,
            kind=kind,
            payload=payload,
            status="pending",
        )
        self.session.add(proposal)
        self.session.commit()
        self.session.refresh(proposal)
        return proposal

    def list_ai_proposals(
        self, household_id: str, *, status: str | None = None
    ) -> list[AiProposal]:
        self._required("household", household_id)
        statement = select(AiProposal).where(AiProposal.household_id == household_id)
        if status:
            statement = statement.where(AiProposal.status == status)
        return list(
            self.session.scalars(statement.order_by(AiProposal.created_at.desc(), AiProposal.id))
        )

    def get_ai_proposal(self, proposal_id: str) -> AiProposal:
        return self._required("ai_proposal", proposal_id)

    def resolve_ai_proposal(self, proposal_id: str, *, resolution: str) -> AiProposal:
        proposal = self._required("ai_proposal", proposal_id)
        if proposal.status != "pending":
            raise DomainRuleError(f"La propuesta ya fue procesada (estado: {proposal.status})")
        if proposal.kind == "budget_adjust" and resolution == "applied":
            self._apply_budget_adjust_proposal(proposal)
        proposal.status = resolution
        proposal.resolved_at = utc_now()
        self.session.commit()
        self.session.refresh(proposal)
        return proposal

    def _apply_budget_adjust_proposal(self, proposal: AiProposal) -> None:
        payload = proposal.payload or {}
        budget_id = payload.get("budget_id")
        category_id = payload.get("category_id")
        planned = payload.get("suggested_planned_amount")
        if not budget_id or not category_id or planned is None:
            raise DomainRuleError("La propuesta de ajuste no tiene datos suficientes")
        budget = self._required("budget", budget_id)
        if budget.household_id != proposal.household_id:
            raise DomainRuleError("El presupuesto no pertenece al hogar de la propuesta")
        self.set_budget_category(budget_id, category_id=category_id, planned_amount=int(planned))

    # ---- Capturas de mensajería (Fase 4, CF4-02/CF4-03) ----

    def create_capture(
        self,
        household_id: str,
        *,
        kind: str,
        raw_text: str | None = None,
        payload: dict | None = None,
        channel: str = "simulated",
    ) -> Capture:
        """Registra una captura pendiente; nunca la confirma ni crea movimientos."""
        self._required("household", household_id)
        if kind not in ("text", "audio", "image"):
            raise DomainRuleError("kind debe ser text, audio o image")
        capture = Capture(
            id=self._new_id("cap"),
            household_id=household_id,
            channel=channel,
            kind=kind,
            raw_text=(raw_text or "").strip() or None,
            payload=payload or {},
            status="pending",
        )
        self.session.add(capture)
        self.session.commit()
        self.session.refresh(capture)
        return capture

    def list_captures(self, household_id: str, *, status: str | None = None) -> list[Capture]:
        self._required("household", household_id)
        statement = select(Capture).where(Capture.household_id == household_id)
        if status:
            statement = statement.where(Capture.status == status)
        return list(self.session.scalars(statement.order_by(Capture.created_at.desc(), Capture.id)))

    def get_capture(self, capture_id: str) -> Capture:
        return self._required("capture", capture_id)

    def resolve_capture(self, capture_id: str, *, resolution: str) -> Capture:
        capture = self._required("capture", capture_id)
        if capture.status != "pending":
            raise DomainRuleError(f"La captura ya fue procesada (estado: {capture.status})")
        if resolution not in ("reject", "discard"):
            raise DomainRuleError("Resolución no soportada; use 'reject' o 'discard'")
        capture.status = {"reject": "rejected", "discard": "discarded"}[resolution]
        capture.resolved_by = "manual"
        capture.resolved_at = utc_now()
        self.session.commit()
        self.session.refresh(capture)
        return capture

    # ---- Análisis y confirmación de capturas (Fase 4, CF4-04/CF4-05) ----

    def analyze_capture(self, capture_id: str) -> Capture:
        """CF4-04: extrae texto (texto directo u OCR local) y propone movimiento.

        Para audio (sin transcripción local) la captura pasa a ``needs_input``.
        La fuente nunca decide la confirmación: siempre confirma una persona.
        """
        capture = self._required("capture", capture_id)
        if capture.status not in ("pending", "needs_input"):
            raise DomainRuleError("La captura ya fue procesada")
        from cuentafaro.captures import extract_capture_text, parse_capture_proposal

        payload = dict(capture.payload or {})
        text = extract_capture_text(kind=capture.kind, raw_text=capture.raw_text, payload=payload)
        if text and not capture.raw_text:
            capture.raw_text = text[:2000]
        proposal = parse_capture_proposal(text or "")
        suggestions: list[dict] = []
        if proposal.get("description"):
            suggestions = self._capture_category_suggestions(capture.household_id, proposal)
        payload["proposal"] = {
            **proposal,
            "category_id": (suggestions[0] if suggestions else {}).get("category_id"),
            "suggestions": suggestions,
            "processed": True,
        }
        payload["proposal_updated_at"] = utc_now().isoformat()
        capture.payload = payload
        capture.status = "needs_input" if text is None else "pending"
        self.session.commit()
        self.session.refresh(capture)
        return capture

    def _capture_category_suggestions(self, household_id: str, proposal: dict) -> list[dict]:
        from cuentafaro.ai import CategorySuggestionContext, get_provider

        provider = get_provider()
        context = CategorySuggestionContext(
            household_id=household_id,
            description=proposal.get("description") or "",
            amount=proposal.get("amount"),
            kind="expense",
            rules=self._category_rules_for(household_id),
            categories=self._ai_categories(household_id),
            history=self._description_category_history(household_id),
        )
        return [
            {
                "category_id": item.category_id,
                "category_name": item.category_name,
                "reason": item.reason,
                "rank": item.rank,
                "confidence": item.confidence,
            }
            for item in provider.suggest_category(context)
        ]

    def update_capture_proposal(
        self,
        capture_id: str,
        *,
        date: str | None = None,
        amount: int | None = None,
        description: str | None = None,
        category_id: str | None = None,
    ) -> Capture:
        """CF4-05: corrige la propuesta de una captura antes de confirmar."""
        capture = self._required("capture", capture_id)
        if capture.status not in ("pending", "needs_input"):
            raise DomainRuleError("La captura ya fue procesada")
        payload = dict(capture.payload or {})
        proposal = dict(payload.get("proposal") or {})
        if date is not None:
            proposal["date"] = date
        if amount is not None:
            proposal["amount"] = amount
        if description is not None:
            proposal["description"] = (description or "").strip()
        if category_id is not None:
            self._required("category", category_id)
            proposal["category_id"] = category_id
        payload["proposal"] = proposal
        payload["proposal_updated_at"] = utc_now().isoformat()
        capture.payload = payload
        capture.status = "pending"
        self.session.commit()
        self.session.refresh(capture)
        return capture

    def confirm_capture(
        self,
        capture_id: str,
        *,
        account_id: str,
        amount: int | None = None,
        capture_date: str | None = None,
        description: str | None = None,
        category_id: str | None = None,
    ) -> Capture:
        """CF4-05: confirma la captura y persiste el movimiento (gasto).

        La confirmación es humana: sin ella ninguna captura crea transacciones.
        """
        capture = self._required("capture", capture_id)
        if capture.status in ("confirmed", "rejected", "discarded"):
            raise DomainRuleError("La captura ya fue procesada")
        payload = dict(capture.payload or {})
        proposal = dict(payload.get("proposal") or {})
        final_amount = amount if amount is not None else proposal.get("amount")
        if not final_amount or int(final_amount) <= 0:
            raise DomainRuleError("La captura no tiene monto; corríjala antes de confirmar")
        transaction_date = capture_date or proposal.get("date") or date.today().isoformat()
        final_description = description or proposal.get("description")
        final_category = category_id or proposal.get("category_id")

        transaction = self.create_transaction(
            account_id=account_id,
            to_account_id=None,
            category_id=final_category,
            recorded_by=None,
            type="expense",
            amount=int(final_amount),
            date=date.fromisoformat(transaction_date),
            description=final_description,
        )
        capture.status = "confirmed"
        capture.confirmed_transaction_id = transaction.id
        capture.resolved_by = "manual"
        capture.resolved_at = utc_now()
        self.session.commit()
        self.session.refresh(capture)
        return capture

    # ---- Avisos programados (Fase 4, CF4-07/CF4-08) ----

    def get_notification_preferences(self, household_id: str) -> list[NotificationPreference]:
        """Preferencias con defaults: lo no configurado cuenta como habilitado."""
        self._required("household", household_id)
        rows = list(
            self.session.scalars(
                select(NotificationPreference).where(
                    NotificationPreference.household_id == household_id
                )
            )
        )
        by_kind = {row.template_kind: row for row in rows}
        merged = []
        for kind in NOTIFICATION_KINDS:
            row = by_kind.get(kind)
            if row is None:
                merged.append(
                    NotificationPreference(
                        id=f"default:{kind}",
                        household_id=household_id,
                        template_kind=kind,
                        enabled=True,
                    )
                )
            else:
                merged.append(row)
        return merged

    def set_notification_preference(
        self, household_id: str, *, template_kind: str, enabled: bool
    ) -> list[NotificationPreference]:
        self._required("household", household_id)
        if template_kind not in NOTIFICATION_KINDS:
            raise DomainRuleError("Plantilla de aviso desconocida")
        preference = self.session.scalar(
            select(NotificationPreference).where(
                NotificationPreference.household_id == household_id,
                NotificationPreference.template_kind == template_kind,
            )
        )
        if preference is None:
            preference = NotificationPreference(
                id=uuid4().hex,
                household_id=household_id,
                template_kind=template_kind,
                enabled=enabled,
            )
            self.session.add(preference)
        else:
            preference.enabled = enabled
        self.session.commit()
        return self.get_notification_preferences(household_id)

    def list_notifications(
        self, household_id: str, *, status: str | None = None, limit: int = 100
    ) -> list[Notification]:
        self._required("household", household_id)
        statement = select(Notification).where(Notification.household_id == household_id)
        if status:
            statement = statement.where(Notification.status == status)
        statement = statement.order_by(Notification.due_date.desc(), Notification.created_at.desc())
        return list(self.session.scalars(statement.limit(limit)))

    def list_notification_sends(
        self, household_id: str, *, limit: int = 100
    ) -> list[NotificationSend]:
        self._required("household", household_id)
        statement = (
            select(NotificationSend)
            .join(Notification, NotificationSend.notification_id == Notification.id)
            .where(Notification.household_id == household_id)
            .order_by(NotificationSend.sent_at.desc(), NotificationSend.id)
        )
        return list(self.session.scalars(statement.limit(limit)))

    # ---- Audit (CF1-20, lectura) ----

    def list_audit(
        self,
        *,
        entity_kind: str | None = None,
        entity_id: str | None = None,
        action: str | None = None,
        actor: str | None = None,
        limit: int = 200,
    ) -> list[AuditEvent]:
        statement = select(AuditEvent).order_by(AuditEvent.occurred_at.desc(), AuditEvent.id)
        if entity_kind:
            statement = statement.where(AuditEvent.entity_kind == entity_kind)
        if entity_id:
            statement = statement.where(AuditEvent.entity_id == entity_id)
        if action:
            statement = statement.where(AuditEvent.action == action)
        if actor:
            statement = statement.where(AuditEvent.actor == actor)
        return list(self.session.scalars(statement.limit(limit)))

    # ---- Generic helpers ----

    def _required(self, kind: str, entity_id: str):
        model = self._kind_model(kind)
        entity = self.session.get(model, entity_id)
        if entity is None:
            raise KeyError(entity_id)
        return entity

    @staticmethod
    def _kind_model(kind: str):
        mapping = {
            "household": Household,
            "member": HouseholdMember,
            "institution": FinancialInstitution,
            "account": FinancialAccount,
            "category": Category,
            "income_source": IncomeSource,
            "transaction": Transaction,
            "debt": Debt,
            "debt_payment": DebtPayment,
            "installment": Installment,
            "budget": Budget,
            "budget_category": BudgetCategory,
            "payment_plan": PaymentPlan,
            "projection_scenario": ProjectionScenario,
            "import_batch": ImportBatch,
            "import_review": ImportReview,
            "import_category_rule": ImportCategoryRule,
            "ai_proposal": AiProposal,
            "capture": Capture,
            "notification_preference": NotificationPreference,
            "notification": Notification,
            "notification_send": NotificationSend,
            "goal": FinancialGoal,
        }
        model = mapping.get(kind)
        if model is None:
            raise DomainRuleError(f"Tipo de entidad desconocido: {kind}")
        return model
