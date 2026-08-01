"""Faz 0 kalibrasyon aracı.

Üç örnek dosyadan (kapak/kapanış/içerik-dekor shape ağaçları markalar arası
bit-bit aynı olduğu doğrulandığı için) TEK bir paylaşılan şablon çıkarır:

- templates/_shared/skeleton.pptx  (0 slaytlı, tema/master/layout korunmuş)
- templates/_shared/badges/*.png   (rozet + kurumsal logo görselleri)
- templates/_shared/cover.xml.fragment      ({{BRAND_NAME}} placeholder'lı)
- templates/_shared/closing.xml.fragment    (tamamen jenerik, "TEŞEKKÜRLER")
- templates/_shared/content_decor.xml.fragment  (sol-alt rozet + sağ-üst logo)

Görsel referansları fragment içinde gerçek r:embed rId'leri yerine
{{IMG:<key>}} token'ları ile tutulur; slide_cloner çalışma zamanında bunları
yeni slaydın kendi rId'leriyle değiştirir.

Kullanım:
    python extract_brand_profile.py
"""
import re
import zipfile
from pathlib import Path

from lxml import etree

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "NUDO temmuz.pptm"
OUT_DIR = ROOT / "templates" / "_shared"
BADGES_DIR = OUT_DIR / "badges"

NS = {
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "rel": "http://schemas.openxmlformats.org/package/2006/relationships",
    "ct": "http://schemas.openxmlformats.org/package/2006/content-types",
}


def read_zip_xml(zf, path):
    return etree.fromstring(zf.read(path))


def get_slide_rels(zf, slide_name):
    """slideN.xml.rels içindeki rId -> (type, target) haritasını döndür."""
    rels_path = f"ppt/slides/_rels/{slide_name}.xml.rels"
    root = read_zip_xml(zf, rels_path)
    mapping = {}
    for rel in root.findall("rel:Relationship", NS):
        mapping[rel.get("Id")] = (rel.get("Type"), rel.get("Target"))
    return mapping


def find_shape_by_id(spTree, shape_id):
    for el in spTree:
        tag = etree.QName(el).localname
        if tag not in ("sp", "pic", "grpSp", "graphicFrame", "cxnSp"):
            continue
        nv = el.find(f"./{{{NS['p']}}}nv{tag[0].upper()}{tag[1:]}Pr") if False else None
        # nvXxxPr elemanının adı shape tipine göre değişir; genel arayışla bul.
        for child in el.iter():
            if etree.QName(child).localname == "cNvPr" and child.get("id") == str(shape_id):
                return el
    return None


def collect_embed_ids(element):
    """Element içindeki tüm r:embed / r:id referanslarını bul."""
    embeds = set()
    for el in element.iter():
        for attr in ("{%s}embed" % NS["r"], "{%s}link" % NS["r"], "{%s}id" % NS["r"]):
            val = el.get(attr)
            if val:
                embeds.add(val)
    return embeds


def extract_fragment(zf, slide_name, shape_ids, image_key_by_rid, brand_text_replace=None):
    slide_root = read_zip_xml(zf, f"ppt/slides/{slide_name}.xml")
    spTree = slide_root.find(".//p:cSld/p:spTree", NS)
    rels = get_slide_rels(zf, slide_name)

    fragment_root = etree.Element("fragment")
    for sid in shape_ids:
        shape_el = find_shape_by_id(spTree, sid)
        if shape_el is None:
            raise ValueError(f"{slide_name}: shape id={sid} bulunamadı")
        shape_copy = etree.fromstring(etree.tostring(shape_el))

        # r:embed / r:link referanslarını {{IMG:key}} token'ına çevir.
        for el in shape_copy.iter():
            for attr in ("{%s}embed" % NS["r"], "{%s}link" % NS["r"]):
                rid = el.get(attr)
                if rid and rid in rels:
                    key = image_key_by_rid.get(rid)
                    if key:
                        el.set(attr, f"{{{{IMG:{key}}}}}")

        if brand_text_replace:
            for t in shape_copy.iter(f"{{{NS['a']}}}t"):
                if t.text and t.text.strip() == brand_text_replace:
                    t.text = "{{BRAND_NAME}}"

        fragment_root.append(shape_copy)

    return fragment_root, rels


def main():
    BADGES_DIR.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(SOURCE) as zf:
        names = zf.namelist()
        slide_files = sorted(
            (n for n in names if re.match(r"ppt/slides/slide\d+\.xml$", n)),
            key=lambda n: int(re.search(r"\d+", Path(n).stem).group()),
        )
        cover_name = Path(slide_files[0]).stem
        closing_name = Path(slide_files[-1]).stem
        content_name = Path(slide_files[1]).stem  # slide2 -> içerik dekor kaynağı

        # --- görselleri çıkar ve isimlendir ---
        image_key_by_rid = {}
        image_key_names = {}

        def register_image(slide_name, shape_id, key):
            rels = get_slide_rels(zf, slide_name)
            slide_root = read_zip_xml(zf, f"ppt/slides/{slide_name}.xml")
            spTree = slide_root.find(".//p:cSld/p:spTree", NS)
            shape_el = find_shape_by_id(spTree, shape_id)
            embeds = collect_embed_ids(shape_el)
            for rid in embeds:
                if rid in rels:
                    _type, target = rels[rid]
                    media_path = "ppt/" + target.replace("../", "")
                    ext = Path(media_path).suffix
                    out_name = f"{key}{ext}"
                    (BADGES_DIR / out_name).write_bytes(zf.read(media_path))
                    image_key_by_rid[rid] = key
                    image_key_names[key] = out_name

        # kapak: id=16 (orta rozet), id=8 (sol-alt rozet grubu, iç PICTURE dahil), id=14 (kurumsal logo)
        register_image(cover_name, 16, "badge_center")
        register_image(cover_name, 8, "badge_corner")
        register_image(cover_name, 14, "corp_logo")

        cover_frag, _ = extract_fragment(
            zf, cover_name, [16, 8, 14, 4], image_key_by_rid, brand_text_replace="NUDO"
        )
        closing_frag, _ = extract_fragment(
            zf, closing_name, [16, 8, 14, 2], image_key_by_rid
        )
        content_frag, _ = extract_fragment(
            zf, content_name, [8, 14], image_key_by_rid
        )

    (OUT_DIR / "cover.xml.fragment").write_bytes(etree.tostring(cover_frag, pretty_print=True))
    (OUT_DIR / "closing.xml.fragment").write_bytes(etree.tostring(closing_frag, pretty_print=True))
    (OUT_DIR / "content_decor.xml.fragment").write_bytes(etree.tostring(content_frag, pretty_print=True))

    print("Çıkarılan görseller:", image_key_names)
    print("Fragment dosyaları yazıldı:", OUT_DIR)


if __name__ == "__main__":
    main()
