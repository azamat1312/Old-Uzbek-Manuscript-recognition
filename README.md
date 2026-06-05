# EUY-HTR — Eski o'zbek yozuvi uchun HTR tizimi

Eski o'zbek yozuvi(arab grafikasiga asoslangan)dagi hujjatlarni matnga o'giruvchi tizim. Rasm
yuklanadi, natija TXT / DOCX / PDF sifatida qaytariladi.

## Talablar

- Python 3.10+
- Node.js 18+
- Model fayllari: `recognition.pth` va `yolov8m_EUY.pt`
  — 📥 [yuklab olish](https://drive.google.com/drive/folders/1gzCauNYhTMDfmFeZUHhf-s0B7gftl9-E?usp=sharing), loyiha ildiziga joylashtiring.

## Qadamlar

1. Python virtual muhit yaratib, kutubxonalarni o'rnating (`requirements-server.txt`).
2. Frontendni qurish: `web/` papkasida `npm install`, so'ng `npm run build`.
3. Model fayllarini yuklab olib, loyiha ildiziga joylashtiring.
4. Serverni ishga tushiring: `python run_server.py`.
5. Brauzerda oching: `http://localhost:8000`
