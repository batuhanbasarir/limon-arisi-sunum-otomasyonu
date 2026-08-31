"""Limon Arısı sunum otomasyonu — masaüstü uygulaması (yerel sunucu).

Kapsam: marka seçimi + görsel(1-2)/video yüklenen içerik öğeleri + elle
yazılan veya AI ile üretilen caption'lar -> tek bir .pptx üretimi.

Bu, kullanıcının kendi bilgisayarında çalışır (bkz. desktop_launcher.py) —
video/görsel dosyaları hiçbir zaman internete çıkmaz, tamamen yerelde
işlenir. Sadece AI caption üretimi/revizyonu için (küçük kareler halinde)
bulut servisine (cloud_app.py, Render'da) istek atılır; OpenAI API anahtarı
sadece orada, kullanıcının bilgisayarında değil.
"""
import json
import os
import tempfile
import traceback
from pathlib import Path

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, Form, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.paths import get_data_dir, get_project_root

PROJECT_ROOT = get_project_root()
load_dotenv(PROJECT_ROOT / "backend" / ".env")

from app.services.deck_builder import ContentItem, build_deck, save_deck, TEMPLATES_DIR
from app.services import media_inspector

app = FastAPI(title="Limon Arısı Sunum Otomasyonu")

# Caption/revize istekleri icin kullanilacak bulut servisi (bkz. cloud_app.py,
# Render'da barinir). CLOUD_CAPTION_URL ile gecersiz kilinabilir (orn. yerel
# gelistirmede kendi makinende calisan bir cloud_app instance'ina isaret
# etmek icin).
CLOUD_CAPTION_URL = os.environ.get(
    "CLOUD_CAPTION_URL", "https://limon-arisi-sunum.onrender.com"
).rstrip("/")
# Not: bu, kullanicinin bilgisayarindaki .exe icine gomulen paylasilan bir
# anahtar - gizli tutulmasi gereken tek sey (OPENAI_API_KEY) sadece
# cloud_app.py'de/Render'da. Bu deger sadece "URL'yi bulan rastgele biri
# degil, bizim masaustu uygulamamiz istiyor" seviyesinde bir kontrol.
# Gercek deger git'e gomulmez: build_exe.bat calistirilirken yerel (gitignore'lu)
# backend/app/_secrets.py dosyasindan .exe'ye gomulur (bkz. o dosya).
try:
    from app._secrets import APP_KEY as _BAKED_APP_KEY
except ImportError:
    _BAKED_APP_KEY = ""
CLOUD_APP_KEY = os.environ.get("APP_KEY", _BAKED_APP_KEY)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DATA_DIR = get_data_dir()
OUTPUT_DIR = DATA_DIR / "output"
UPLOAD_TMP_DIR = DATA_DIR / "uploads"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_TMP_DIR.mkdir(parents=True, exist_ok=True)

UPLOAD_CHUNK_SIZE = 1024 * 1024  # 1 MB
# Artik yerel makinede calistigi icin (bkz. desktop_launcher.py) paylasimli
# bir sunucunun RAM siniri yok - ama videolar yine de pptx'e gomulmeden once
# sikistiriliyor (bkz. media_inspector.compress_video): hem nihai .pptx
# dosyasi kucuk kalir (paylasmasi/mailmesi kolaylasir) hem de PowerPoint'in
# kendisi buyuk videolarla daha akici calisir. Sadece gercekten devasa
# (muhtemelen yanlislikla secilmis) bir dosyaya karsi bir ust sinir var.
MAX_RAW_VIDEO_MB_PER_FILE = int(os.environ.get("MAX_RAW_VIDEO_MB_PER_FILE", "2000"))
# Bunun altindaki videolar zaten kucuk, sikistirmaya (ve onun getirdigi
# islem suresine) gerek yok.
COMPRESS_VIDEO_THRESHOLD_MB = 8


