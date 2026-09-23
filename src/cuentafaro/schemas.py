from __future__ import annotations

import datetime as dt
from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ApiModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class HouseholdCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    timezone: str = Field(default="America/Santiago", min_length=1, max_length=80)
    status: str = Field(default="active")


class HouseholdUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    timezone: str | None = Field(default=None, min_length=1, max_length=80)
    status: str | None = None


class HouseholdView(ApiModel):
    id: str
    name: str
    status: str
    timezone: str
    created_at: datetime
    updated_at: datetime


class MemberCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    role: str = Field(default="member")
    status: str = Field(default="active")


class MemberUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    role: str | None = None
    status: str | None = None


class MemberView(ApiModel):
    id: str
    household_id: str
    name: str
    role: str
    status: str
    created_at: datetime
    updated_at: datetime


class InstitutionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    type: str = Field(default="other")
    status: str = Field(default="active")


class InstitutionUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    type: str | None = None
    status: str | None = None


class InstitutionView(ApiModel):
    id: str
    name: str
    type: str
    status: str
    created_at: datetime
    updated_at: datetime


class AccountCreate(BaseModel):
    household_id: str = Field(min_length=1, max_length=80)
    institution_id: str | None = Field(default=None, min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=200)
    type: str = Field(default="checking")
    currency: str = Field(default="CLP")
    balance_reported: int = Field(default=0)
    balance_calculated: int = Field(default=0)
    original_amount: int | None = Field(default=None, ge=0)
    credit_limit: int | None = Field(default=None, ge=0)
    statement_day: int | None = Field(default=None, ge=1, le=31)
    due_day: int | None = Field(default=None, ge=1, le=31)
    status: str = Field(default="active")


class AccountUpdate(BaseModel):
    institution_id: str | None = Field(default=None, min_length=1, max_length=80)
    name: str | None = Field(default=None, min_length=1, max_length=200)
    type: str | None = None
    balance_reported: int | None = Field(default=None)
    credit_limit: int | None = Field(default=None, ge=0)
    statement_day: int | None = Field(default=None, ge=1, le=31)
    due_day: int | None = Field(default=None, ge=1, le=31)
    status: str | None = None


class AccountView(ApiModel):
    id: str
    household_id: str
    institution_id: str | None
    institution_name: str | None = None
    name: str
    type: str
    currency: str
    balance_reported: int
    balance_calculated: int
    original_amount: int | None
    credit_limit: int | None = None
    statement_day: int | None = None
    due_day: int | None = None
    status: str
    created_at: datetime
    updated_at: datetime


class CategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    kind: Literal["expense", "income", "transfer"] = "expense"
    status: Literal["active", "inactive"] = "active"


class CategoryUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    kind: Literal["expense", "income", "transfer"] | None = None
    status: Literal["active", "inactive"] | None = None


class CategoryView(ApiModel):
    id: str
    household_id: str
    name: str
    kind: str
    status: str
    created_at: datetime
    updated_at: datetime


class IncomeSourceCreate(BaseModel):
    member_id: str | None = Field(default=None, min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=120)
    type: str = Field(default="salary", max_length=30)
    expected_amount: int = Field(default=0, ge=0)
    frequency: str = Field(default="monthly", max_length=20)
    status: Literal["active", "inactive"] = "active"


class IncomeSourceUpdate(BaseModel):
    member_id: str | None = Field(default=None, min_length=1, max_length=80)
    name: str | None = Field(default=None, min_length=1, max_length=120)
    type: str | None = Field(default=None, max_length=30)
    expected_amount: int | None = Field(default=None, ge=0)
    frequency: str | None = Field(default=None, max_length=20)
    status: Literal["active", "inactive"] | None = None


class IncomeSourceView(ApiModel):
    id: str
    household_id: str
    member_id: str | None
    name: str
    type: str
    expected_amount: int
    frequency: str
    status: str
    created_at: datetime
    updated_at: datetime


class GoalCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    category: Literal["fondo", "security", "travel", "purchase", "debt", "other"] = "fondo"
    target_amount: int = Field(gt=0)
    current_amount: int = Field(default=0, ge=0)
    monthly_contribution: int = Field(default=0, ge=0)
    target_date: date | None = None
    status: Literal["active", "achieved", "archived"] = "active"


class GoalUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    category: Literal["fondo", "security", "travel", "purchase", "debt", "other"] | None = None
    target_amount: int | None = Field(default=None, gt=0)
    current_amount: int | None = Field(default=None, ge=0)
    monthly_contribution: int | None = Field(default=None, ge=0)
    target_date: date | None = None
    status: Literal["active", "achieved", "archived"] | None = None


class GoalContribute(BaseModel):
    amount: int = Field(gt=0)
    account_id: str | None = Field(default=None, min_length=1, max_length=80)
    description: str | None = Field(default=None, max_length=500)
    date: dt.date | None = None


class GoalView(ApiModel):
    id: str
    household_id: str
    name: str
    category: str
    target_amount: int
    current_amount: int
    monthly_contribution: int
    target_date: date | None
    status: str
    created_at: datetime
    updated_at: datetime


class TransactionCreate(BaseModel):
    account_id: str = Field(min_length=1, max_length=80)
    to_account_id: str | None = Field(default=None, min_length=1, max_length=80)
    category_id: str | None = Field(default=None, min_length=1, max_length=80)
    recorded_by: str | None = Field(default=None, min_length=1, max_length=80)
    type: Literal["expense", "income", "transfer", "payment", "adjustment"]
    amount: int
    date: date
    description: str | None = Field(default=None, max_length=500)


class TransactionUpdate(BaseModel):
    account_id: str | None = Field(default=None, min_length=1, max_length=80)
    to_account_id: str | None = Field(default=None, min_length=1, max_length=80)
    category_id: str | None = Field(default=None, min_length=1, max_length=80)
    type: Literal["expense", "income", "transfer", "payment", "adjustment"] | None = None
    amount: int | None = None
    date: dt.date | None = None
    description: str | None = Field(default=None, max_length=500)


class TransactionView(ApiModel):
    id: str
    account_id: str
    to_account_id: str | None
    category_id: str | None
    recorded_by: str | None
    import_batch_id: str | None
    type: str
    amount: int
    date: date
    description: str | None
    external_id: str | None
    external_source: str | None
    status: str
    created_at: datetime
    updated_at: datetime


class DebtCreate(BaseModel):
    account_id: str | None = Field(default=None, min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=200)
    type: Literal["credit_card", "loan", "auto", "mortgage", "line", "other"]
    original_amount: int = Field(ge=0)
    minimum_payment: int = Field(default=0, ge=0)
    interest_rate: float = Field(default=0.0, ge=0)
    due_day: int = Field(default=1, ge=1, le=31)
    status: Literal["active", "paid_off", "closed"] = "active"


class DebtUpdate(BaseModel):
    account_id: str | None = Field(default=None, min_length=1, max_length=80)
    name: str | None = Field(default=None, min_length=1, max_length=200)
    type: Literal["credit_card", "loan", "auto", "mortgage", "line", "other"] | None = None
    current_balance: int | None = Field(default=None, ge=0)
    minimum_payment: int | None = Field(default=None, ge=0)
    interest_rate: float | None = Field(default=None, ge=0)
    due_day: int | None = Field(default=None, ge=1, le=31)
    status: Literal["active", "paid_off", "closed"] | None = None


class DebtView(ApiModel):
    id: str
    household_id: str
    account_id: str | None
    name: str
    type: str
    original_amount: int
    current_balance: int
    interest_rate: float
    minimum_payment: int
    due_day: int
    status: str
    created_at: datetime
    updated_at: datetime


class DebtPaymentCreate(BaseModel):
    account_id: str | None = Field(default=None, min_length=1, max_length=80)
    recorded_by: str | None = Field(default=None, min_length=1, max_length=80)
    amount: int = Field(gt=0)
    type: Literal["ordinary", "extraordinary"] = "ordinary"
    payment_date: date


class DebtPaymentView(ApiModel):
    id: str
    debt_id: str
    account_id: str | None
    transaction_id: str | None
    recorded_by: str | None
    amount: int
    type: str
    payment_date: date
    created_at: datetime
    updated_at: datetime


class InstallmentCreate(BaseModel):
    due_date: date
    principal_amount: int = Field(default=0, ge=0)
    interest_amount: int = Field(default=0, ge=0)
    fee_amount: int = Field(default=0, ge=0)


class InstallmentUpdate(BaseModel):
    status: Literal["pending", "paid", "overdue"] | None = None


