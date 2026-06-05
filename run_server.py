r"""EUY-HTR serverni ishga tushirish.

Terminaldan:
    python run_server.py

Server 0.0.0.0:8000 da tinglaydi — lokal tarmoqdagi qurilmalar
http://<server-ip>:8000 orqali ulanadi. Host/port'ni EUY_HOST / EUY_PORT
muhit o'zgaruvchilari orqali o'zgartirish mumkin.
"""
from __future__ import annotations

import os
import socket


def _local_ip() -> str:
    """Lokal tarmoqdagi IP manzilni aniqlashga urinadi (faqat ko'rsatma uchun)."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("8.8.8.8", 80))  # haqiqiy ulanish ochilmaydi
            return s.getsockname()[0]
        finally:
            s.close()
    except Exception:  # noqa: BLE001
        return "127.0.0.1"


def main() -> None:
    import uvicorn

    host = os.environ.get("EUY_HOST", "0.0.0.0")
    port = int(os.environ.get("EUY_PORT", "8000"))

    ip = _local_ip()
    print("=" * 60)
    print("  EUY-HTR server ishga tushmoqda")
    print(f"  Shu kompyuterda:           http://localhost:{port}")
    print(f"  Lokal tarmoqdan (klient):  http://{ip}:{port}")
    print("=" * 60)

    # DIQQAT: workers=1 va reload=False bo'lishi SHART —
    # ish holati xotirada saqlanadi, HTR modeli ketma-ket ishlaydi.
    uvicorn.run("server.main:app", host=host, port=port, workers=1, reload=False)


if __name__ == "__main__":
    main()