async def _save_upload_streaming(upload: UploadFile, dest_dir: Path, suffix: str) -> Path:
    """Yuklenen dosyayi tek seferde tamamen bellege okumadan (await
    upload.read() gibi), parca parca diske yazar. Ozellikle buyuk
    videolarda bellek kullanimini onemli olcude azaltir."""
    with tempfile.NamedTemporaryFile(dir=dest_dir, suffix=suffix, delete=False) as tmp:
        tmp_path = Path(tmp.name)
        while True:
            chunk = await upload.read(UPLOAD_CHUNK_SIZE)
            if not chunk:
                break
            tmp.write(chunk)
    return tmp_path


async def _cloud_post(
    path: str, data: dict, files: list[tuple] | None = None
) -> dict:
    """Bulut (Render) uzerindeki kucuk caption servisine istek atar. Sadece
    kucuk metin/gorsel verisi gonderilir - video/gorsel dosyalarinin tamami
    HER ZAMAN yerel makinede kalir, sunucuya hic yuklenmez."""
    headers = {"X-App-Key": CLOUD_APP_KEY} if CLOUD_APP_KEY else {}
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{CLOUD_CAPTION_URL}{path}", data=data, files=files, headers=headers
            )
    except httpx.RequestError as exc:
        raise HTTPException(
            503,
            f"AI servisine ulaşılamadı, internet bağlantınızı kontrol edin ({exc}).",
        )

    if resp.status_code != 200:
        try:
            detail = resp.json().get("detail", resp.text)
        except Exception:
            detail = resp.text
        raise HTTPException(resp.status_code, detail)
    return resp.json()


@app.exception_handler(Exception)
async def unhandled_exception_handler(request, exc):
    traceback.print_exc()
    return JSONResponse(status_code=500, content={"detail": f"Sunucu hatası: {exc}"})


@app.get("/healthz")
def healthz():
    """Uptime-ping servisleri icin: sadece hizli 200 doner, agir is yapmaz."""
    return {"status": "ok"}


@app.get("/api/brands")
def list_brands():
    brands = []
    for brand_dir in sorted(TEMPLATES_DIR.iterdir()):
        if brand_dir.name.startswith("_"):
            continue
        brand_json = brand_dir / "brand.json"
        if brand_json.exists():
            data = json.loads(brand_json.read_text(encoding="utf-8"))
            brands.append({"id": data["id"], "display_name": data["display_name"]})
    return brands


@app.post("/api/caption")
async def caption(brand: str = Form(...), file: UploadFile = File(...)):
    UPLOAD_TMP_DIR.mkdir(parents=True, exist_ok=True)
    suffix = Path(file.filename or "").suffix or ".jpg"
    tmp_path = await _save_upload_streaming(file, UPLOAD_TMP_DIR, suffix)

    frame_paths: list[Path] = []
    try:
        if media_inspector.is_video(tmp_path):
            frame_dir = tmp_path.with_suffix("")
            frame_paths = media_inspector.extract_caption_frames(tmp_path, frame_dir)
            if not frame_paths:
                raise HTTPException(400, "Videodan kare çıkarılamadı")
            image_paths = frame_paths
        else:
            image_paths = [tmp_path]

        files = [
            ("frames", (p.name, p.read_bytes(), "image/jpeg")) for p in image_paths
        ]
        result = await _cloud_post("/api/caption-from-frames", {"brand": brand}, files=files)
        return {"caption": result["caption"]}
    finally:
        tmp_path.unlink(missing_ok=True)
        for fp in frame_paths:
            fp.unlink(missing_ok=True)
        frame_dir = tmp_path.with_suffix("")
        if frame_dir.exists():
            try:
                frame_dir.rmdir()
            except OSError:
                pass