class InstallmentView(ApiModel):
    id: str
    debt_id: str
    due_date: date
    principal_amount: int
    interest_amount: int
    fee_amount: int
    total_amount: int
    status: str
    created_at: datetime
    updated_at: datetime


class BudgetCreate(BaseModel):
    year: int = Field(ge=2000, le=2100)
    month: int = Field(ge=1, le=12)
    status: Literal["draft", "active", "closed"] = "draft"


class BudgetUpdate(BaseModel):
    status: Literal["draft", "active", "closed"] | None = None


class BudgetView(ApiModel):
    id: str
    household_id: str
    year: int
    month: int
    status: str
    created_at: datetime
    updated_at: datetime


class BudgetCategorySet(BaseModel):
    category_id: str = Field(min_length=1, max_length=80)
    planned_amount: int = Field(ge=0)


class BudgetCategoryView(ApiModel):
    id: str
    budget_id: str
    category_id: str
    planned_amount: int
    actual_amount: int
    created_at: datetime
    updated_at: datetime


class StrategySimulationRequest(BaseModel):
    strategy: Literal["snowball", "avalanche"]
    monthly_payment: int = Field(gt=0)


class PaymentPlanCreate(BaseModel):
    strategy: Literal["snowball", "avalanche"]
    name: str = Field(min_length=1, max_length=200)


class PaymentPlanUpdate(BaseModel):
    status: Literal["draft", "selected", "archived"] | None = None


class PaymentPlanView(ApiModel):
    id: str
    household_id: str
    strategy: str
    name: str
    status: str
    created_at: datetime
    updated_at: datetime


class ExtraIncome(BaseModel):
    month_offset: int = Field(ge=1)
    amount: int = Field(gt=0)


class ScenarioCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    monthly_payment: int = Field(gt=0)
    extra_income: list[ExtraIncome] = Field(default_factory=list)


class ProjectionScenarioView(ApiModel):
    id: str
    plan_id: str
    name: str
    monthly_payment: int
    extra_income: list[dict] | None
    assumptions: dict[str, Any] | None
    result_summary: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime


class AuditEventView(ApiModel):
    id: str
    entity_kind: str
    entity_id: str
    action: str
    actor: str | None
    changes: dict[str, Any] | None
    occurred_at: datetime


class ImportBatchMapping(BaseModel):
    column_mapping: dict[str, str]
    header_row: int = Field(default=1, ge=1)
    separator: str | None = Field(default=None, max_length=4)


class ImportRowView(BaseModel):
    row: int
    values: dict[str, str | None]
    valid: bool
    errors: list[str]


class ImportBatchView(ApiModel):
    id: str
    household_id: str
    account_id: str
    source_filename: str
    source_kind: str
    status: str
    column_mapping: dict[str, str]
    header_row: int
    separator: str | None
    total_rows: int
    valid_rows: int
    invalid_rows: int
    statement_meta: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime


class ImportBatchDetailView(ImportBatchView):
    rows: list[ImportRowView]


class MovementPreviewRowView(BaseModel):
    row: int
    date: dt.date | None = None
    description: str | None = None
    amount: int | None = None
    balance: int | None = None
    external_id: str | None = None
    kind: Literal["income", "expense"] | None = None
    valid: bool = True
    errors: list[str] = Field(default_factory=list)
    balance_ok: bool | None = None
    duplicate: bool = False
    duplicate_type: Literal["identity", "heuristic"] | None = None
    duplicate_of: str | None = None
    suggested_category_id: str | None = None


class ImportPreviewView(BaseModel):
    id: str
    status: str
    account_type: str | None = None
    statement_meta: dict[str, Any] = Field(default_factory=dict)
    total_rows: int
    valid_rows: int
    invalid_rows: int
    duplicate_rows: int
    reconciliation_mismatches: int
    rows: list[MovementPreviewRowView]


class ImportConfirmResultView(BaseModel):
    id: str
    status: str
    created: int
    queued_for_review: int
    skipped_duplicates: int
    total_rows: int
    card_statement: dict[str, Any] | None = None


class ImportReviewView(ApiModel):
    id: str
    batch_id: str
    household_id: str
    account_id: str
    source_filename: str
    row_number: int
    values: dict[str, str | None]
    kind: Literal["invalid", "duplicate"]
    reason: str | None
    status: str
    transaction_id: str | None
    created_at: datetime
    updated_at: datetime
    resolved_at: datetime | None


