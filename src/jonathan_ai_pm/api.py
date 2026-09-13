from fastapi import FastAPI

from jonathan_ai_pm import __version__

app = FastAPI(title="Jonathan AI PM", version=__version__)


@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__}