@app.post("/api/revise-caption")
async def revise_caption(
    brand: str = Form(...),
    caption: str = Form(...),
    instruction: str = Form(...),
):
    result = await _cloud_post(
        "/api/revise-caption",
        {"brand": brand, "caption": caption, "instruction": instruction},
    )
    return {"caption": result["caption"]}


@app.post("/api/assemble")
async def assemble(
    brand: str = Form(...),
    month: str = Form(...),
    year: int = Form(...),
    captions: list[str] = Form(...),
    kinds: list[str] = Form(...),
    file_item_index: list[int] = Form(...),
    files: list[UploadFile] = File(...),
):
    if len(kinds) != len(captions):
        raise HTTPException(400, "captions ve kinds sayısı eşleşmeli")
    if len(files) != len(file_item_index):
        raise HTTPException(400, "files ve file_item_index sayısı eşleşmeli")
    if not kinds:
        raise HTTPException(400, "en az bir içerik gerekli")

    UPLOAD_TMP_DIR.mkdir(parents=True, exist_ok=True)
    tmp_paths: list[Path] = []
    files_by_item: dict[int, list[Path]] = {}

    try:
        for idx, upload in zip(file_item_index, files):
            suffix = Path(upload.filename or "").suffix or ".png"
            tmp_path = await _save_upload_streaming(upload, UPLOAD_TMP_DIR, suffix)
            tmp_paths.append(tmp_path)
            files_by_item.setdefault(idx, []).append(tmp_path)

        items: list[ContentItem] = []
        for i, (caption, kind) in enumerate(zip(captions, kinds)):
            item_files = files_by_item.get(i, [])
            if not item_files:
                raise HTTPException(400, f"İçerik {i + 1} için dosya bulunamadı")

            if kind == "video":
                video_path = item_files[0]
                raw_mb = video_path.stat().st_size / 1024 / 1024
                if raw_mb > MAX_RAW_VIDEO_MB_PER_FILE:
                    raise HTTPException(
                        400,
                        f"İçerik {i + 1}: video dosyası çok büyük ({raw_mb:.0f} MB). "
                        f"En fazla {MAX_RAW_VIDEO_MB_PER_FILE} MB olabilir.",
                    )

                if raw_mb > COMPRESS_VIDEO_THRESHOLD_MB:
                    compressed_path = video_path.with_suffix(".compressed.mp4")
                    try:
                        media_inspector.compress_video(video_path, compressed_path)
                    except Exception as exc:
                        raise HTTPException(400, f"İçerik {i + 1}: video sıkıştırılamadı ({exc})")
                    tmp_paths.append(compressed_path)
                    video_path = compressed_path

                poster_path = video_path.with_suffix(".poster.jpg")
                try:
                    media_inspector.extract_poster_frame(video_path, poster_path)
                except Exception as exc:
                    raise HTTPException(400, f"İçerik {i + 1}: video işlenemedi ({exc})")
                tmp_paths.append(poster_path)
                items.append(ContentItem(
                    caption=caption, video_path=str(video_path), poster_path=str(poster_path)
                ))
            else:
                if len(item_files) > 2:
                    raise HTTPException(400, f"İçerik {i + 1}: en fazla 2 görsel desteklenir")
                items.append(ContentItem(
                    caption=caption, image_paths=[str(p) for p in item_files]
                ))

        try:
            prs = build_deck(brand, items)
        except ValueError as exc:
            raise HTTPException(400, str(exc))

        out_name = f"{brand.upper()} {month} {year}.pptx"
        out_path = OUTPUT_DIR / out_name
        save_deck(prs, out_path)
    finally:
        for p in tmp_paths:
            p.unlink(missing_ok=True)

    return FileResponse(
        out_path,
        filename=out_name,
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
    )


BADGES_DIR = TEMPLATES_DIR / "_shared" / "badges"
if BADGES_DIR.exists():
    app.mount("/brand-assets", StaticFiles(directory=BADGES_DIR), name="brand-assets")

FRONTEND_DIR = PROJECT_ROOT / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
