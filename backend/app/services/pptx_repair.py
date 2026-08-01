"""docProps/app.xml düzeltmesi.

python-pptx slayt eklerken/silerken docProps/app.xml içindeki
<Slides>/<Notes>/<MMClips>/<HeadingPairs>/<TitlesOfParts> alanlarını
güncellemiyor. Bu alanlar gerçek paket içeriğiyle (ör. "14 slayt" derken
paket 0 slayt içeriyorsa) tutarsız kalırsa PowerPoint dosyayı bozuk sanıp
onarım isteyebiliyor (Faz 0 doğrulamasında PowerPoint COM otomasyonuyla
tespit edildi). Bu modül, kaydedilmiş bir .pptx dosyasındaki app.xml'i
gerçek slayt sayısına göre tutarlı hale getirir.
"""
import zipfile
from pathlib import Path

from lxml import etree

_NS_EP = "http://schemas.openxmlformats.org/officeDocument/2006/extended-properties"
_NS_VT = "http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes"
_NSMAP = {"ep": _NS_EP, "vt": _NS_VT}


def _qn(prefix_local: str) -> str:
    prefix, local = prefix_local.split(":")
    return f"{{{_NSMAP[prefix]}}}{local}"


_NS_CT = "http://schemas.openxmlformats.org/package/2006/content-types"

_MACRO_ENABLED_CT = "application/vnd.ms-powerpoint.presentation.macroEnabled.main+xml"
_PLAIN_PPTX_CT = "application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"


def _fix_presentation_content_type(root: etree._Element):
    """.pptm kaynaklı bir Presentation'ı .pptx olarak kaydederken
    [Content_Types].xml içindeki /ppt/presentation.xml Override'ı hâlâ
    "macroEnabled" tipini taşıyabiliyor (python-pptx bunu otomatik
    düzeltmiyor). Uzantı (.pptx) ile iç içerik tipi (macroEnabled, .pptm'e
    özgü) uyuşmazlığı PowerPoint'in dosyayı bozuk sanıp onarım istemesine
    yol açıyor — Faz 0 doğrulamasında PowerPoint COM otomasyonuyla tespit
    edildi."""
    for override in root.iter(f"{{{_NS_CT}}}Override"):
        if override.get("PartName") == "/ppt/presentation.xml" and override.get("ContentType") == _MACRO_ENABLED_CT:
            override.set("ContentType", _PLAIN_PPTX_CT)


def fix_pptx_package(pptx_path: Path, slide_count: int):
    """Kaydedilmiş bir .pptx dosyasını PowerPoint'in onarım istemesine yol
    açan iki bilinen tutarsızlık için düzeltir: (1) docProps/app.xml'deki
    stale slayt/not/multimedya sayıları, (2) .pptm kaynaklı macroEnabled
    içerik tipi kalıntısı."""
    with zipfile.ZipFile(pptx_path) as zf:
        names = zf.namelist()
        contents = {n: zf.read(n) for n in names}

    if "docProps/app.xml" in contents:
        app_root = etree.fromstring(contents["docProps/app.xml"])
        for tag, value in (("ep:Slides", str(slide_count)), ("ep:Notes", "0"), ("ep:MMClips", "0")):
            el = app_root.find(_qn(tag))
            if el is not None:
                el.text = value
        for tag in ("ep:HeadingPairs", "ep:TitlesOfParts"):
            el = app_root.find(_qn(tag))
            if el is not None:
                app_root.remove(el)
        contents["docProps/app.xml"] = etree.tostring(
            app_root, xml_declaration=True, encoding="UTF-8", standalone=True
        )

    if "[Content_Types].xml" in contents:
        ct_root = etree.fromstring(contents["[Content_Types].xml"])
        _fix_presentation_content_type(ct_root)
        contents["[Content_Types].xml"] = etree.tostring(
            ct_root, xml_declaration=True, encoding="UTF-8", standalone=True
        )

    with zipfile.ZipFile(pptx_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in contents.items():
            zf.writestr(name, data)
