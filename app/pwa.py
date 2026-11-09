"""Application installable (PWA) : le service worker est servi à la racine pour couvrir tout le site."""
from fastapi import APIRouter
from fastapi.responses import FileResponse

from .config import BASE_DIR

router = APIRouter()


@router.get("/sw.js", include_in_schema=False)
def service_worker():
    return FileResponse(BASE_DIR / "static" / "sw.js", media_type="text/javascript",
                        headers={"Cache-Control": "no-cache", "Service-Worker-Allowed": "/"})
