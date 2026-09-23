from __future__ import annotations

from datetime import UTC, date, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utc_now() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class Household(TimestampMixin, Base):
    __tablename__ = "households"
    __table_args__ = (CheckConstraint("status IN ('active','paused','archived')"),)

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(20), default="active")
    timezone: Mapped[str] = mapped_column(String(80))


class HouseholdMember(TimestampMixin, Base):
    __tablename__ = "household_members"
    __table_args__ = (
        CheckConstraint("role IN ('admin','member')"),
        CheckConstraint("status IN ('active','inactive')"),
    )

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    household_id: Mapped[str] = mapped_column(
        ForeignKey("households.id", ondelete="RESTRICT"), index=True
    )
    name: Mapped[str] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(20), default="member")
    status: Mapped[str] = mapped_column(String(20), default="active")


class FinancialInstitution(TimestampMixin, Base):
    __tablename__ = "financial_institutions"
    __table_args__ = (
        CheckConstraint("type IN ('bank','fintech','store','other')"),
        CheckConstraint("status IN ('active','inactive')"),
    )

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True)
    type: Mapped[str] = mapped_column(String(20), default="other")
    status: Mapped[str] = mapped_column(String(20), default="active")


class FinancialAccount(TimestampMixin, Base):
    __tablename__ = "financial_accounts"
    __table_args__ = (
        CheckConstraint("type IN ('checking','savings','credit_card','cash','wallet','loan_line')"),
        CheckConstraint("currency = 'CLP'"),
        CheckConstraint("original_amount IS NULL OR original_amount >= 0"),
        CheckConstraint("credit_limit IS NULL OR credit_limit >= 0"),
        CheckConstraint(
            "statement_day IS NULL OR statement_day BETWEEN 1 AND 31",
            name="ck_account_statement_day",
        ),
        CheckConstraint(
            "due_day IS NULL OR due_day BETWEEN 1 AND 31",
            name="ck_account_due_day",
        ),
        CheckConstraint("status IN ('active','paused','closed')"),
    )

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    household_id: Mapped[str] = mapped_column(
        ForeignKey("households.id", ondelete="RESTRICT"), index=True
    )
    institution_id: Mapped[str | None] = mapped_column(
        ForeignKey("financial_institutions.id", ondelete="SET NULL"), index=True
    )
    name: Mapped[str] = mapped_column(String(200))
    type: Mapped[str] = mapped_column(String(20), default="checking")
    currency: Mapped[str] = mapped_column(String(3), default="CLP")
    balance_reported: Mapped[int] = mapped_column(Integer, default=0)
    balance_calculated: Mapped[int] = mapped_column(Integer, default=0)
    original_amount: Mapped[int | None] = mapped_column(Integer)
    credit_limit: Mapped[int | None] = mapped_column(Integer)
    statement_day: Mapped[int | None] = mapped_column(Integer)
    due_day: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="active")


class Category(TimestampMixin, Base):
    __tablename__ = "categories"
    __table_args__ = (
        CheckConstraint("kind IN ('expense','income','transfer')", name="ck_category_kind"),
        CheckConstraint("status IN ('active','inactive')", name="ck_category_status"),
        UniqueConstraint("household_id", "name", "kind", name="uq_category_household_name_kind"),
    )

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    household_id: Mapped[str] = mapped_column(
        ForeignKey("households.id", ondelete="RESTRICT"), index=True
    )
    name: Mapped[str] = mapped_column(String(120))
    kind: Mapped[str] = mapped_column(String(20), default="expense")
    status: Mapped[str] = mapped_column(String(20), default="active")


class IncomeSource(TimestampMixin, Base):
    __tablename__ = "income_sources"
    __table_args__ = (
        CheckConstraint(
            "expected_amount >= 0", name="ck_income_source_expected_amount_nonnegative"
        ),
        CheckConstraint("status IN ('active','inactive')", name="ck_income_source_status"),
        UniqueConstraint("household_id", "name", name="uq_income_source_household_name"),
    )

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    household_id: Mapped[str] = mapped_column(
        ForeignKey("households.id", ondelete="RESTRICT"), index=True
    )
    member_id: Mapped[str | None] = mapped_column(
        ForeignKey("household_members.id", ondelete="SET NULL"), index=True
    )
    name: Mapped[str] = mapped_column(String(120))
    type: Mapped[str] = mapped_column(String(30), default="salary")
    expected_amount: Mapped[int] = mapped_column(Integer, default=0)
    frequency: Mapped[str] = mapped_column(String(20), default="monthly")
    status: Mapped[str] = mapped_column(String(20), default="active")


