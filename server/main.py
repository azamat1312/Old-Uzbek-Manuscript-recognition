"""FastAPI ilovasi — REST API va frontendni tarqatish.

Endpointlar:
    GET  /api/health                     — server holati
    POST /api/jobs                       — rasm(lar) yuklash, ish yaratish (darhol qaytadi)
    GET  /api/jobs/{id}                  — ish holati va natijasi (polling uchun)
    GET  /api/jobs/{id}/images/{idx}     — annotatsiyalangan (ramkali) rasm
    GET  /api/jobs/{id}/download?format= — natijani txt/docx/pdf sifatida yuklash

Frontend (React build) `web/dist` da bo'lsa, "/" manzilida tarqatiladi.
"""
from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager
from typing import List

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .config import (
    ALLOWED_CONTENT_TYPES,
    CORS_ORIGINS,
    MAX_IMAGES_PER_JOB,
    MAX_UPLOAD_BYTES,
    WEB_DIST_DIR,
)
from .exporters import MEDIA_TYPES
from .jobs import get_manager
from .logging_config import setup_logging
from .htr_engine import get_engine

setup_logging()
log = logging.getLogger("euyhtr.api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ishga tushganda modellarni oldindan yuklaymiz (tez xatoni aniqlash + isitish)
    log.info("Server ishga tushmoqda — modellar yuklanmoqda...")
    try:
        get_engine()
        log.info("Modellar tayyor.")
    except Exception:  # noqa: BLE001
        log.exception("Modellarni yuklab bo'lmadi!")
    get_manager()
    yield
    log.info("Server to'xtatilmoqda.")


app = FastAPI(title="EUY-HTR", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Har bir so'rovni logga yozamiz."""
    start = time.perf_counter()
    client = request.client.host if request.client else "?"
    response = await call_next(request)
    elapsed = (time.perf_counter() - start) * 1000
    log.info(
        "%s %s -> %d (%.0f ms) | klient=%s",
        request.method, request.url.path, response.status_code, elapsed, client,
    )
    return response


# --------------------------------------------------------------------------- #
# API
# --------------------------------------------------------------------------- #
@app.get("/api/health")
async def health():
    engine = get_engine()
    return {
        "status": "ok",
        "device": str(engine.device),
        "num_class": engine.num_class,
    }


@app.post("/api/jobs", status_code=202)
async def create_job(request: Request, images: List[UploadFile] = File(...)):
    if not images:
        raise HTTPException(status_code=400, detail="Hech qanday rasm yuborilmadi.")
    if len(images) > MAX_IMAGES_PER_JOB:
        raise HTTPException(
            status_code=400,
            detail=f"Juda ko'p rasm (maksimal {MAX_IMAGES_PER_JOB}).",
        )

    files = []
    for up in images:
        if up.content_type not in ALLOWED_CONTENT_TYPES:
            raise HTTPException(
                status_code=415,
                detail=f"Qo'llab-quvvatlanmaydigan fayl turi: {up.content_type}",
            )
        data = await up.read()
        if len(data) == 0:
            raise HTTPException(status_code=400, detail=f"Bo'sh fayl: {up.filename}")
        if len(data) > MAX_UPLOAD_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"Fayl juda katta: {up.filename} (maksimal {MAX_UPLOAD_BYTES // (1024*1024)} MB)",
            )
        files.append(
            {"filename": up.filename or "image", "content_type": up.content_type, "data": data}
        )

    client_ip = request.client.host if request.client else ""
    user_agent = request.headers.get("user-agent", "")
    meta = get_manager().create_job(files, client_ip=client_ip, user_agent=user_agent)
    return {"job_id": meta["job_id"], "status": meta["status"]}


@app.get("/api/jobs/{job_id}")
async def get_job(job_id: str):
    meta = get_manager().get_job(job_id)
    if meta is None:
        raise HTTPException(status_code=404, detail="Ish topilmadi.")
    return meta


@app.get("/api/jobs/{job_id}/images/{index}")
async def get_annotated(job_id: str, index: int):
    path = get_manager().annotated_path(job_id, index)
    if path is None:
        raise HTTPException(status_code=404, detail="Rasm topilmadi.")
    return FileResponse(str(path), media_type="image/png")


# `def` (async emas) — FastAPI buni threadpool'da bajaradi, shunda og'ir
# PDF/DOCX yaratish event loop'ni (va polling'ni) bloklamaydi.
@app.get("/api/jobs/{job_id}/download")
def download(job_id: str, format: str = "txt"):
    fmt = format.lower()
    if fmt not in MEDIA_TYPES:
        raise HTTPException(status_code=400, detail=f"Noma'lum format: {fmt}")
    meta = get_manager().get_job(job_id)
    if meta is None:
        raise HTTPException(status_code=404, detail="Ish topilmadi.")
    if meta.get("status") != "done":
        raise HTTPException(status_code=409, detail="Ish hali tugamagan.")
    try:
        path = get_manager().build_export(job_id, fmt)
    except Exception as exc:  # noqa: BLE001
        log.exception("Eksport xatosi")
        raise HTTPException(status_code=500, detail=f"Eksport xatosi: {exc}")
    if path is None:
        raise HTTPException(status_code=404, detail="Natija topilmadi.")
    return FileResponse(
        str(path),
        media_type=MEDIA_TYPES[fmt],
        filename=f"euyhtr_{job_id}.{fmt}",
    )


# --------------------------------------------------------------------------- #
# Frontend (React build) — agar mavjud bo'lsa
# --------------------------------------------------------------------------- #
if WEB_DIST_DIR.exists():
    app.mount("/", StaticFiles(directory=str(WEB_DIST_DIR), html=True), name="web")
    log.info("Frontend tarqatilmoqda: %s", WEB_DIST_DIR)
else:
    @app.get("/")
    async def root():
        return JSONResponse(
            {
                "message": "EUY-HTR API ishlamoqda. Frontend hali qurilmagan "
                "(web/dist yo'q). React'ni qurish uchun: cd web && npm run build",
                "docs": "/docs",
                "health": "/api/health",
            }
        )
