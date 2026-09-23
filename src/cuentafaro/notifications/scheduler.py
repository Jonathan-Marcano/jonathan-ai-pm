"""Programador de notificaciones (Fase 4, CF4-07).

Dos fases, ambas por fecha e idempotentes:

1. *Cola de salida*: a partir de los datos del período y de las plantillas del
   dominio se crean los avisos pendientes (``Notification``). Una clave
   ``external_ref`` por hogar+tipo evita duplicados entre ejecuciones.
2. *Ejecución por fecha*: los avisos pendientes ya vencidos se entregan por el
   proveedor configurado (simulado en este tramo) y cada envío queda auditado
   en ``notification_sends``.

Recibe ``today`` inyectable para pruebas: mismo insumo → misma programación.
"""

from __future__ import annotations

from datetime import date
from uuid import uuid4

from sqlalchemy import select

from cuentafaro.messaging import OutboundMessage
from cuentafaro.models import (
    NOTIFICATION_KINDS,
    Debt,
    Household,
    Installment,
    Notification,
    NotificationPreference,
    NotificationSend,
    utc_now,
)
from cuentafaro.notifications.templates import (
    render_budget_deviation,
    render_monthly_close,
    render_upcoming_payment,
    render_weekly_summary,
)
from cuentafaro.services import DomainStore

HORIZON_DAYS = 3  # cuántos días hacia adelante se avisan los pagos por vencer
WEEKLY_SUMMARY_WEEKDAY = 6  # domingo: día del resumen semanal
CLOSE_REQUEST_DAY = 28  # a partir de este día se pide cerrar el mes


def _new_id() -> str:
    return uuid4().hex


def _recipient(household: Household) -> str:
    return household.name or f"hogar-{household.id[:8]}"


def _enabled_kinds(store: DomainStore, household_id: str) -> set[str]:
    rows = list(
        store.session.scalars(
            select(NotificationPreference).where(
                NotificationPreference.household_id == household_id
            )
        )
    )
    set_kinds = {row.template_kind for row in rows}
    defaults = {kind for kind in NOTIFICATION_KINDS if kind not in set_kinds}
    disabled = {row.template_kind for row in rows if not row.enabled}
    return (defaults | set_kinds) - disabled


def _upsert(
    store: DomainStore,
    *,
    household_id: str,
    kind: str,
    recipient: str,
    external_ref: str,
    due_date: date,
    title: str,
    body: str,
    payload: dict,
) -> bool:
    existing = store.session.scalar(
        select(Notification).where(
            Notification.household_id == household_id,
            Notification.template_kind == kind,
            Notification.external_ref == external_ref,
        )
    )
    if existing is not None:
        return False
    store.session.add(
        Notification(
            id=_new_id(),
            household_id=household_id,
            template_kind=kind,
            recipient=recipient,
            external_ref=external_ref,
            due_date=due_date,
            title=title,
            body=body,
            payload=payload,
        )
    )
    return True


