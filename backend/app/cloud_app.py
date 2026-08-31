"""Limon Arısı — bulut caption servisi.

Masaüstü uygulamasına geçişle birlikte, sunucuda SADECE OpenAI API
anahtarının gizli kalması gereken kısım kaldı: caption üretimi/revizyonu.
Video/görsel dosyalarının kendisi hiçbir zaman bu servise yüklenmez —
masaüstü uygulaması videodan/görselden küçük kareler çıkarıp (birkaç yüz
KB) sadece onları buraya gönderir. Sunum oluşturma (.pptx derleme) tamamen
kullanıcının kendi bilgisayarında, bu servise hiç dokunmadan olur.
"""
import os
import secrets
import tempfile
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Form, File, UploadFile, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware

from .paths import get_project_root

load_dotenv(get_project_root() / "backend" / ".env")

from .services import ai_captioner  # noqa: E402  (load_dotenv'den sonra import edilmeli)

app = FastAPI(title="Limon Arısı Caption Servisi")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Masaüstü uygulamalarının bu servise erişmek için gönderdiği ortak anahtar.
# Boş bırakılırsa (yerel geliştirmede olduğu gibi) kontrol devre dışı kalır -
# ama canlıda (Render) mutlaka ayarlanmalı, yoksa OpenAI faturasını herkes
# ücretsiz kullanabilir.
APP_KEY = os.environ.get("APP_KEY")


def _check_key(x_app_key: str | None) -> None:
    if APP_KEY and not (x_app_key and secrets.compare_digest(x_app_key, APP_KEY)):
        raise HTTPException(401, "Geçersiz uygulama anahtarı.")


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


@app.post("/api/caption-from-frames")
async def caption_from_frames(
    brand: str = Form(...),
    frames: list[UploadFile] = File(...),
    x_app_key: str | None = Header(default=None, alias="X-App-Key"),
):
    _check_key(x_app_key)
    if not frames:
        raise HTTPException(400, "En az bir kare gerekli.")

    with tempfile.TemporaryDirectory() as tmp:
        image_paths: list[Path] = []
        for i, frame in enumerate(frames):
            suffix = Path(frame.filename or "").suffix or ".jpg"
            path = Path(tmp) / f"frame_{i}{suffix}"
            path.write_bytes(await frame.read())
            image_paths.append(path)

        try:
            text = ai_captioner.generate_caption(brand, image_paths)
        except (RuntimeError, ValueError) as exc:
            raise HTTPException(400, str(exc))

    return {"caption": text}


@app.post("/api/revise-caption")
async def revise_caption(
    brand: str = Form(...),
    caption: str = Form(...),
    instruction: str = Form(...),
    x_app_key: str | None = Header(default=None, alias="X-App-Key"),
):
    _check_key(x_app_key)
    try:
        text = ai_captioner.revise_caption(brand, caption, instruction)
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(400, str(exc))
    return {"caption": text}