class Transaction(TimestampMixin, Base):
    __tablename__ = "transactions"
    __table_args__ = (
        CheckConstraint("amount <> 0", name="ck_transaction_amount_nonzero"),
        CheckConstraint(
            "type IN ('expense','income','transfer','payment','adjustment')",
            name="ck_transaction_type",
        ),
        CheckConstraint(
            "type <> 'transfer' OR to_account_id IS NOT NULL", name="ck_transfer_destination"
        ),
        CheckConstraint(
            "type = 'transfer' OR to_account_id IS NULL", name="ck_transfer_source_only"
        ),
        CheckConstraint("status IN ('posted','voided')", name="ck_transaction_status"),
        Index(
            "uq_transactions_external",
            "account_id",
            "external_id",
            "external_source",
            unique=True,
            sqlite_where=text("external_id IS NOT NULL"),
        ),
    )

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    account_id: Mapped[str] = mapped_column(
        ForeignKey("financial_accounts.id", ondelete="RESTRICT"), index=True
    )
    to_account_id: Mapped[str | None] = mapped_column(
        ForeignKey("financial_accounts.id", ondelete="RESTRICT"), index=True
    )
    category_id: Mapped[str | None] = mapped_column(
        ForeignKey("categories.id", ondelete="SET NULL"), index=True
    )
    recorded_by: Mapped[str | None] = mapped_column(
        ForeignKey("household_members.id", ondelete="SET NULL"), index=True
    )
    import_batch_id: Mapped[str | None] = mapped_column(
        ForeignKey("import_batches.id", ondelete="SET NULL"), index=True
    )
    type: Mapped[str] = mapped_column(String(20))
    amount: Mapped[int] = mapped_column(Integer)
    date: Mapped[date] = mapped_column(Date, index=True)
    description: Mapped[str | None] = mapped_column(String(500))
    external_id: Mapped[str | None] = mapped_column(String(120), index=True)
    external_source: Mapped[str | None] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(20), default="posted")


class Debt(TimestampMixin, Base):
    __tablename__ = "debts"
    __table_args__ = (
        CheckConstraint(
            "type IN ('credit_card','loan','auto','mortgage','line','other')",
            name="ck_debt_type",
        ),
        CheckConstraint("original_amount >= 0", name="ck_debt_original_amount_nonnegative"),
        CheckConstraint("current_balance >= 0", name="ck_debt_current_balance_nonnegative"),
        CheckConstraint("minimum_payment >= 0", name="ck_debt_minimum_payment_nonnegative"),
        CheckConstraint("interest_rate >= 0", name="ck_debt_interest_rate_nonnegative"),
        CheckConstraint("due_day BETWEEN 1 AND 31", name="ck_debt_due_day"),
        CheckConstraint("status IN ('active','paid_off','closed')", name="ck_debt_status"),
    )

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    household_id: Mapped[str] = mapped_column(
        ForeignKey("households.id", ondelete="RESTRICT"), index=True
    )
    account_id: Mapped[str | None] = mapped_column(
        ForeignKey("financial_accounts.id", ondelete="SET NULL"), index=True
    )
    name: Mapped[str] = mapped_column(String(200))
    type: Mapped[str] = mapped_column(String(30))
    original_amount: Mapped[int] = mapped_column(Integer)
    current_balance: Mapped[int] = mapped_column(Integer)
    interest_rate: Mapped[float] = mapped_column(Float, default=0.0)
    minimum_payment: Mapped[int] = mapped_column(Integer, default=0)
    due_day: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(20), default="active")


class DebtPayment(TimestampMixin, Base):
    __tablename__ = "debt_payments"
    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_debt_payment_amount_positive"),
        CheckConstraint("type IN ('ordinary','extraordinary')", name="ck_debt_payment_type"),
    )

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    debt_id: Mapped[str] = mapped_column(ForeignKey("debts.id", ondelete="RESTRICT"), index=True)
    account_id: Mapped[str | None] = mapped_column(
        ForeignKey("financial_accounts.id", ondelete="SET NULL"), index=True
    )
    transaction_id: Mapped[str | None] = mapped_column(
        ForeignKey("transactions.id", ondelete="SET NULL"), index=True
    )
    recorded_by: Mapped[str | None] = mapped_column(
        ForeignKey("household_members.id", ondelete="SET NULL"), index=True
    )
    amount: Mapped[int] = mapped_column(Integer)
    type: Mapped[str] = mapped_column(String(20))
    payment_date: Mapped[date] = mapped_column(Date, index=True)


