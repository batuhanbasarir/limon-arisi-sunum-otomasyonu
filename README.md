# Limon Arısı — Monthly Presentation Automation

A small internal web app for **Limon Arısı** (ad agency) that automates building the
monthly client report decks (Instagram/TikTok content recaps) for brands like
Erişun, Nudo, Miluni, and others.

## What it does

- Pick a brand from a dropdown (brand list is just the folders under `templates/`).
- Drag & drop content per slide: 1 image, 2 images side by side, or a video.
- Generate an on-brand Turkish caption + hashtags for each item with Claude
  (vision), or write your own.
- Get back a ready `.pptx`: cover slide (brand name, big logo) → one slide per
  content item → closing slide — visually matching the agency's existing template,
  with correct aspect ratios (no stretched images) and a small brand logo on
  every slide.

## Stack

- **Backend**: Python, FastAPI, `python-pptx` (deck assembly), `Pillow` +
  `imageio-ffmpeg` (media handling), Anthropic SDK (caption generation).
- **Frontend**: plain HTML/CSS/JS, no build step.

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\pip install -r backend\requirements.txt

# AI captions need an Anthropic API key
copy backend\.env.example backend\.env
# then edit backend\.env and set ANTHROPIC_API_KEY=sk-ant-...

.\.venv\Scripts\python -m uvicorn app.main:app --app-dir backend --port 8000
```

Open `http://127.0.0.1:8000`.

## Project layout

```
backend/app/main.py             FastAPI routes (/api/brands, /api/assemble, /api/caption)
backend/app/services/           deck building, media inspection, AI captioning
templates/_shared/              shared cover/closing/content slide fragments + skeleton.pptx
templates/<brand>/brand.json    per-brand display name + few-shot caption examples
frontend/                       drag-and-drop UI
data/uploads, data/output       runtime scratch space (gitignored)
```

## Ekibe paylaşma (ücretsiz, uzaktan erişim)

Herkes evden bağlanacaksa app'i [Render](https://render.com)'ın ücretsiz
"Web Service" katmanında barındırabilirsiniz (kredi kartı gerekmez).

1. render.com'da GitHub hesabınızla giriş yapın, bu repoyu (`limon-arisi-sunum-otomasyonu`) seçin.
2. **New > Blueprint** ile devam edin — repodaki `render.yaml` build/start komutlarını otomatik okur (plan: `free`).
   - Blueprint görünmüyorsa **New > Web Service** ile manuel kurun:
     - Build command: `pip install -r backend/requirements.txt`
     - Start command: `uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port $PORT`
3. **Environment** sekmesinden şu değişkenleri girin:
   - `ANTHROPIC_API_KEY` — AI caption için.
   - `APP_USERNAME`, `APP_PASSWORD` — ikisi de doluysa siteye girerken ortak
     kullanıcı adı/şifre sorulur (linki bulan herkesin API'yi ücretsiz
     kullanmasını engeller). Ekibe bu ikisini paylaşın.
4. Deploy edin. Render size `https://limon-arisi-sunum.onrender.com` gibi bir
   URL verir, o linki ekiple paylaşmanız yeterli.

Not: ücretsiz katman ~15 dakika kullanılmayınca uyur; bir sonraki istekte
sunucunun uyanması 30-50 saniye sürebilir, sonrası normal hızda çalışır.

## Adding a brand

Add a new `templates/<brand_id>/brand.json`:

```json
{ "id": "brand_id", "display_name": "BRAND NAME", "caption_examples": ["..."] }
```

It shows up in the brand dropdown automatically. `caption_examples` are real
past captions used as few-shot examples so the AI matches that brand's voice —
the more/better examples, the better the generated captions.
