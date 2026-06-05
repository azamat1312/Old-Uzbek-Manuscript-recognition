"""HTR dvigateli — satr aniqlash + matn tanib olish quvuri.

`app.py` dagi mantiqning qayta ishlatiladigan versiyasi. Modellar bir marta
(singleton sifatida) yuklanadi. CPU rejimida modellar qayta kirishga xavfsiz
emasligi sababli inference bitta lock ostida ketma-ket bajariladi.

Satrlar aniqlangach, ular `layout.reading_order` orqali mantiqiy text bloklarga
ajratiladi va RTL tartibida (eng yuqoridagi o'ng blokdan boshlab) o'qiladi.
"""
from __future__ import annotations

import logging
import sys
import threading
from dataclasses import dataclass, field
from typing import Callable, List, Optional

import torch
from PIL import Image, ImageDraw, ImageFont

from .config import (
    PROJECT_ROOT,
    GLYPHS_FILE,
    RECOGNITION_WEIGHTS,
    DETECTION_WEIGHTS,
    DETECTION_CONF,
    DETECTION_IMGSZ,
)
from .layout import reading_order

# model.py / read.py / utils.py / modules/ loyiha ildizida joylashgan —
# ularni import qilish uchun ildizni sys.path ga qo'shamiz.
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from model import Model              # noqa: E402
from read import text_recognizer    # noqa: E402
from utils import CTCLabelConverter  # noqa: E402
from ultralytics import YOLO         # noqa: E402

log = logging.getLogger("euyhtr.engine")

# Bloklarni belgilash uchun ranglar
_PALETTE = [
    (220, 40, 40), (40, 140, 40), (40, 80, 220), (200, 120, 0),
    (150, 40, 180), (0, 150, 150), (180, 60, 90), (90, 110, 30),
]

# Loyiha bilan birga keladigan shrift (tizimga bog'liq emas — PyCharm/offline uchun).
_BUNDLED_FONT = str(PROJECT_ROOT / "assets" / "fonts" / "Amiri-Regular.ttf")

# Annotatsiya yorliqlari (blok raqamlari) uchun shrift nomzodlari — bir nechta OT.
# Birinchi topilgani ishlatiladi; hech biri bo'lmasa PIL standart shrifti.
_LABEL_FONT_CANDIDATES = (
    _BUNDLED_FONT,  # loyiha ichidagi shrift — birinchi navbatda
    # Linux (Ubuntu/Debian) — fonts-dejavu-core / fonts-liberation
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    # Windows
    r"C:\Windows\Fonts\arialbd.ttf",
    r"C:\Windows\Fonts\arial.ttf",
    # macOS
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
)


@dataclass
class LineResult:
    """Bitta aniqlangan satr natijasi."""
    box: List[float]   # [x1, y1, x2, y2]
    text: str
    block: int         # qaysi blokka tegishli (o'qish tartibidagi indeks)


@dataclass
class ImageResult:
    """Bitta rasm bo'yicha to'liq natija."""
    text: str = ""
    lines: List[LineResult] = field(default_factory=list)
    annotated: Optional[Image.Image] = None  # ramkalar va bloklar chizilgan tasvir
    num_blocks: int = 0


def _safe_torch_load(path, device):
    """torch 2.6+ da weights_only sukut bo'yicha True; eski checkpointlar uchun
    kerak bo'lsa False bilan qayta urinamiz."""
    try:
        return torch.load(str(path), map_location=device)
    except Exception:  # noqa: BLE001
        return torch.load(str(path), map_location=device, weights_only=False)


