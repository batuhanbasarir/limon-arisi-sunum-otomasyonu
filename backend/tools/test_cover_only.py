import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pptx import Presentation
from app.services import slide_cloner

SHARED_DIR = Path(__file__).resolve().parents[2] / "templates" / "_shared"
BADGES_DIR = SHARED_DIR / "badges"
OUT = Path(__file__).resolve().parents[2] / "data" / "output" / "test_cover_only.pptx"


def main():
    prs = Presentation(SHARED_DIR / "skeleton.pptx")
    layout = prs.slide_masters[0].slide_layouts[1]

    cover_slide = slide_cloner.new_slide(prs, layout)
    cover_frag = slide_cloner.load_fragment(SHARED_DIR / "cover.xml.fragment")
    slide_cloner.apply_fragment(cover_slide, cover_frag, BADGES_DIR, brand_name="NUDO")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    prs.save(OUT)
    print(f"Yazıldı: {OUT}")


if __name__ == "__main__":
    main()
