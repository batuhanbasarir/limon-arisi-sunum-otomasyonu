"""GPT (OpenAI) vision ile, markanın kendi caption üslubunu (brand.json'daki
few-shot örnekler) taklit eden açıklama + hashtag metni üretir."""
import base64
import json
import mimetypes
import os
from pathlib import Path

import openai

TEMPLATES_DIR = Path(__file__).resolve().parents[3] / "templates"
DEFAULT_MODEL = os.environ.get("OPENAI_CAPTION_MODEL", "gpt-4o-mini")

_MAX_IMAGE_BYTES = 15_000_000  # OpenAI görsel boyut sınırına güvenli pay


def _load_brand(brand_id: str) -> dict:
    path = TEMPLATES_DIR / brand_id / "brand.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _image_block(path: Path) -> dict:
    from PIL import Image
    import io

    data = path.read_bytes()
    media_type = mimetypes.guess_type(str(path))[0] or "image/jpeg"

    if len(data) > _MAX_IMAGE_BYTES:
        img = Image.open(io.BytesIO(data))
        img.thumbnail((1568, 1568))
        buf = io.BytesIO()
        fmt = "PNG" if media_type == "image/png" else "JPEG"
        img.convert("RGB" if fmt == "JPEG" else img.mode).save(buf, format=fmt)
        data = buf.getvalue()
        media_type = "image/png" if fmt == "PNG" else "image/jpeg"

    b64 = base64.standard_b64encode(data).decode("utf-8")
    return {
        "type": "image_url",
        "image_url": {"url": f"data:{media_type};base64,{b64}"},
    }


def _call_chat(messages: list[dict]) -> str:
    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError(
            "OPENAI_API_KEY tanımlı değil. backend/.env dosyasına ekleyip sunucuyu yeniden başlatın."
        )

    client = openai.OpenAI()
    try:
        response = client.chat.completions.create(
            model=DEFAULT_MODEL,
            max_tokens=500,
            messages=messages,
        )
    except openai.AuthenticationError:
        raise RuntimeError("OPENAI_API_KEY geçersiz. backend/.env dosyasındaki anahtarı kontrol edin.")
    except openai.PermissionDeniedError:
        raise RuntimeError("API anahtarının bu işlem için izni yok.")
    except openai.BadRequestError as exc:
        raise RuntimeError(f"AI isteği reddedildi: {exc}")
    except openai.RateLimitError as exc:
        message = str(exc)
        if "quota" in message.lower() or "insufficient_quota" in message.lower():
            raise RuntimeError(
                "OpenAI hesabınızda kredi bakiyesi yetersiz. "
                "platform.openai.com üzerinden Billing bölümünden kredi yükleyin."
            )
        raise RuntimeError("OpenAI API hız sınırına takıldı, birazdan tekrar deneyin.")
    except openai.APIConnectionError:
        raise RuntimeError("OpenAI API'ye bağlanılamadı. İnternet bağlantınızı kontrol edin.")

    choice = response.choices[0]
    if choice.finish_reason == "content_filter":
        raise RuntimeError("AI içerik üretimini reddetti, lütfen elle yazın.")

    return (choice.message.content or "").strip()


def _brand_voice_prompt(brand: dict) -> str:
    examples = brand.get("caption_examples", [])
    return (
        f"Sen Limon Arısı reklam ajansının sosyal medya metin yazarısın. "
        f"{brand['display_name']} markası için Instagram/TikTok tarzında kısa açıklama + hashtag "
        "bloğu yazıyorsun. Markanın önceki gönderilerinden örnekler:\n\n"
        + "\n---\n".join(examples)
        + "\n\nÜretilen/güncellenen metin bu örneklerle AYNI üslupta olmalı. Sadece açıklama "
        "metnini döndür, başka hiçbir açıklama, başlık veya tırnak işareti ekleme."
    )


def generate_caption(brand_id: str, image_paths: list[Path]) -> str:
    brand = _load_brand(brand_id)
    system_prompt = (
        _brand_voice_prompt(brand)
        + "\n\nVerilen görsel(ler)e bakarak bu üslupta, kısa, samimi, emoji kullanan, ardından "
        "boş satır(lar) ve #hashtag bloğu içeren yeni bir açıklama yaz."
    )

    content = [_image_block(p) for p in image_paths]
    content.append({
        "type": "text",
        "text": "Bu görsel(ler) için markanın üslubunda bir açıklama + hashtag metni yaz.",
    })

    return _call_chat([
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": content},
    ])


def revise_caption(brand_id: str, caption: str, instruction: str) -> str:
    """Var olan bir caption'ı, verilen talimata göre (daha kısa/resmi/esprili ya da
    serbest metin) markanın üslubunu koruyarak yeniden yazar."""
    if not caption.strip():
        raise ValueError("Revize edilecek bir açıklama yok. Önce bir açıklama yazın veya AI ile üretin.")
    if not instruction.strip():
        raise ValueError("Revize talimatı boş olamaz.")

    brand = _load_brand(brand_id)
    system_prompt = (
        _brand_voice_prompt(brand)
        + "\n\nSana mevcut bir açıklama ve bir revize talimatı verilecek. Açıklamayı, marka "
        "üslubunu koruyarak talimata göre yeniden yaz."
    )
    user_prompt = f"Mevcut açıklama:\n{caption}\n\nRevize talimatı: {instruction}"

    return _call_chat([
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ])
