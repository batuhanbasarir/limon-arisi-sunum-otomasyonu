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


def extract_poster_frame(video_path: Path, out_path: Path, at_seconds: float = 0.1):
    """pptx içine gömülecek poster (kapak) kareyi çıkarır."""
    subprocess.run(
        [
            _ffmpeg_exe(), "-y", "-ss", str(at_seconds), "-i", str(video_path),
            "-vframes", "1", str(out_path),
        ],
        check=True, capture_output=True,
    )


def _probe_duration(video_path: Path) -> float:
    result = subprocess.run(
        [
            _ffmpeg_exe(), "-i", str(video_path),
        ],
        capture_output=True, text=True,
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
            check=True, capture_output=True,
        )
        if out_path.exists():
            frames.append(out_path)
    return frames
