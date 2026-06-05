"""Ish (job) menejeri — asinxron HTR ishlovi, holatni saqlash va loglash.

Har bir yuborilgan rasm(lar) to'plami uchun alohida "ish" yaratiladi. Ishlov
fonda (alohida ish-zarrachada) bajariladi, shuning uchun HTTP so'rovi darhol
qaytadi va klient bloklanmaydi. Klient `GET /api/jobs/{id}` orqali holatni
so'rab turadi (polling).

Har bir ish o'z papkasiga ega bo'lib, u butun jarayonning doimiy LOGI bo'lib
xizmat qiladi:

    storage/jobs/<job_id>/
        meta.json              # to'liq metama'lumot (holat, vaqtlar, klient, natija)
        input/0001_<nom>.jpg   # serverga yuborilgan rasm(lar)
        output/result.txt      # tanib olingan matn (klientga qaytarilgan natija)
        output/annotated_0001.png  # ramkalar chizilgan tasvir(lar)
        output/result.docx|pdf # so'rov bo'yicha yaratilgan eksport fayllari
"""
from __future__ import annotations

import json
import logging
import os
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from enum import Enum
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Optional

from PIL import Image

from .config import JOBS_DIR
from . import exporters
from .htr_engine import get_engine

log = logging.getLogger("euyhtr.jobs")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class JobStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    DONE = "done"
    ERROR = "error"