class Installment(TimestampMixin, Base):
    __tablename__ = "installments"
    __table_args__ = (
        CheckConstraint("principal_amount >= 0", name="ck_installment_principal_nonnegative"),
        CheckConstraint("interest_amount >= 0", name="ck_installment_interest_nonnegative"),
        CheckConstraint("fee_amount >= 0", name="ck_installment_fee_nonnegative"),
        CheckConstraint(
            "total_amount = principal_amount + interest_amount + fee_amount",
            name="ck_installment_total",
        ),
        CheckConstraint("status IN ('pending','paid','overdue')", name="ck_installment_status"),
    )

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    debt_id: Mapped[str] = mapped_column(ForeignKey("debts.id", ondelete="RESTRICT"), index=True)
    due_date: Mapped[date] = mapped_column(Date, index=True)
    principal_amount: Mapped[int] = mapped_column(Integer, default=0)
    interest_amount: Mapped[int] = mapped_column(Integer, default=0)
    fee_amount: Mapped[int] = mapped_column(Integer, default=0)
    total_amount: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="pending")


class Budget(TimestampMixin, Base):
    __tablename__ = "budgets"
    __table_args__ = (
        CheckConstraint("year BETWEEN 2000 AND 2100", name="ck_budget_year"),
        CheckConstraint("month BETWEEN 1 AND 12", name="ck_budget_month"),
        CheckConstraint("status IN ('draft','active','closed')", name="ck_budget_status"),
        UniqueConstraint("household_id", "year", "month", name="uq_budget_household_period"),
    )

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    household_id: Mapped[str] = mapped_column(
        ForeignKey("households.id", ondelete="RESTRICT"), index=True
    )
    year: Mapped[int] = mapped_column(Integer)
    month: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="draft")


class BudgetCategory(TimestampMixin, Base):
    __tablename__ = "budget_categories"
    __table_args__ = (
        CheckConstraint("planned_amount >= 0", name="ck_budget_category_planned_nonnegative"),
        CheckConstraint("actual_amount >= 0", name="ck_budget_category_actual_nonnegative"),
        UniqueConstraint("budget_id", "category_id", name="uq_budget_category"),
    )

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    budget_id: Mapped[str] = mapped_column(ForeignKey("budgets.id", ondelete="CASCADE"), index=True)
    category_id: Mapped[str] = mapped_column(
        ForeignKey("categories.id", ondelete="RESTRICT"), index=True
    )
    planned_amount: Mapped[int] = mapped_column(Integer, default=0)
    actual_amount: Mapped[int] = mapped_column(Integer, default=0)


class PaymentPlan(TimestampMixin, Base):
    __tablename__ = "payment_plans"
    __table_args__ = (
        CheckConstraint("strategy IN ('snowball','avalanche')", name="ck_payment_plan_strategy"),
        CheckConstraint("status IN ('draft','selected','archived')", name="ck_payment_plan_status"),
    )

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    household_id: Mapped[str] = mapped_column(
        ForeignKey("households.id", ondelete="RESTRICT"), index=True
    )
    strategy: Mapped[str] = mapped_column(String(20))
    name: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(20), default="draft")


class ProjectionScenario(TimestampMixin, Base):
    __tablename__ = "projection_scenarios"
    __table_args__ = (
        CheckConstraint("monthly_payment >= 0", name="ck_projection_monthly_payment_nonnegative"),
    )

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    plan_id: Mapped[str] = mapped_column(
        ForeignKey("payment_plans.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(200))
    monthly_payment: Mapped[int] = mapped_column(Integer, default=0)
    extra_income: Mapped[list | dict | None] = mapped_column(JSON)
    assumptions: Mapped[list | dict | None] = mapped_column(JSON)
    result_summary: Mapped[list | dict | None] = mapped_column(JSON)


class ImportBatch(TimestampMixin, Base):
    __tablename__ = "import_batches"
    __table_args__ = (
        CheckConstraint("source_kind IN ('csv','excel','pdf')", name="ck_import_batch_source_kind"),
        CheckConstraint(
            "status IN ('parsed','validated','confirmed','cancelled')",
            name="ck_import_batch_status",
        ),
        CheckConstraint("total_rows >= 0", name="ck_import_batch_total_rows_nonnegative"),
        CheckConstraint("valid_rows >= 0", name="ck_import_batch_valid_rows_nonnegative"),
        CheckConstraint("invalid_rows >= 0", name="ck_import_batch_invalid_rows_nonnegative"),
    )

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    household_id: Mapped[str] = mapped_column(
        ForeignKey("households.id", ondelete="RESTRICT"), index=True
    )
    account_id: Mapped[str] = mapped_column(
        ForeignKey("financial_accounts.id", ondelete="RESTRICT"), index=True
    )
    source_filename: Mapped[str] = mapped_column(String(255))
    source_kind: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), default="parsed")
    column_mapping: Mapped[dict] = mapped_column(JSON)
    header_row: Mapped[int] = mapped_column(Integer, default=1)
    separator: Mapped[str | None] = mapped_column(String(4))
    total_rows: Mapped[int] = mapped_column(Integer, default=0)
    valid_rows: Mapped[int] = mapped_column(Integer, default=0)
    invalid_rows: Mapped[int] = mapped_column(Integer, default=0)
    rows: Mapped[list] = mapped_column(JSON)
    statement_meta: Mapped[list | dict | None] = mapped_column(JSON, default=None)
    confirm_summary: Mapped[list | dict | None] = mapped_column(JSON, default=None)


