"""API de importación de estados de cuenta (Fase 2)."""

from __future__ import annotations

import json
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session

from cuentafaro.deps import get_session
from cuentafaro.importing import ImportFormatError, guess_source_kind
from cuentafaro.schemas import (
    ImportBatchDetailView,
    ImportBatchView,
    ImportCategoryRuleCreate,
    ImportCategoryRuleUpdate,
    ImportCategoryRuleView,
    ImportConfirmResultView,
    ImportPreviewView,
    ImportReviewResolve,
    ImportReviewView,
    ImportRowView,
)
from cuentafaro.services import DomainRuleError, DomainStore

router = APIRouter(tags=["imports"])
SessionDependency = Annotated[Session, Depends(get_session)]


def _parse_mapping(raw: str) -> dict[str, str]:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as error:
        raise DomainRuleError("column_mapping debe ser un objeto JSON") from error
    if not isinstance(payload, dict) or not all(
        isinstance(key, str) and isinstance(value, str) for key, value in payload.items()
    ):
        raise DomainRuleError("column_mapping debe ser un objeto de claves y valores de texto")
    return payload


@router.post(
    "/households/{household_id}/import-batches", response_model=ImportBatchView, status_code=201
)
def create_import_batch(
    household_id: str,
    account_id: Annotated[str, Form()],
    column_mapping: Annotated[
        str, Form(description="JSON: {campo del contrato: columna del archivo}")
    ],
    file: Annotated[UploadFile, File()],
    session: SessionDependency,
    header_row: Annotated[int, Form()] = 1,
    separator: Annotated[str, Form()] = "",
    source_kind: Annotated[str, Form()] = "",
) -> dict:
    store = DomainStore(session)
    content = file.file.read()
    if not source_kind:
        try:
            kind = guess_source_kind(file.filename or "")
        except ImportFormatError as error:
            raise DomainRuleError(str(error)) from error
    else:
        kind = source_kind
    batch = store.create_import_batch(
        household_id=household_id,
        account_id=account_id,
        source_filename=file.filename or "archivo",
        source_kind=kind,
        content=content,
        column_mapping=_parse_mapping(column_mapping),
        header_row=header_row,
        separator=separator or None,
    )
    return ImportBatchView.model_validate(batch).model_dump(mode="json")


@router.get("/households/{household_id}/import-batches", response_model=list[ImportBatchView])
def list_import_batches(household_id: str, session: SessionDependency) -> list[dict]:
    store = DomainStore(session)
    batches = store.list_import_batches(household_id)
    return [ImportBatchView.model_validate(batch).model_dump(mode="json") for batch in batches]


@router.get("/import-batches/{batch_id}", response_model=ImportBatchDetailView)
def get_import_batch(batch_id: str, session: SessionDependency) -> dict:
    store = DomainStore(session)
    batch = store.get_import_batch(batch_id)
    view = ImportBatchDetailView(
        **ImportBatchView.model_validate(batch).model_dump(mode="json"),
        rows=[ImportRowView.model_validate(row) for row in batch.rows],
    )
    return view.model_dump(mode="json")


@router.get("/import-batches/{batch_id}/preview", response_model=ImportPreviewView)
def preview_import_batch(batch_id: str, session: SessionDependency) -> dict:
    store = DomainStore(session)
    return store.preview_import_batch(batch_id)


@router.post("/import-batches/{batch_id}/confirm", response_model=ImportConfirmResultView)
def confirm_import_batch(batch_id: str, session: SessionDependency) -> dict:
    store = DomainStore(session)
    batch, summary = store.confirm_import_batch(batch_id)
    return {
        "id": batch.id,
        "status": batch.status,
        **summary,
    }


# ---- Cola de revisión (CF2-10, CF2-11) ----


@router.get("/import-reviews", response_model=list[ImportReviewView])
def list_import_reviews(
    session: SessionDependency,
    household_id: str | None = None,
    account_id: str | None = None,
    status: str | None = None,
) -> list[dict]:
    store = DomainStore(session)
    reviews = store.list_import_reviews(
        household_id=household_id, account_id=account_id, status=status
    )
    return [ImportReviewView.model_validate(r).model_dump(mode="json") for r in reviews]


@router.get("/import-reviews/{review_id}", response_model=ImportReviewView)
def get_import_review(review_id: str, session: SessionDependency) -> dict:
    store = DomainStore(session)
    review = store.get_import_review(review_id)
    return ImportReviewView.model_validate(review).model_dump(mode="json")


@router.post("/import-reviews/{review_id}/resolve", response_model=ImportReviewView)
def resolve_import_review(
    review_id: str, payload: ImportReviewResolve, session: SessionDependency
) -> dict:
    store = DomainStore(session)
    review = store.resolve_import_review(
        review_id,
        action=payload.action,
        values=payload.values,
        category_id=payload.category_id,
    )
    return ImportReviewView.model_validate(review).model_dump(mode="json")


# ---- Reglas de categoría por columna importada (CF2-12) ----


@router.post(
    "/households/{household_id}/import-category-rules",
    response_model=ImportCategoryRuleView,
    status_code=201,
)
def create_import_category_rule(
    household_id: str, payload: ImportCategoryRuleCreate, session: SessionDependency
) -> dict:
    store = DomainStore(session)
    rule = store.create_import_category_rule(
        household_id,
        column=payload.column,
        pattern=payload.pattern,
        category_id=payload.category_id,
    )
    return ImportCategoryRuleView.model_validate(rule).model_dump(mode="json")


@router.get(
    "/households/{household_id}/import-category-rules", response_model=list[ImportCategoryRuleView]
)
def list_import_category_rules(household_id: str, session: SessionDependency) -> list[dict]:
    store = DomainStore(session)
    rules = store.list_import_category_rules(household_id)
    return [ImportCategoryRuleView.model_validate(r).model_dump(mode="json") for r in rules]


@router.patch("/import-category-rules/{rule_id}", response_model=ImportCategoryRuleView)
def update_import_category_rule(
    rule_id: str, payload: ImportCategoryRuleUpdate, session: SessionDependency
) -> dict:
    store = DomainStore(session)
    rule = store.update_import_category_rule(
        rule_id,
        column=payload.column,
        pattern=payload.pattern,
        category_id=payload.category_id,
        enabled=payload.enabled,
    )
    return ImportCategoryRuleView.model_validate(rule).model_dump(mode="json")


@router.delete("/import-category-rules/{rule_id}", status_code=204)
def delete_import_category_rule(rule_id: str, session: SessionDependency) -> None:
    store = DomainStore(session)
    store.delete_import_category_rule(rule_id)
