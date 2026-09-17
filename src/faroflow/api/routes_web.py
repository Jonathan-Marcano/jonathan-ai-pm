from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse

router = APIRouter(tags=["web"])

STATIC_DIR = Path(__file__).resolve().parents[3] / "static"


@router.get("/", include_in_schema=False)
def index():
    return FileResponse(STATIC_DIR / "web" / "index.html")