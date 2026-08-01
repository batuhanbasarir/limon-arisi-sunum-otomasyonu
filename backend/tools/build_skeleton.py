"""templates/_shared/skeleton.pptx üretir.

Örnek dosyalardan birini temel alıp tüm slaytları (ve onlarla birlikte
erişilemez hale gelen medya/parçaları) kaldırır; tema, slaytMaster ve
slaytLayout'lar (dolayısıyla fontlar/renkler) korunur. python-pptx'in
save() metodu yalnızca ilişki grafiğinden erişilebilir parçaları
serileştirdiği için, sldIdLst + ilişkiyi kaldırmak medya/slide XML'lerinin
de otomatik olarak dışarıda kalmasını sağlar.
"""
from pathlib import Path

import sys

from pptx import Presentation

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.services.pptx_repair import fix_pptx_package  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "NUDO temmuz.pptm"
OUT = ROOT / "templates" / "_shared" / "skeleton.pptx"


def main():
    prs = Presentation(SOURCE)
    xml_slides = prs.slides._sldIdLst
    for sld in list(xml_slides):
        prs.part.drop_rel(sld.rId)
        xml_slides.remove(sld)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    prs.save(OUT)
    fix_pptx_package(OUT, slide_count=0)
    print(f"skeleton.pptx yazıldı: {OUT} ({OUT.stat().st_size} bayt)")


if __name__ == "__main__":
    main()
