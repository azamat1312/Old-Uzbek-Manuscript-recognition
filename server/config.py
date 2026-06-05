"""Markaziy konfiguratsiya: yo'llar va sozlamalar.

Barcha yo'llar loyiha ildiziga (PROJECT_ROOT) nisbatan hisoblanadi, shuning uchun
serverni istalgan ish papkasidan ishga tushirish mumkin.
"""
from pathlib import Path

# server/config.py -> server/ -> PROJECT_ROOT
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# --- Model fayllari (loyiha ildizida) ---
GLYPHS_FILE = PROJECT_ROOT / "EUYGlyphs.txt"
RECOGNITION_WEIGHTS = PROJECT_ROOT / "recognition.pth"
DETECTION_WEIGHTS = PROJECT_ROOT / "yolov8m_EUY.pt"

# --- Runtime ma'lumotlari (loglar va ishlar) ---
STORAGE_DIR = PROJECT_ROOT / "storage"
JOBS_DIR = STORAGE_DIR / "jobs"
LOGS_DIR = PROJECT_ROOT / "logs"

# --- Frontend (React build natijasi) ---
WEB_DIST_DIR = PROJECT_ROOT / "web" / "dist"

# --- Satr aniqlash parametrlari ---
DETECTION_CONF = 0.2
DETECTION_IMGSZ = 1280

# --- Tanib olish (recognition) parametrlari ---
MAX_TEXT_WIDTH = 400          # bitta satr tasvirining maksimal eni (px)
RECOG_HEIGHT = 32             # satr tasviri balandligi (px)

# --- Yuklash cheklovlari ---
MAX_UPLOAD_BYTES = 25 * 1024 * 1024   # bitta rasm uchun 25 MB
MAX_IMAGES_PER_JOB = 20               # bitta ishdagi maksimal rasm soni
ALLOWED_CONTENT_TYPES = {
    "image/jpeg", "image/jpg", "image/png", "image/bmp",
    "image/tiff", "image/webp",
}

# --- Server ---
HOST = "0.0.0.0"
PORT = 8000

# Dev rejimida React Vite serveriga (5173) CORS ruxsati
CORS_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]
