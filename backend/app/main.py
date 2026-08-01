"""Limon Arısı sunum otomasyonu — backend.

Kapsam: marka seçimi + görsel(1-2)/video yüklenen içerik öğeleri + elle
yazılan veya AI ile üretilen caption'lar -> tek bir .pptx üretimi.
"""
import json
import tempfile
import traceback
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Form, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / "backend" / ".env")

from app.services.deck_builder import ContentItem, build_deck, save_deck, TEMPLATES_DIR
from app.services import media_inspector, ai_captioner

app = FastAPI(title="Limon Arısı Sunum Otomasyonu")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

OUTPUT_DIR = PROJECT_ROOT / "data" / "output"
UPLOAD_TMP_DIR = PROJECT_ROOT / "data" / "uploads"


@app.exception_handler(Exception)
async def unhandled_exception_handler(request, exc):
    traceback.print_exc()
    return JSONResponse(status_code=500, content={"detail": f"Sunucu hatası: {exc}"})


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
    with tempfile.NamedTemporaryFile(dir=UPLOAD_TMP_DIR, suffix=suffix, delete=False) as tmp:
        tmp.write(await file.read())
        tmp_path = Path(tmp.name)

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

        try:
            text = ai_captioner.generate_caption(brand, image_paths)
        except RuntimeError as exc:
            raise HTTPException(400, str(exc))
        except ValueError as exc:
            raise HTTPException(400, str(exc))

        return {"caption": text}
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
            with tempfile.NamedTemporaryFile(
                dir=UPLOAD_TMP_DIR, suffix=suffix, delete=False
            ) as tmp:
                tmp.write(await upload.read())
                tmp_path = Path(tmp.name)
            tmp_paths.append(tmp_path)
            files_by_item.setdefault(idx, []).append(tmp_path)

        items: list[ContentItem] = []
        for i, (caption, kind) in enumerate(zip(captions, kinds)):
            item_files = files_by_item.get(i, [])
            if not item_files:
                raise HTTPException(400, f"İçerik {i + 1} için dosya bulunamadı")

            if kind == "video":
                video_path = item_files[0]
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
