from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

WEB_DIR = Path(__file__).resolve().parent.parent / "web"
STATIC_DIR = WEB_DIR / "static"
STATIC_ROOT = STATIC_DIR.resolve()

router = APIRouter(tags=["web"])

_NO_CACHE = {"Cache-Control": "no-store"}


@router.api_route("/static/{file_path:path}", methods=["GET", "HEAD"], include_in_schema=False)
def static_file(file_path: str) -> FileResponse:
    candidate = (STATIC_DIR / file_path).resolve()
    if not candidate.is_relative_to(STATIC_ROOT) or not candidate.is_file():
        raise HTTPException(status_code=404, detail="Not Found")
    return FileResponse(candidate, headers=_NO_CACHE)


@router.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(WEB_DIR / "index.html", media_type="text/html", headers=_NO_CACHE)