from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.transcribe import router as transcribe_router

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

app = FastAPI(title="逐字稿載入系統")
app.include_router(transcribe_router)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")
