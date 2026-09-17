from fastapi import APIRouter, Request, Response

from faroflow.schemas import (
    EntityId,
    TranslatableEntityKind,
    TranslationCreate,
    TranslationField,
    TranslationRead,
    TranslationUpdate,
)

from .deps import (
    DbSession,
    PageLimit,
    PageOffset,
    create_record,
    delete_record,
    get_record,
    page_items,
    set_page_links,
    update_record,
)

router = APIRouter()


@router.post(
    "/api/v1/translations",
    response_model=TranslationRead,
    status_code=201,
    tags=["translations"],
)
def create_translation(payload: TranslationCreate, session: DbSession):
    return create_record(session, "translation", payload)


@router.get("/api/v1/translations", response_model=list[TranslationRead], tags=["translations"])
def list_translations(
    session: DbSession,
    response: Response,
    request: Request,
    entity_kind: TranslatableEntityKind | None = None,
    entity_id: EntityId | None = None,
    field_name: TranslationField | None = None,
    language: str | None = None,
    limit: PageLimit = None,
    offset: PageOffset = 0,
):
    items, has_more = page_items(
        session,
        "translation",
        {
            "entity_kind": entity_kind,
            "entity_id": entity_id,
            "field_name": field_name,
            "language": language,
        },
        limit,
        offset,
    )
    set_page_links(response, request, limit, offset, has_more)
    return items


@router.get(
    "/api/v1/translations/{entity_id}",
    response_model=TranslationRead,
    tags=["translations"],
)
def get_translation(entity_id: EntityId, session: DbSession):
    return get_record(session, "translation", entity_id)


@router.patch(
    "/api/v1/translations/{entity_id}",
    response_model=TranslationRead,
    tags=["translations"],
)
def update_translation(
    entity_id: EntityId,
    payload: TranslationUpdate,
    session: DbSession,
):
    return update_record(session, "translation", entity_id, payload)


@router.delete("/api/v1/translations/{entity_id}", status_code=204, tags=["translations"])
def delete_translation(entity_id: EntityId, session: DbSession):
    return delete_record(session, "translation", entity_id)