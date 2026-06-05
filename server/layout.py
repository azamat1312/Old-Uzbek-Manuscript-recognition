"""Sahifa tartibini tahlil qilish — aniqlangan satrlarni mantiqiy text bloklarga
ajratib, ularni o'qish tartibiga (RTL: o'ngdan-chapga, yuqoridan-pastga) keltiradi.

Sahifalar turlicha: bir ustunli nasr, ikki ustunli she'r (devon), ko'p ustun +
to'liq enli sarlavhalar, sahifa raqami va hoshiya (marginal) yozuvlari bilan.

Yondashuv — "straddle" (kesib o'tish) hisobiga asoslangan ustun bo'shlig'i (gutter):
  1) TASMA: satrlar Y bo'yicha saralanib, katta vertikal bo'shliqlar bo'yicha
     tasmalarga bo'linadi.
  2) GUTTER: har tasmada eng kam satr kesib o'tadigan vertikal chiziq (gutter)
     qidiriladi. Haqiqiy ustun bo'shlig'ini deyarli hech bir ustun-satri kesmaydi;
     bir-ikkita markaziy sarlavha kesib o'tsa ham gutter aniqlanaveradi (shu bilan
     u oddiy "bo'shliq" usulidan ancha barqaror). Gutter topilmasa — bir ustun.
  3) USTUN + SARLAVHA (rekursiv): gutterning chap/o'ng tomonidagi satrlar alohida
     guruhlar; gutterni kesib o'tuvchi satr (sarlavha/ajratuvchi) ustun oqimini
     uzib, alohida blok bo'ladi. Har guruh yana rekursiv ajratiladi (3+ ustun
     uchun). Ustunlar o'ngdan-chapga (RTL) chiqariladi.

Natija: tasmalar yuqoridan-pastga, ustunlar o'ngdan-chapga, ustun ichida satrlar
yuqoridan-pastga — eng yuqoridagi o'ng blokdan boshlab o'qiladi.
"""
from __future__ import annotations

from statistics import median
from typing import List, Optional, Sequence

Box = Sequence[float]  # [x1, y1, x2, y2]

# --- Sozlanadigan evristik chegaralar ---
BAND_GAP_FACTOR = 2.0    # tasmani uzadigan min. vertikal bo'shliq (median satr balandligida)
SPAN_FRAC = 0.60         # tasma enining shu ulushidan keng satr gutter qidirishda hisobga olinmaydi (sarlavha)
MARGIN_FRAC = 0.12       # tasma enining shu ulushidan tor satr hisobga olinmaydi (raqam/hoshiya)
SIDE_MIN_FRAC = 0.20     # gutterning har ikki tomonida shuncha (ulush) satr bo'lishi shart
STRADDLE_MAX_FRAC = 0.15 # gutterni shu ulushdan ko'p satr kesmasligi kerak
MAX_DEPTH = 5


def _split_bands(order: List[int], boxes: List[Box], band_gap: float) -> List[List[int]]:
    bands: List[List[int]] = []
    cur: List[int] = []
    cur_bottom: Optional[float] = None
    for i in order:
        top, bottom = boxes[i][1], boxes[i][3]
        if cur and cur_bottom is not None and (top - cur_bottom) > band_gap:
            bands.append(cur)
            cur = []
            cur_bottom = None
        cur.append(i)
        cur_bottom = bottom if cur_bottom is None else max(cur_bottom, bottom)
    if cur:
        bands.append(cur)
    return bands


def _find_gutter(band: List[int], boxes: List[Box], mh: float) -> Optional[float]:
    """Tasma ichida ustun bo'shlig'i (gutter) X-koordinatasini qaytaradi yoki None.
    Gutter — eng kam satr kesib o'tadigan, har ikki tomonida yetarli satr bo'lgan
    vertikal chiziq."""
    bx1 = min(boxes[i][0] for i in band)
    bx2 = max(boxes[i][2] for i in band)
    bw = (bx2 - bx1) or 1.0

    # Gutter qidirishda juda keng (sarlavha) va juda tor (raqam/hoshiya) satrlarni chiqaramiz
    mid = [i for i in band if MARGIN_FRAC * bw <= (boxes[i][2] - boxes[i][0]) <= SPAN_FRAC * bw]
    if len(mid) < 4:
        return None

    side_min = max(2, int(SIDE_MIN_FRAC * len(mid)))
    straddle_max = max(1, int(STRADDLE_MAX_FRAC * len(mid)))
    step = max(2.0, mh / 6.0)

    best_pos: Optional[float] = None
    best_straddle: Optional[int] = None
    x = bx1 + 0.12 * bw
    end = bx1 + 0.88 * bw
    while x <= end:
        straddle = left = right = 0
        for i in mid:
            x1i, x2i = boxes[i][0], boxes[i][2]
            if x1i < x < x2i:
                straddle += 1
            elif x2i <= x:
                left += 1
            else:
                right += 1
        if left >= side_min and right >= side_min:
            if best_straddle is None or straddle < best_straddle:
                best_straddle = straddle
                best_pos = x
        x += step

    if best_pos is not None and best_straddle is not None and best_straddle <= straddle_max:
        return best_pos
    return None


def _process(band: List[int], boxes: List[Box], mh: float, depth: int = 0) -> List[List[int]]:
    """Tasmani bloklarga ajratadi (rekursiv ustun + sarlavha)."""
    band = sorted(band, key=lambda i: boxes[i][1])
    if len(band) <= 1 or depth >= MAX_DEPTH:
        return [band] if band else []

    pos = _find_gutter(band, boxes, mh)
    if pos is None:
        return [band]  # bir ustun

    result: List[List[int]] = []
    cur_left: List[int] = []
    cur_right: List[int] = []

    def flush() -> None:
        # RTL: avval o'ng ustun, keyin chap (har biri rekursiv — 3+ ustun uchun)
        if cur_right:
            result.extend(_process(cur_right, boxes, mh, depth + 1))
        if cur_left:
            result.extend(_process(cur_left, boxes, mh, depth + 1))
        cur_right.clear()
        cur_left.clear()

    for i in band:
        x1i, x2i = boxes[i][0], boxes[i][2]
        if x1i < pos < x2i:        # gutterni kesib o'tadi -> sarlavha/ajratuvchi
            flush()
            result.append([i])
        elif x2i <= pos:           # gutterning chapida
            cur_left.append(i)
        else:                      # gutterning o'ngida
            cur_right.append(i)
    flush()
    return result


def reading_order(boxes: List[Box]) -> List[List[int]]:
    """Satr ramkalaridan o'qish tartibidagi bloklar ro'yxatini qaytaradi.
    Har bir blok — satr indekslari (blok ichida yuqoridan-pastga)."""
    n = len(boxes)
    if n == 0:
        return []
    mh = median([b[3] - b[1] for b in boxes]) or 1.0
    band_gap = BAND_GAP_FACTOR * mh

    order = sorted(range(n), key=lambda i: boxes[i][1])
    blocks: List[List[int]] = []
    for band in _split_bands(order, boxes, band_gap):
        blocks.extend(_process(band, boxes, mh))
    return [b for b in blocks if b]
