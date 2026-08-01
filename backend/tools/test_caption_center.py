import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.deck_builder import ContentItem, build_deck, save_deck  # noqa: E402

TEST_IMAGE = r"C:\Users\avaka\AppData\Local\Temp\claude\c--Users-avaka-OneDrive-Desktop-Powerpoint\ff7a3e6e-9570-4632-a2c0-b1e82cc6204a\scratchpad\test_upload.png"
OUT = Path(__file__).resolve().parents[2] / "data" / "output" / "test_caption_center.pptx"


def main():
    items = [
        ContentItem(caption="Kısa açıklama ✨\n\n#Nudo", image_paths=[TEST_IMAGE]),
        ContentItem(caption="Bu daha uzun bir açıklama satırı, biraz daha fazla metin içeriyor. 🍜\n\nİkinci satır burada.\n\n#Nudo #Uzun", image_paths=[TEST_IMAGE]),
    ]
    prs = build_deck("nudo", items)
    save_deck(prs, OUT)
    print(f"Yazıldı: {OUT}")


if __name__ == "__main__":
    main()
