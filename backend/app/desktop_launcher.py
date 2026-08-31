"""Masaüstü .exe giriş noktası: yerel sunucuyu başlatır ve tarayıcıyı açar.

PyInstaller ile bu dosya derlenir (bkz. proje kökündeki build_exe.bat).
Çalışırken app.main:app'i (tüm .pptx üretim mantığı) 127.0.0.1 üzerinde
uvicorn ile ayağa kaldırır ve varsayılan tarayıcıyı otomatik açar."""
import socket
import sys
import threading
import time
import webbrowser

import uvicorn

HOST = "127.0.0.1"


def _find_free_port(preferred: int = 8000) -> int:
    for port in range(preferred, preferred + 20):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind((HOST, port))
                return port
            except OSError:
                continue
    return preferred


def _open_browser(port: int) -> None:
    time.sleep(1.5)
    webbrowser.open(f"http://{HOST}:{port}")


def main() -> None:
    from app.main import app  # gec import: once .env/PROJECT_ROOT kurulumu tamamlansin

    port = _find_free_port()
    print("=" * 60)
    print("  Limon Arısı Sunum Otomasyonu")
    print("=" * 60)
    print(f"\nTarayıcınızda birazdan http://{HOST}:{port} otomatik açılacak.")
    print("\n*** BU PENCEREYİ KAPATMAYIN *** — kapatırsanız uygulama durur.")
    print("(Bitirdiğinizde bu pencereyi kapatarak çıkabilirsiniz.)\n")

    threading.Thread(target=_open_browser, args=(port,), daemon=True).start()

    try:
        uvicorn.run(app, host=HOST, port=port, log_level="warning")
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    sys.exit(main() or 0)
