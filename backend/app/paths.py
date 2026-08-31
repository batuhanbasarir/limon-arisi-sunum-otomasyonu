"""Proje kok dizini ve kalici veri dizini tespiti.

Hem normal `python -m uvicorn ...` calistirmasinda hem de PyInstaller ile
derlenmis masaustu .exe'si icinde ayni sekilde calismasi icin, "salt okunur
varliklar" (templates/, frontend/) ile "yazilabilir veri" (uretilen .pptx,
gecici yuklemeler) ayri fonksiyonlarla cozuluyor.
"""
import os
import sys
from pathlib import Path


def get_project_root() -> Path:
    """templates/ ve frontend/ gibi salt-okunur varliklarin kok dizini.

    PyInstaller onefile modunda calisirken bu dosyalar `--add-data` ile
    gecici bir cikartma dizinine (sys._MEIPASS) gomulur; normal
    calistirmada proje kok dizinidir (bu dosyadan iki ust dizin: app -> backend -> proje kok)."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parents[2]


def get_data_dir() -> Path:
    """Yazilabilir, kalici veri dizini (uretilen .pptx dosyalari, gecici
    yuklemeler). .exe icindeki gecici cikartma dizinine YAZILMAZ - o dizin
    uygulama kapaninca silinir ve bazen salt-okunurdur. Onun yerine
    kullanicinin kendi AppData'sinda kalici bir klasor kullanilir."""
    if getattr(sys, "frozen", False):
        base = Path(os.environ.get("LOCALAPPDATA") or Path.home())
        data_dir = base / "LimonArisiSunum"
    else:
        data_dir = get_project_root() / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir
