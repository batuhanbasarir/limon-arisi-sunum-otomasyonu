"""Yüklenen dosyanın video mu görsel mi olduğunu tespit eder ve video için
poster kare / AI caption karesi çıkarır."""
import mimetypes
import subprocess
from pathlib import Path

import imageio_ffmpeg

VIDEO_EXTENSIONS = {".mp4", ".mov", ".m4v", ".webm"}


def is_video(path: Path) -> bool:
    if path.suffix.lower() in VIDEO_EXTENSIONS:
        return True
    mime, _ = mimetypes.guess_type(str(path))
    return bool(mime and mime.startswith("video/"))


def _ffmpeg_exe() -> str:
    return imageio_ffmpeg.get_ffmpeg_exe()


def compress_video(
    src: Path,
    dst: Path,
    *,
    max_dim: int = 1080,
    video_bitrate_kbps: int = 2000,
    audio_bitrate_kbps: int = 128,
) -> None:
    """Videoyu .pptx'e gömmeden önce küçültür: uzun kenarı `max_dim` piksele,
    bit hızını `video_bitrate_kbps`'e sabitler. python-pptx add_movie()
    dosyanın TAMAMINI belleğe okuyup save() çağrılana kadar tuttuğu için, bu
    adım hem sunucudaki RAM kullanımını hem de nihai .pptx dosya boyutunu
    büyük ölçüde azaltır (tipik telefon çekimi 15-50 Mbps iken burada ~2
    Mbps'e iniyor — inceleme sunumu için yeterli kalitede kalır)."""
    scale = (
        f"scale='if(gt(iw,ih),min({max_dim},iw),-2)':"
        f"'if(gt(iw,ih),-2,min({max_dim},ih))'"
    )
    subprocess.run(
        [
            _ffmpeg_exe(), "-y", "-i", str(src),
            "-vf", scale,
            "-c:v", "libx264", "-preset", "veryfast",
            "-b:v", f"{video_bitrate_kbps}k",
            "-maxrate", f"{video_bitrate_kbps}k",
            "-bufsize", f"{video_bitrate_kbps * 2}k",
            "-c:a", "aac", "-b:a", f"{audio_bitrate_kbps}k",
            "-movflags", "+faststart",
            str(dst),
        ],
        check=True, capture_output=True, timeout=300,
    )


def extract_poster_frame(video_path: Path, out_path: Path, at_seconds: float = 0.1):
    """pptx içine gömülecek poster (kapak) kareyi çıkarır."""
    subprocess.run(
        [
            _ffmpeg_exe(), "-y", "-ss", str(at_seconds), "-i", str(video_path),
            "-vframes", "1", str(out_path),
        ],
        check=True, capture_output=True, timeout=60,
    )


def _probe_duration(video_path: Path) -> float:
    result = subprocess.run(
        [
            _ffmpeg_exe(), "-i", str(video_path),
        ],
        capture_output=True, text=True, timeout=60,
    )
    # ffmpeg (ffprobe değil) sürüm bilgisini stderr'e yazar; "Duration: HH:MM:SS.xx" satırını ara.
    for line in result.stderr.splitlines():
        line = line.strip()
        if line.startswith("Duration:"):
            hms = line.split(",")[0].replace("Duration:", "").strip()
            h, m, s = hms.split(":")
            return int(h) * 3600 + int(m) * 60 + float(s)
    return 3.0


def extract_caption_frames(video_path: Path, out_dir: Path, count: int = 4) -> list[Path]:
    """AI caption üretimi için videodan eşit aralıklarla `count` kare çıkarır."""
    out_dir.mkdir(parents=True, exist_ok=True)
    duration = _probe_duration(video_path)
    frames = []
    for i in range(count):
        # Baş ve sonu tam kenardan almamak için (0.1, 1) aralığına yay
        fraction = 0.1 + (0.8 * i / max(count - 1, 1))
        timestamp = max(duration * fraction, 0.1)
        out_path = out_dir / f"frame_{i}.jpg"
        subprocess.run(
            [
                _ffmpeg_exe(), "-y", "-ss", str(timestamp), "-i", str(video_path),
                "-vframes", "1", str(out_path),
            ],
            check=True, capture_output=True, timeout=60,
        )
        if out_path.exists():
            frames.append(out_path)
    return frames
