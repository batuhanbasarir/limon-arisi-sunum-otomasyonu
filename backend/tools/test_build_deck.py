"""Faz 1 uçtan uca doğrulama: tek marka + tek statik görsel + elle caption."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.deck_builder import ContentItem, build_deck, save_deck  # noqa: E402

TEST_IMAGE = r"C:\Users\avaka\AppData\Local\Temp\claude\c--Users-avaka-OneDrive-Desktop-Powerpoint\ff7a3e6e-9570-4632-a2c0-b1e82cc6204a\scratchpad\test_upload.png"

OUT = Path(__file__).resolve().parents[2] / "data" / "output" / "test_nudo.pptx"


def main():
    items = [
        ContentItem(
            caption="Test açıklaması 🍜✨\n\n#Nudo #Test",
            image_paths=[TEST_IMAGE],
        )
    ]
    prs = build_deck("nudo", items)
    save_deck(prs, OUT)
    print(f"Yazıldı: {OUT} ({OUT.stat().st_size} bayt), slayt sayısı: {len(prs.slides)}")


if __name__ == "__main__":
    main()
