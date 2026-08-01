"""Claude vision ile, markanın kendi caption üslubunu (brand.json'daki
few-shot örnekler) taklit eden açıklama + hashtag metni üretir."""
import base64
import json
import mimetypes
import os
from pathlib import Path

import anthropic

TEMPLATES_DIR = Path(__file__).resolve().parents[3] / "templates"
DEFAULT_MODEL = os.environ.get("ANTHROPIC_CAPTION_MODEL", "claude-opus-5")

_MAX_IMAGE_BYTES = 4_500_000  # Anthropic API görsel boyut sınırına güvenli pay


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

    return {
        "type": "image",
        "source": {
            "type": "base64",
            "media_type": media_type,
            "data": base64.standard_b64encode(data).decode("utf-8"),
        },
    }


def generate_caption(brand_id: str, image_paths: list[Path]) -> str:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise RuntimeError(
            "ANTHROPIC_API_KEY tanımlı değil. backend/.env dosyasına ekleyip sunucuyu yeniden başlatın."
        )

    brand = _load_brand(brand_id)
    examples = brand.get("caption_examples", [])

    system_prompt = (
        f"Sen Limon Arısı reklam ajansının sosyal medya metin yazarısın. "
        f"{brand['display_name']} markası için, verilen görsel(ler)e bakarak Instagram/TikTok tarzında "
        "kısa bir açıklama + hashtag bloğu yazacaksın. Markanın önceki gönderilerinden örnekler:\n\n"
        + "\n---\n".join(examples)
        + "\n\nYeni açıklama bu örneklerle AYNI üslupta olmalı: kısa, samimi, emoji kullanan, "
        "ardından boş satır(lar) ve #hashtag bloğu. Sadece açıklama metnini döndür, başka hiçbir "
        "açıklama, başlık veya tırnak işareti ekleme."
    )

    content = [_image_block(p) for p in image_paths]
    content.append({
        "type": "text",
        "text": "Bu görsel(ler) için markanın üslubunda bir açıklama + hashtag metni yaz.",
    })

    client = anthropic.Anthropic()
    try:
        response = client.messages.create(
            model=DEFAULT_MODEL,
            max_tokens=500,
            system=system_prompt,
            messages=[{"role": "user", "content": content}],
        )
    except anthropic.AuthenticationError:
        raise RuntimeError("ANTHROPIC_API_KEY geçersiz. backend/.env dosyasındaki anahtarı kontrol edin.")
    except anthropic.PermissionDeniedError:
        raise RuntimeError("API anahtarının bu işlem için izni yok.")
    except anthropic.BadRequestError as exc:
        message = str(exc)
        if "credit balance" in message.lower():
            raise RuntimeError(
                "Anthropic hesabınızda kredi bakiyesi yetersiz. "
                "console.anthropic.com üzerinden Plans & Billing bölümünden kredi yükleyin."
            )
        raise RuntimeError(f"AI isteği reddedildi: {message}")
    except anthropic.RateLimitError:
        raise RuntimeError("Anthropic API hız sınırına takıldı, birazdan tekrar deneyin.")
    except anthropic.APIConnectionError:
        raise RuntimeError("Anthropic API'ye bağlanılamadı. İnternet bağlantınızı kontrol edin.")

    if response.stop_reason == "refusal":
        raise RuntimeError("AI içerik üretimini reddetti, lütfen elle yazın.")

    return "".join(block.text for block in response.content if block.type == "text").strip()
