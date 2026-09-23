from __future__ import annotations

from fastapi import Request
from sqlalchemy.orm import Session

from cuentafaro.audit import ACTOR_KEY
from cuentafaro.db import get_session_factory


def get_session(request: Request) -> Session:
    session = get_session_factory()()
    session.info[ACTOR_KEY] = (request.headers.get("X-Actor") or "").strip() or None
    try:
        yield session
    finally:
        session.close()