class ImportReview(TimestampMixin, Base):
    __tablename__ = "import_reviews"
    __table_args__ = (
        CheckConstraint("kind IN ('invalid','duplicate')", name="ck_import_review_kind"),
        CheckConstraint(
            "status IN ('pending','resolved','discarded')", name="ck_import_review_status"
        ),
    )

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    batch_id: Mapped[str] = mapped_column(
        ForeignKey("import_batches.id", ondelete="CASCADE"), index=True
    )
    household_id: Mapped[str] = mapped_column(
        ForeignKey("households.id", ondelete="RESTRICT"), index=True
    )
    account_id: Mapped[str] = mapped_column(
        ForeignKey("financial_accounts.id", ondelete="RESTRICT"), index=True
    )
    source_filename: Mapped[str] = mapped_column(String(255))
    row_number: Mapped[int] = mapped_column(Integer)
    values: Mapped[dict] = mapped_column(JSON)
    kind: Mapped[str] = mapped_column(String(20))
    reason: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(20), default="pending")
    transaction_id: Mapped[str | None] = mapped_column(
        ForeignKey("transactions.id", ondelete="SET NULL"), index=True
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ImportCategoryRule(TimestampMixin, Base):
    __tablename__ = "import_category_rules"
    __table_args__ = (CheckConstraint("enabled IN (0,1)", name="ck_import_category_rule_enabled"),)

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    household_id: Mapped[str] = mapped_column(
        ForeignKey("households.id", ondelete="RESTRICT"), index=True
    )
    column: Mapped[str] = mapped_column(String(80))
    pattern: Mapped[str] = mapped_column(String(200))
    category_id: Mapped[str] = mapped_column(
        ForeignKey("categories.id", ondelete="RESTRICT"), index=True
    )
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class AiProposal(TimestampMixin, Base):
    """Propuesta del asistente: siempre nace pendiente, nunca se aplica sola (CF3-03/05)."""

    __tablename__ = "ai_proposals"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('category_suggestion','insight','anomaly','budget_adjust')",
            name="ck_ai_proposal_kind",
        ),
        CheckConstraint(
            "status IN ('pending','applied','dismissed')", name="ck_ai_proposal_status"
        ),
    )

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    household_id: Mapped[str] = mapped_column(
        ForeignKey("households.id", ondelete="RESTRICT"), index=True
    )
    kind: Mapped[str] = mapped_column(String(40))
    payload: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AuditEvent(TimestampMixin, Base):
    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    entity_kind: Mapped[str] = mapped_column(String(80), index=True)
    entity_id: Mapped[str] = mapped_column(String(80), index=True)
    action: Mapped[str] = mapped_column(String(20))
    actor: Mapped[str | None] = mapped_column(String(120))
    changes: Mapped[list | dict | None] = mapped_column(JSON)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, index=True
    )


class Capture(TimestampMixin, Base):
    """Captura de WhatsApp/canal (Fase 4, CF4-02): llega pendiente y solo la
    confirma una persona. Nunca genera movimientos por sí sola."""

    __tablename__ = "captures"
    __table_args__ = (
        CheckConstraint("kind IN ('text','audio','image')", name="ck_capture_kind"),
        CheckConstraint(
            "status IN ('pending','needs_input','confirmed','rejected','discarded')",
            name="ck_capture_status",
        ),
    )

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    household_id: Mapped[str] = mapped_column(
        ForeignKey("households.id", ondelete="RESTRICT"), index=True
    )
    channel: Mapped[str] = mapped_column(String(40))
    kind: Mapped[str] = mapped_column(String(20))
    raw_text: Mapped[str | None] = mapped_column(String(2000))
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    confirmed_transaction_id: Mapped[str | None] = mapped_column(
        ForeignKey("transactions.id", ondelete="SET NULL")
    )
    resolved_by: Mapped[str | None] = mapped_column(String(120))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