class HtrEngine:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        log.info("HTR dvigateli yuklanmoqda... device=%s", self.device)

        # --- Belgilar lug'ati (vocab) ---
        with open(GLYPHS_FILE, "r", encoding="utf-8") as f:
            content = "".join(line.strip("\n") for line in f.readlines())
        content = content + " "
        self.converter = CTCLabelConverter(content)
        self.num_class = len(self.converter.character)

        # --- Tanib olish modeli ---
        self.recognition_model = Model(
            num_class=self.num_class, device=self.device
        ).to(self.device)
        state = _safe_torch_load(RECOGNITION_WEIGHTS, self.device)
        self.recognition_model.load_state_dict(state)
        self.recognition_model.eval()
        log.info("Tanib olish modeli yuklandi (%d sinf).", self.num_class)

        # --- Satr aniqlash modeli ---
        self.detection_model = YOLO(str(DETECTION_WEIGHTS))
        log.info("Satr aniqlash modeli yuklandi: %s", DETECTION_WEIGHTS.name)

    def detect_lines(self, image: Image.Image) -> List[List[float]]:
        """Hujjatdagi matn satrlarini topib, ramkalarni qaytaradi."""
        results = self.detection_model.predict(
            source=image,
            conf=DETECTION_CONF,
            imgsz=DETECTION_IMGSZ,
            save=False,
            nms=True,
            device=self.device,
            verbose=False,
        )
        return results[0].boxes.xyxy.cpu().numpy().tolist()

    # ------------------------------------------------------------------ #
    # Annotatsiya (ramkalar + bloklar + o'qish tartibi raqamlari)
    # ------------------------------------------------------------------ #
    def _get_font(self, image: Image.Image) -> ImageFont.FreeTypeFont:
        size = max(22, image.height // 38)
        for path in _LABEL_FONT_CANDIDATES:
            try:
                return ImageFont.truetype(path, size)
            except Exception:  # noqa: BLE001
                continue
        return ImageFont.load_default()

    @staticmethod
    def _text_size(draw: ImageDraw.ImageDraw, text: str, font) -> tuple:
        try:
            l, t, r, b = draw.textbbox((0, 0), text, font=font)
            return r - l, b - t
        except Exception:  # noqa: BLE001
            return (len(text) * 10, 16)

    def _annotate(
        self, image: Image.Image, boxes: List[List[float]], ordered_blocks: List[List[int]]
    ) -> Image.Image:
        annotated = image.copy()
        draw = ImageDraw.Draw(annotated)
        font = self._get_font(image)

        # Avval barcha satrlarni ingichka kulrang ramka bilan
        for box in boxes:
            draw.rectangle(box, outline=(130, 130, 130), width=2)

        # Keyin bloklarni rangli ramka + o'qish tartibi raqami bilan
        for order_idx, blk in enumerate(ordered_blocks, start=1):
            x1 = min(boxes[i][0] for i in blk)
            y1 = min(boxes[i][1] for i in blk)
            x2 = max(boxes[i][2] for i in blk)
            y2 = max(boxes[i][3] for i in blk)
            color = _PALETTE[(order_idx - 1) % len(_PALETTE)]
            draw.rectangle([x1, y1, x2, y2], outline=color, width=4)

            # Raqam yorlig'i blokning yuqori-o'ng burchagida (RTL boshlanish nuqtasi)
            label = str(order_idx)
            tw, th = self._text_size(draw, label, font)
            lx, ly = x2 - tw - 8, y1 + 2
            draw.rectangle([lx - 5, ly - 3, lx + tw + 5, ly + th + 5], fill=color)
            draw.text((lx, ly), label, fill=(255, 255, 255), font=font)

        return annotated

    # ------------------------------------------------------------------ #
    # Asosiy: bitta rasmni qayta ishlash
    # ------------------------------------------------------------------ #
    def recognize(
        self,
        image: Image.Image,
        progress_cb: Optional[Callable[[int, int], None]] = None,
    ) -> ImageResult:
        """Rasmni qayta ishlaydi: satrlarni aniqlaydi, bloklarga ajratadi,
        RTL o'qish tartibida har bir satrni o'qiydi.

        progress_cb(done, total) — ixtiyoriy, har bir satrdan keyin chaqiriladi.
        """
        image = image.convert("RGB")

        with self._lock, torch.no_grad():
            boxes = self.detect_lines(image)
            total = len(boxes)

            # Mantiqiy bloklarga ajratib, o'qish tartibini aniqlaymiz
            ordered_blocks = reading_order(boxes)
            log.info("%d ta satr -> %d ta blok aniqlandi.", total, len(ordered_blocks))

            annotated = self._annotate(image, boxes, ordered_blocks)

            # O'qish tartibida tanib olamiz
            idx_text: dict = {}
            lines: List[LineResult] = []
            done = 0
            for block_order, blk in enumerate(ordered_blocks):
                for li in blk:
                    box = boxes[li]
                    cropped = image.crop(box)
                    text = text_recognizer(
                        cropped, self.recognition_model, self.converter, self.device
                    )
                    idx_text[li] = text
                    lines.append(
                        LineResult(box=[float(v) for v in box], text=text, block=block_order)
                    )
                    done += 1
                    if progress_cb is not None:
                        progress_cb(done, total)

        # Matnni bloklar bo'yicha birlashtiramiz (bloklar orasida bo'sh qator)
        parts = ["\n".join(idx_text[li] for li in blk) for blk in ordered_blocks]
        full_text = "\n\n".join(parts)

        return ImageResult(
            text=full_text,
            lines=lines,
            annotated=annotated,
            num_blocks=len(ordered_blocks),
        )


# --- Singleton ---
_engine: Optional[HtrEngine] = None
_engine_lock = threading.Lock()


def get_engine() -> HtrEngine:
    """Dvigatelni (bir marta) yuklab, qaytaradi."""
    global _engine
    if _engine is None:
        with _engine_lock:
            if _engine is None:
                _engine = HtrEngine()
    return _engine
