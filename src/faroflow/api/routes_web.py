from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse

router = APIRouter(tags=["web"])

STATIC_DIR = Path(__file__).resolve().parents[3] / "static"

# El index nunca se cachea: es el documento que apunta a los módulos de /static.
# Sin esto, el navegador guarda el HTML con el heurístico de Chrome y puede
# seguir apuntando a un JS viejo aunque el archivo en disco ya sea otro.
NO_CACHE = {"Cache-Control": "no-cache"}


@router.get("/", include_in_schema=False)
def index():
    return FileResponse(STATIC_DIR / "web" / "index.html", headers=NO_CACHE)