NOTIFICATION_KINDS = (
    "upcoming_payment",
    "weekly_summary",
    "budget_deviation",
    "monthly_close",
)

_NOTIFICATION_KINDS_SQL = (
    "template_kind IN ('upcoming_payment','weekly_summary','budget_deviation','monthly_close')"
)


class NotificationPreference(TimestampMixin, Base):
    """Preferencia por hogar: qué plantillas de aviso están habilitadas (CF4-07/08)."""

    __tablename__ = "notification_preferences"
    __table_args__ = (
        CheckConstraint(_NOTIFICATION_KINDS_SQL, name="ck_notification_preference_kind"),
        CheckConstraint("enabled IN (0,1)", name="ck_notification_preference_enabled"),
        UniqueConstraint("household_id", "template_kind", name="uq_notification_preference"),
    )

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    household_id: Mapped[str] = mapped_column(
        ForeignKey("households.id", ondelete="RESTRICT"), index=True
    )
    template_kind: Mapped[str] = mapped_column(String(40))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class Notification(TimestampMixin, Base):
    """Cola de salida programada (CF4-07): se agenda por fecha y se renderiza con
    la plantilla del dominio. Sólo se envía por el proveedor configurado y cada
    envío real queda auditado en :class:`NotificationSend`."""

    __tablename__ = "notifications"
    __table_args__ = (
        CheckConstraint(_NOTIFICATION_KINDS_SQL, name="ck_notification_kind"),
        CheckConstraint("status IN ('pending','sent','failed')", name="ck_notification_status"),
        CheckConstraint("attempts >= 0", name="ck_notification_attempts_nonnegative"),
        UniqueConstraint(
            "household_id", "template_kind", "external_ref", name="uq_notification_ref"
        ),
    )

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    household_id: Mapped[str] = mapped_column(
        ForeignKey("households.id", ondelete="RESTRICT"), index=True
    )
    template_kind: Mapped[str] = mapped_column(String(40))
    recipient: Mapped[str] = mapped_column(String(120))
    external_ref: Mapped[str] = mapped_column(String(120), default="")
    due_date: Mapped[date] = mapped_column(Date, index=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(String(2000))
    status: Mapped[str] = mapped_column(String(20), default="pending")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    send_provider: Mapped[str] = mapped_column(String(40), default="")
    message_id: Mapped[str] = mapped_column(String(120), default="")
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class NotificationSend(TimestampMixin, Base):
    """Registro auditable de un envío real a través de un proveedor (CF4-07)."""

    __tablename__ = "notification_sends"
    __table_args__ = (CheckConstraint("provider != ''", name="ck_notification_send_provider"),)

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    notification_id: Mapped[str | None] = mapped_column(
        ForeignKey("notifications.id", ondelete="SET NULL"), index=True
    )
    provider: Mapped[str] = mapped_column(String(40))
    message_id: Mapped[str] = mapped_column(String(120))
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(String(2000))
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class FinancialGoal(TimestampMixin, Base):
    """Meta de ahorro del hogar (Fase UI-6). El avance se calcula desde el
    saldo sumado de las cuentas vinculadas; si no hay cuentas vinculadas,
    se usa el aporte mensual como avance acumulado (progreso aproximado).
    ``current_amount`` lo mantiene el servicio al aplicar un aporte."""

    __tablename__ = "financial_goals"
    __table_args__ = (
        CheckConstraint("target_amount > 0", name="ck_financial_goal_target_positive"),
        CheckConstraint("current_amount >= 0", name="ck_financial_goal_current_nonnegative"),
        CheckConstraint(
            "monthly_contribution >= 0",
            name="ck_financial_goal_contribution_nonnegative",
        ),
        CheckConstraint(
            "status IN ('active','achieved','archived')",
            name="ck_financial_goal_status",
        ),
        CheckConstraint(
            "category IN ('fondo','security','travel','purchase','debt','other')",
            name="ck_financial_goal_category",
        ),
    )

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    household_id: Mapped[str] = mapped_column(
        ForeignKey("households.id", ondelete="RESTRICT"), index=True
    )
    name: Mapped[str] = mapped_column(String(200))
    category: Mapped[str] = mapped_column(String(40), default="fondo")
    target_amount: Mapped[int] = mapped_column(Integer)
    current_amount: Mapped[int] = mapped_column(Integer, default=0)
    monthly_contribution: Mapped[int] = mapped_column(Integer, default=0)
    target_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20), default="active")


MODEL_BY_KIND = {
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
    "audit_event": AuditEvent,
    "goal": FinancialGoal,
}