def _enqueue_household(store: DomainStore, household_id: str, today: date) -> int:
    kinds = _enabled_kinds(store, household_id)
    household = store._required("household", household_id)
    recipient = _recipient(household)
    created = 0

    if "upcoming_payment" in kinds:
        data = store.upcoming_payments(household_id, days=HORIZON_DAYS, today=today)
        for item in data["pending_installments"]:
            installment = store.session.get(Installment, item["id"])
            debt = store.session.get(Debt, item["debt_id"]) if installment else None
            if installment is None or debt is None:
                continue
            title, body = render_upcoming_payment(
                debt_name=debt.name,
                amount=item["total_amount"],
                due_date=item["due_date"],
                days_left=item["days_left"],
            )
            created += _upsert(
                store,
                household_id=household_id,
                kind="upcoming_payment",
                recipient=recipient,
                external_ref=f"installment:{installment.id}",
                due_date=today,
                title=title,
                body=body,
                payload={
                    "source": "installment",
                    "debt_id": debt.id,
                    "due_date": item["due_date"].isoformat(),
                },
            )
        for item in data["recurring_minimums"]:
            ref = f"recurring:{item['debt_id']}:{item['due_date'].isoformat()}"
            title, body = render_upcoming_payment(
                debt_name=item["debt_name"],
                amount=item["minimum_payment"],
                due_date=item["due_date"],
                days_left=(item["due_date"] - today).days,
            )
            created += _upsert(
                store,
                household_id=household_id,
                kind="upcoming_payment",
                recipient=recipient,
                external_ref=ref,
                due_date=today,
                title=title,
                body=body,
                payload={
                    "source": "recurring",
                    "debt_id": item["debt_id"],
                    "due_date": item["due_date"].isoformat(),
                },
            )

    if "weekly_summary" in kinds and today.weekday() == WEEKLY_SUMMARY_WEEKDAY:
        iso = today.isocalendar()
        week_ref = f"{iso.year}-W{iso.week:02d}"
        summary = store.weekly_summary(household_id, today=today)
        title, body = render_weekly_summary(
            week_start=summary["week_start"],
            week_end=summary["week_end"],
            income=summary["income"],
            expenses=summary["expenses"],
            balance=summary["balance"],
        )
        created += _upsert(
            store,
            household_id=household_id,
            kind="weekly_summary",
            recipient=recipient,
            external_ref=f"period:{week_ref}",
            due_date=today,
            title=title,
            body=body,
            payload={"week": week_ref},
        )

    if "budget_deviation" in kinds:
        dashboard = store.dashboard(household_id, year=today.year, month=today.month)
        rows = [
            row
            for row in dashboard["budget"]
            if row["planned"] > 0 and row["actual"] > row["planned"]
        ]
        if rows:
            title, body = render_budget_deviation(rows)
            created += _upsert(
                store,
                household_id=household_id,
                kind="budget_deviation",
                recipient=recipient,
                external_ref=f"period:{today.year:04d}-{today.month:02d}",
                due_date=today,
                title=title,
                body=body,
                payload={"period": f"{today.year:04d}-{today.month:02d}", "categories": len(rows)},
            )

    if "monthly_close" in kinds and today.day >= CLOSE_REQUEST_DAY:
        dashboard = store.dashboard(household_id, year=today.year, month=today.month)
        budget_total = sum(row["planned"] for row in dashboard["budget"])
        title, body = render_monthly_close(
            period=f"{today.year:04d}-{today.month:02d}",
            expenses=dashboard["expenses"],
            budget_total=budget_total or None,
        )
        created += _upsert(
            store,
            household_id=household_id,
            kind="monthly_close",
            recipient=recipient,
            external_ref=f"period:{today.year:04d}-{today.month:02d}",
            due_date=today,
            title=title,
            body=body,
            payload={"period": f"{today.year:04d}-{today.month:02d}"},
        )

    return created


def _flush_household(
    store: DomainStore, household_id: str, provider, today: date
) -> tuple[int, int]:
    items = list(
        store.session.scalars(
            select(Notification)
            .where(
                Notification.household_id == household_id,
                Notification.status == "pending",
                Notification.due_date <= today,
            )
            .order_by(Notification.due_date, Notification.created_at)
        )
    )
    sent = 0
    failed = 0
    for notification in items:
        notification.attempts += 1
        message = OutboundMessage(
            to=notification.recipient,
            template_kind=notification.template_kind,
            title=notification.title,
            body=notification.body,
            metadata={
                "notification_id": notification.id,
                "due_date": notification.due_date.isoformat(),
            },
        )
        try:
            receipt = provider.send(message)
        except Exception:
            notification.status = "failed"
            failed += 1
            continue
        store.session.add(
            NotificationSend(
                id=_new_id(),
                notification_id=notification.id,
                provider=receipt.provider,
                message_id=receipt.message_id,
                title=notification.title,
                body=notification.body,
            )
        )
        notification.status = "sent"
        notification.send_provider = receipt.provider
        notification.message_id = receipt.message_id
        notification.sent_at = utc_now()
        sent += 1
    return sent, failed


def run_household_notifications(
    session,
    provider,
    household_id: str,
    *,
    today: date | None = None,
) -> dict:
    """Encola lo programado para hoy y entrega lo que ya venció (CF4-07).

    Devuelve conteos para diagnóstico: ``enqueued``, ``sent`` y ``failed``.
    """
    today = today or date.today()
    store = DomainStore(session)
    enqueued = _enqueue_household(store, household_id, today)
    session.flush()
    sent, failed = _flush_household(store, household_id, provider, today)
    session.commit()
    return {
        "household_id": household_id,
        "enqueued": enqueued,
        "sent": sent,
        "failed": failed,
    }