class JobManager:
    def __init__(self) -> None:
        # HTR modeli qayta kirishga xavfsiz emas -> bitta worker (ketma-ket)
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="htr")
        self._lock = threading.Lock()
        self._jobs: Dict[str, Dict[str, Any]] = {}
        JOBS_DIR.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------ #
    # Yo'l yordamchilari
    # ------------------------------------------------------------------ #
    def _job_dir(self, job_id: str) -> Path:
        return JOBS_DIR / job_id

    def _meta_path(self, job_id: str) -> Path:
        return self._job_dir(job_id) / "meta.json"

    # ------------------------------------------------------------------ #
    # Saqlash (atomar yozish)
    # ------------------------------------------------------------------ #
    def _persist(self, meta: Dict[str, Any]) -> None:
        path = self._meta_path(meta["job_id"])
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, path)

    def _update(self, job_id: str, **changes: Any) -> Dict[str, Any]:
        with self._lock:
            meta = self._jobs[job_id]
            meta.update(changes)
            meta["updated_at"] = _now_iso()
            self._persist(meta)
            return dict(meta)

    # ------------------------------------------------------------------ #
    # Ish yaratish
    # ------------------------------------------------------------------ #
    def create_job(
        self,
        files: List[Dict[str, Any]],  # [{filename, content_type, data(bytes)}]
        client_ip: str = "",
        user_agent: str = "",
    ) -> Dict[str, Any]:
        job_id = uuid.uuid4().hex[:12]
        job_dir = self._job_dir(job_id)
        input_dir = job_dir / "input"
        output_dir = job_dir / "output"
        input_dir.mkdir(parents=True, exist_ok=True)
        output_dir.mkdir(parents=True, exist_ok=True)

        inputs_meta: List[Dict[str, Any]] = []
        for idx, f in enumerate(files, start=1):
            safe_name = Path(f["filename"]).name or f"image_{idx}"
            stored = input_dir / f"{idx:04d}_{safe_name}"
            stored.write_bytes(f["data"])
            try:
                with Image.open(BytesIO(f["data"])) as im:
                    w, h = im.size
            except Exception:  # noqa: BLE001
                w = h = None
            inputs_meta.append(
                {
                    "index": idx,
                    "original_filename": f["filename"],
                    "stored_path": str(stored.relative_to(JOBS_DIR.parent)),
                    "content_type": f.get("content_type"),
                    "size_bytes": len(f["data"]),
                    "width": w,
                    "height": h,
                }
            )

        meta: Dict[str, Any] = {
            "job_id": job_id,
            "status": JobStatus.PENDING.value,
            "created_at": _now_iso(),
            "updated_at": _now_iso(),
            "started_at": None,
            "finished_at": None,
            "client_ip": client_ip,
            "user_agent": user_agent,
            "inputs": inputs_meta,
            "progress": {"image": 0, "image_total": len(files), "line": 0, "line_total": 0},
            "result": None,
            "error": None,
            "downloads": [],
        }

        with self._lock:
            self._jobs[job_id] = meta
            self._persist(meta)

        log.info(
            "Yangi ish yaratildi: %s | %d ta rasm | klient=%s",
            job_id, len(files), client_ip,
        )
        self._executor.submit(self._process, job_id)
        return dict(meta)

    # ------------------------------------------------------------------ #
    # Fon ishlovi
    # ------------------------------------------------------------------ #
    def _process(self, job_id: str) -> None:
        log.info("Ishlov boshlandi: %s", job_id)
        self._update(
            job_id,
            status=JobStatus.PROCESSING.value,
            started_at=_now_iso(),
        )
        try:
            engine = get_engine()
            meta = self._jobs[job_id]
            inputs = meta["inputs"]
            output_dir = self._job_dir(job_id) / "output"

            images_result: List[Dict[str, Any]] = []
            all_texts: List[str] = []

            for img_meta in inputs:
                idx = img_meta["index"]
                stored = JOBS_DIR.parent / img_meta["stored_path"]
                image = Image.open(stored)

                def progress_cb(done: int, total: int, _idx=idx) -> None:
                    with self._lock:
                        m = self._jobs[job_id]
                        m["progress"] = {
                            "image": _idx,
                            "image_total": len(inputs),
                            "line": done,
                            "line_total": total,
                        }
                        m["updated_at"] = _now_iso()
                        self._persist(m)

                result = engine.recognize(image, progress_cb=progress_cb)

                # Annotatsiyalangan rasmni saqlaymiz
                annotated_name = f"annotated_{idx:04d}.png"
                if result.annotated is not None:
                    result.annotated.save(output_dir / annotated_name)

                images_result.append(
                    {
                        "index": idx,
                        "original_filename": img_meta["original_filename"],
                        "num_lines": len(result.lines),
                        "num_blocks": result.num_blocks,
                        "text": result.text,
                        "annotated_file": annotated_name,
                        "lines": [
                            {"box": ln.box, "text": ln.text, "block": ln.block}
                            for ln in result.lines
                        ],
                    }
                )
                all_texts.append(result.text)
                log.info("Ish %s: rasm %d -> %d satr", job_id, idx, len(result.lines))

            # Bir nechta rasm bo'lsa, ularni ajratuvchi bilan birlashtiramiz
            if len(all_texts) > 1:
                full_text = "\n\n".join(
                    f"--- {i+1}-rasm ---\n{t}" for i, t in enumerate(all_texts)
                )
            else:
                full_text = all_texts[0] if all_texts else ""

            # Natija matnini faylga (logga) yozamiz
            (output_dir / "result.txt").write_text(full_text, encoding="utf-8")

            self._update(
                job_id,
                status=JobStatus.DONE.value,
                finished_at=_now_iso(),
                result={
                    "text": full_text,
                    "num_images": len(images_result),
                    "total_lines": sum(r["num_lines"] for r in images_result),
                    "images": images_result,
                },
            )
            log.info("Ishlov tugadi: %s", job_id)

        except Exception as exc:  # noqa: BLE001
            log.exception("Ishlovda xatolik: %s", job_id)
            self._update(
                job_id,
                status=JobStatus.ERROR.value,
                finished_at=_now_iso(),
                error=f"{type(exc).__name__}: {exc}",
            )

    # ------------------------------------------------------------------ #
    # O'qish
    # ------------------------------------------------------------------ #
    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            if job_id in self._jobs:
                return dict(self._jobs[job_id])
        # Serverdan keyin qayta yuklash uchun diskdan ham o'qiymiz
        meta_path = self._meta_path(job_id)
        if meta_path.exists():
            return json.loads(meta_path.read_text(encoding="utf-8"))
        return None

    def get_result_text(self, job_id: str) -> Optional[str]:
        path = self._job_dir(job_id) / "output" / "result.txt"
        return path.read_text(encoding="utf-8") if path.exists() else None

    # ------------------------------------------------------------------ #
    # Eksport (txt/docx/pdf) — talab bo'yicha yaratiladi va keshlanadi
    # ------------------------------------------------------------------ #
    def build_export(self, job_id: str, fmt: str) -> Optional[Path]:
        text = self.get_result_text(job_id)
        if text is None:
            return None
        out_path = self._job_dir(job_id) / "output" / f"result.{fmt}"
        exporters.export(fmt, text, out_path, title="EUY-HTR — Tanib olingan matn")
        self._record_download(job_id, fmt)
        log.info("Eksport yaratildi: %s -> %s", job_id, fmt)
        return out_path

    def _record_download(self, job_id: str, fmt: str) -> None:
        """Yuklab olishni meta.json ga (logga) yozadi. Lock ichida get_job
        chaqirmaymiz (qayta kirmaydigan lock -> deadlock bo'lardi)."""
        with self._lock:
            meta = self._jobs.get(job_id)
            if meta is None:
                meta_path = self._meta_path(job_id)
                if meta_path.exists():
                    meta = json.loads(meta_path.read_text(encoding="utf-8"))
                    self._jobs[job_id] = meta
            if meta is not None:
                meta.setdefault("downloads", []).append(
                    {"format": fmt, "at": _now_iso()}
                )
                self._persist(meta)

    def annotated_path(self, job_id: str, index: int) -> Optional[Path]:
        path = self._job_dir(job_id) / "output" / f"annotated_{index:04d}.png"
        return path if path.exists() else None


# --- Singleton ---
_manager: Optional[JobManager] = None
_manager_lock = threading.Lock()


def get_manager() -> JobManager:
    global _manager
    if _manager is None:
        with _manager_lock:
            if _manager is None:
                _manager = JobManager()
    return _manager
