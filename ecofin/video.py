"""4-bosqich (b): tushuntiruvchi video — slaydlar + ovoz, FFmpeg (bepul)."""
from __future__ import annotations

import subprocess
from pathlib import Path

from . import image
from .audio import duration
from .config import common


def build(post: dict, ch: dict, n: int, narr: list[Path], workdir: Path) -> Path:
    vc = common().get("video", {})
    W, H, fps = vc.get("width", 1080), vc.get("height", 1920), vc.get("fps", 30)
    total = len(post["slides"])
    segs = []
    for i, audio in enumerate(narr):
        png = image.slide(post, ch, n, i, total, workdir / f"slide_{i:02d}.jpg", W, H)
        d = duration(audio) + 0.7
        seg = workdir / f"seg_{i:02d}.mp4"
        # sekin "zoom" effekti va boshida/oxirida yumshoq o'tish
        zoom = (f"scale={W*2}:{H*2},zoompan=z='min(1+0.0004*on,1.06)':d={int(d*fps)+1}"
                f":x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={W}x{H}:fps={fps},"
                f"fade=t=in:st=0:d=0.3,fade=t=out:st={max(d-0.3,0):.2f}:d=0.3,format=yuv420p")
        subprocess.run([
            "ffmpeg", "-y", "-loglevel", "error", "-loop", "1", "-i", str(png), "-i", str(audio),
            "-filter_complex", f"[0:v]{zoom}[v];[1:a]apad=pad_dur=0.7,aresample=44100[a]",
            "-map", "[v]", "-map", "[a]", "-t", f"{d:.2f}",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-r", str(fps),
            "-c:a", "aac", "-b:a", "128k", "-ac", "1", str(seg)], check=True)
        segs.append(seg)

    lst = workdir / "segs.txt"
    lst.write_text("\n".join(f"file '{s.name}'" for s in segs), encoding="utf-8")
    out = workdir / "video.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst),
                    "-c", "copy", "-movflags", "+faststart", str(out)], check=True)
    # Telegram oldindan ko'rinishi uchun muqova
    image.slide(post, ch, n, 0, total, workdir / "thumb_full.jpg", W, H)
    from PIL import Image
    th = Image.open(workdir / "thumb_full.jpg")
    th.thumbnail((320, 320))
    th.save(workdir / "thumb.jpg", quality=85)
    return out
