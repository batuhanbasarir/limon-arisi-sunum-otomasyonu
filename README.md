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

## Adding a brand

Add a new `templates/<brand_id>/brand.json`:

```json
{ "id": "brand_id", "display_name": "BRAND NAME", "caption_examples": ["..."] }
```

It shows up in the brand dropdown automatically. `caption_examples` are real
past captions used as few-shot examples so the AI matches that brand's voice —
the more/better examples, the better the generated captions.
