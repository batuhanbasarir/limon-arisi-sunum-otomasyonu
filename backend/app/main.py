"""Limon Arısı sunum otomasyonu — backend.

Kapsam: marka seçimi + görsel(1-2)/video yüklenen içerik öğeleri + elle
yazılan veya AI ile üretilen caption'lar -> tek bir .pptx üretimi.
"""
import hashlib
import json
import os
import secrets
import tempfile
import traceback
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Form, Request, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / "backend" / ".env")

from app.services.deck_builder import ContentItem, build_deck, save_deck, TEMPLATES_DIR
from app.services import media_inspector, ai_captioner

app = FastAPI(title="Limon Arısı Sunum Otomasyonu")

APP_USERNAME = os.getenv("APP_USERNAME")
APP_PASSWORD = os.getenv("APP_PASSWORD")
SESSION_COOKIE = "la_session"
# Dogru kullanici adi/sifre girildiginde cookie'ye yazilacak sabit deger.
_SESSION_TOKEN = (
    hashlib.sha256(f"{APP_USERNAME}:{APP_PASSWORD}".encode("utf-8")).hexdigest()
    if APP_USERNAME and APP_PASSWORD
    else None
)

LOGIN_PAGE = """<!DOCTYPE html>
<html lang="tr"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Giriş — Limon Arısı</title>
<style>
  * {{ box-sizing: border-box; }}
  body {{ margin:0; min-height:100vh; display:flex; align-items:center; justify-content:center;
    font-family: system-ui, -apple-system, "Segoe UI", sans-serif; background:#fffdf5;
    background-image: radial-gradient(circle at 100% 0%, rgba(253,224,0,0.18), transparent 45%); }}
  .card {{ background:#fff; border:1px solid #e7dfc0; border-radius:12px; padding:2rem 2.25rem;
    width:100%; max-width:340px; box-shadow:0 4px 20px rgba(0,0,0,0.06); }}
  h1 {{ font-size:1.1rem; margin:0 0 1.25rem; color:#24242a; }}
  label {{ display:block; font-size:0.85rem; font-weight:600; margin-bottom:0.3rem; color:#24242a; }}
  input {{ width:100%; padding:0.55rem 0.65rem; margin-bottom:1rem; border:1px solid #e7dfc0;
    border-radius:6px; font:inherit; background:#fffef9; }}
  button {{ width:100%; padding:0.65rem; border:none; border-radius:6px; background:#FDE000;
    color:#24242a; font-weight:700; cursor:pointer; font-size:0.95rem; }}
  button:hover {{ background:#e6cc00; }}
  .error {{ background:#fdecea; color:#c0392b; border:1px solid #c0392b; border-radius:6px;
    padding:0.6rem 0.75rem; font-size:0.85rem; font-weight:600; margin-bottom:1rem; }}
</style></head>
<body>
  <form class="card" method="post" action="/login">
    <h1>🐝 Limon Arısı — Giriş</h1>
    {error_html}
    <label for="u">Kullanıcı adı</label>
    <input id="u" name="username" autocomplete="username" autofocus required>
    <label for="p">Şifre</label>
    <input id="p" name="password" type="password" autocomplete="current-password" required>
    <button type="submit">Giriş Yap</button>
  </form>
</body></html>"""


class SessionAuthMiddleware(BaseHTTPMiddleware):
    """APP_USERNAME/APP_PASSWORD ayarlıysa tüm siteyi ortak bir şifre arkasına
    kilitler (paylaşılan bir sunucuda barındırırken API bütçesini korumak
    için). İkisi de boşsa (yerel geliştirme) auth devre dışı kalır.

    Tarayıcı-native "Basic Auth" yerine kendi /login sayfamızı kullanıyoruz:
    yanlış şifre girildiğinde tarayıcı o girdiyi sonsuza kadar önbelleğe
    alıp kullanıcıya bir daha soru sormadan tekrar tekrar 401 döndürebiliyor
    (gerçek bug, kullanıcıdan geldi). Kendi login formumuzda bu sorun yok:
    yanlış girilirse formu net bir hatayla tekrar gösteririz."""

    async def dispatch(self, request, call_next):
        if not _SESSION_TOKEN:
            return await call_next(request)

        path = request.url.path
        # Ping servisleri ve login sayfasinin kendisi auth'suz erisilebilir olmali.
        if path == "/healthz" or path == "/login":
            return await call_next(request)

        if secrets.compare_digest(request.cookies.get(SESSION_COOKIE, ""), _SESSION_TOKEN):
            return await call_next(request)

        if path.startswith("/api/"):
            return JSONResponse(status_code=401, content={"detail": "Giriş yapmanız gerekiyor."})
        return RedirectResponse(url="/login", status_code=302)


@app.get("/login", response_class=HTMLResponse)
def login_form():
    if not _SESSION_TOKEN:
        return RedirectResponse(url="/", status_code=302)
    return LOGIN_PAGE.format(error_html="")


@app.post("/login")
def login_submit(username: str = Form(...), password: str = Form(...)):
    if not _SESSION_TOKEN:
        return RedirectResponse(url="/", status_code=302)

    if secrets.compare_digest(username, APP_USERNAME) and secrets.compare_digest(
        password, APP_PASSWORD
    ):
        resp = RedirectResponse(url="/", status_code=302)
        resp.set_cookie(
            key=SESSION_COOKIE,
            value=_SESSION_TOKEN,
            httponly=True,
            secure=True,
            samesite="lax",
            max_age=60 * 60 * 24 * 30,  # 30 gün
        )
        return resp

    error_html = '<div class="error">Kullanıcı adı veya şifre yanlış. Tekrar deneyin.</div>'
    return HTMLResponse(LOGIN_PAGE.format(error_html=error_html), status_code=401)


@app.get("/logout")
def logout():
    resp = RedirectResponse(url="/login", status_code=302)
    resp.delete_cookie(SESSION_COOKIE)
    return resp


app.add_middleware(SessionAuthMiddleware)

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


@app.post("/api/revise-caption")
async def revise_caption(
    brand: str = Form(...),
    caption: str = Form(...),
    instruction: str = Form(...),
):
    try:
        text = ai_captioner.revise_caption(brand, caption, instruction)
    except RuntimeError as exc:
        raise HTTPException(400, str(exc))
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return {"caption": text}


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