class ImportReviewResolve(BaseModel):
    action: Literal["confirm", "correct", "discard"]
    values: dict[str, str | None] | None = None
    category_id: str | None = Field(default=None, min_length=1, max_length=80)


class ImportCategoryRuleCreate(BaseModel):
    column: str = Field(min_length=1, max_length=80)
    pattern: str = Field(min_length=1, max_length=200)
    category_id: str = Field(min_length=1, max_length=80)


class ImportCategoryRuleUpdate(BaseModel):
    column: str | None = Field(default=None, min_length=1, max_length=80)
    pattern: str | None = Field(default=None, min_length=1, max_length=200)
    category_id: str | None = Field(default=None, min_length=1, max_length=80)
    enabled: bool | None = None


class ImportCategoryRuleView(ApiModel):
    id: str
    household_id: str
    column: str
    pattern: str
    category_id: str
    enabled: bool
    created_at: datetime
    updated_at: datetime


# ---- Asistente con IA (Fase 3, CF3-01..CF3-08) ----


class AiCategorySuggestionView(BaseModel):
    category_id: str
    category_name: str
    reason: str
    rank: int
    confidence: float


class AiProposalView(ApiModel):
    id: str
    household_id: str
    kind: str
    payload: dict[str, Any]
    status: str
    resolved_at: datetime | None
    created_at: datetime
    updated_at: datetime


class AiSuggestCategoryCreate(BaseModel):
    description: str = Field(min_length=1, max_length=500)
    amount: int | None = Field(default=None, ge=0)


class AiSuggestCategoryResult(BaseModel):
    provider: str
    suggestions: list[AiCategorySuggestionView]
    proposal: AiProposalView


class AiInsightView(BaseModel):
    severity: str
    title: str
    detail: str
    category_id: str | None = None


class AiAnomalyView(BaseModel):
    category_id: str | None
    title: str
    detail: str
    severity: str = "warning"
    budget_id: str | None = None
    suggested_planned_amount: int | None = None


class AiInsightsResult(BaseModel):
    provider: str
    period: str
    insights: list[AiInsightView]
    anomalies: list[AiAnomalyView]


class AiProposalResolve(BaseModel):
    resolution: Literal["applied", "dismissed"]


# ---- Capturas de mensajería (Fase 4, CF4-02/CF4-03) ----


class CaptureCreate(BaseModel):
    kind: Literal["text", "audio", "image"]
    raw_text: str | None = Field(default=None, max_length=2000)
    payload: dict[str, Any] | None = None
    channel: str = Field(default="simulated", max_length=40)


class CaptureProposalUpdate(BaseModel):
    date: dt.date | None = None
    amount: int | None = Field(default=None, gt=0)
    description: str | None = Field(default=None, max_length=200)
    category_id: str | None = None


class CaptureConfirm(BaseModel):
    account_id: str
    amount: int | None = Field(default=None, gt=0)
    date: dt.date | None = None
    description: str | None = Field(default=None, max_length=200)
    category_id: str | None = None


class CaptureView(ApiModel):
    id: str
    household_id: str
    channel: str
    kind: str
    raw_text: str | None
    payload: dict[str, Any]
    status: str
    confirmed_transaction_id: str | None
    resolved_by: str | None
    resolved_at: datetime | None
    created_at: datetime
    updated_at: datetime


class CaptureResolve(BaseModel):
    resolution: Literal["reject", "discard"]


# ---- Avisos programados (Fase 4, CF4-07/CF4-08) ----


class NotificationView(ApiModel):
    id: str
    household_id: str
    template_kind: str
    recipient: str
    due_date: dt.date
    status: str
    attempts: int
    send_provider: str
    message_id: str
    title: str
    body: str
    payload: dict[str, Any]
    sent_at: datetime | None
    created_at: datetime


class NotificationSendView(ApiModel):
    id: str
    notification_id: str | None
    provider: str
    message_id: str
    title: str
    body: str
    sent_at: datetime
    created_at: datetime


class NotificationPreferenceView(ApiModel):
    id: str
    household_id: str
    template_kind: str
    enabled: bool


class NotificationPreferenceUpdate(BaseModel):
    template_kind: Literal[
        "upcoming_payment", "weekly_summary", "budget_deviation", "monthly_close"
    ]
    enabled: bool


class NotificationRunResult(BaseModel):
    household_id: str
    enqueued: int
    sent: int
    failed: int
