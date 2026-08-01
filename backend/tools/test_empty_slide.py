import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pptx import Presentation
from app.services import slide_cloner

SHARED_DIR = Path(__file__).resolve().parents[2] / "templates" / "_shared"
OUT = Path(__file__).resolve().parents[2] / "data" / "output" / "test_empty_slide.pptx"


def main():
    prs = Presentation(SHARED_DIR / "skeleton.pptx")
    layout = prs.slide_masters[0].slide_layouts[1]
    slide_cloner.new_slide(prs, layout)
    prs.save(OUT)
    print(f"Yazıldı: {OUT}")


if __name__ == "__main__":
    main()
