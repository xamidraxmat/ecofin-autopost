"""4-bosqich (a): matnni ovozga aylantirish — Microsoft Edge neyron ovozlari (bepul)."""
from __future__ import annotations

import asyncio
import os
import subprocess
from pathlib import Path

from .config import log


def duration(path: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "default=nw=1:nk=1", str(path)], capture_output=True, text=True)
    return float(out.stdout.strip() or 0)


async def _edge(text: str, voice: str, rate: str, out: Path):
    import edge_tts
    await edge_tts.Communicate(text, voice, rate=rate).save(str(out))


def tts(text: str, voice: str, rate: str, out: Path) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    if os.environ.get("TTS_FALLBACK") == "silence":
        # faqat sinov uchun: ovoz o'rniga jimlik (taxminiy davomiylik)
        secs = max(2.5, len(text.split()) / 2.4)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                        f"sine=frequency=0:duration={secs}", "-ac", "1", "-ar", "24000",
                        "-b:a", "64k", str(out)], check=True)
        return out
    for attempt in range(3):
        try:
            asyncio.run(_edge(text, voice, rate, out))
            if out.exists() and out.stat().st_size > 1000:
                return out
        except Exception as e:  # tarmoq xatosi — qayta urinish
            log(f"TTS xato ({attempt + 1}/3): {e}")
    raise RuntimeError("Ovoz yaratib bo'lmadi (Edge TTS).")


def narrate_slides(post: dict, ch: dict, workdir: Path) -> tuple[list[Path], Path]:
    """Har bir slayd uchun alohida audio va ularni birlashtirgan to'liq audio."""
    parts = []
    for i, s in enumerate(post["slides"]):
        parts.append(tts(s["narration"], ch["voice"], ch.get("voice_rate", "+0%"),
                         workdir / f"narr_{i:02d}.mp3"))
    full = workdir / "audio.mp3"
    lst = workdir / "audio_list.txt"
    # slaydlar orasida 0.5 s pauza
    gap = workdir / "gap.mp3"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                    "anullsrc=r=24000:cl=mono", "-t", "0.5", "-b:a", "64k", str(gap)], check=True)
    lines = []
    for p in parts:
        lines += [f"file '{p.name}'", f"file '{gap.name}'"]
    lst.write_text("\n".join(lines), encoding="utf-8")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst),
                    "-ac", "1", "-ar", "44100", "-b:a", "128k", str(full)], check=True)
    return parts, full
