"""3-bosqich: brend rasm (post kartasi) va video slaydlarini chizish — Pillow, bepul."""
from __future__ import annotations

import math
import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .config import ROOT

FONTS = ROOT / "assets" / "fonts"


def font(weight: str, size: int) -> ImageFont.FreeTypeFont:
    files = {"display": "InterDisplay-ExtraBold.otf", "bold": "Inter-Bold.otf",
             "semi": "Inter-SemiBold.otf", "medium": "Inter-Medium.otf", "regular": "Inter-Regular.otf"}
    return ImageFont.truetype(str(FONTS / files[weight]), size)


def hex2rgb(h: str, a: int | None = None):
    h = h.lstrip("#")
    rgb = tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
    return rgb + (a,) if a is not None else rgb


EMOJI = re.compile("[\U0001F000-\U0001FFFF\u2600-\u27BF\u2B00-\u2BFF\uFE0F\u200D]")


def plain(text: str) -> str:
    """Shriftda yo'q emoji/belgilarni olib tashlaydi (rasmda kvadrat chiqmasligi uchun)."""
    return re.sub(r"\s{2,}", " ", EMOJI.sub("", text or "")).strip()


def wrap(draw: ImageDraw.ImageDraw, text: str, fnt, width: int) -> list[str]:
    text = plain(text)
    lines = []
    for para in text.split("\n"):
        words, line = para.split(), ""
        for w in words:
            test = f"{line} {w}".strip()
            if draw.textlength(test, font=fnt) <= width:
                line = test
            else:
                if line:
                    lines.append(line)
                line = w
        lines.append(line)
    return lines


def fit_text(draw, text, weight, max_size, min_size, width, max_lines):
    size = max_size
    while size >= min_size:
        f = font(weight, size)
        lines = wrap(draw, text, f, width)
        if len(lines) <= max_lines:
            return f, lines
        size -= 4
    f = font(weight, min_size)
    lines = wrap(draw, text, f, width)[:max_lines]
    lines[-1] = lines[-1].rstrip(" .,") + "…"
    return f, lines


# ---------- fon va bezaklar ----------

def background(w: int, h: int, c: dict) -> Image.Image:
    top, bot = hex2rgb(c["bg_top"]), hex2rgb(c["bg_bottom"])
    img = Image.new("RGB", (w, h))
    px = ImageDraw.Draw(img)
    for y in range(h):
        t = y / h
        px.line([(0, y), (w, y)], fill=tuple(int(top[i] + (bot[i] - top[i]) * t) for i in range(3)))
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    acc = c["accent"]
    # islomiy geometrik naqsh: 8 qirrali yulduzlar (o'ng yuqori burchakda)
    step = 150
    for gx in range(0, w + step, step):
        for gy in range(0, int(h * 0.55), step):
            dist = math.hypot(w - gx, gy) / math.hypot(w, h * 0.55)
            alpha = int(max(0, 34 * (1 - dist * 1.25)))
            if alpha > 3:
                star(d, gx, gy, 52, hex2rgb(acc, alpha), width=2)
    # pastki burchakda yumshoq yorug'lik
    glow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    for r in range(420, 0, -12):
        gd.ellipse([-r, h - r, r, h + r], fill=hex2rgb(acc, int(10 * (1 - r / 420)) ))
    img = Image.alpha_composite(img.convert("RGBA"), glow)
    return Image.alpha_composite(img, layer)


def star(d: ImageDraw.ImageDraw, cx, cy, r, color, width=2):
    for rot in (0, 45):
        pts = []
        for k in range(4):
            a = math.radians(rot + 45 + 90 * k)
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
        d.polygon(pts, outline=color, width=width)
    d.ellipse([cx - r * 0.32, cy - r * 0.32, cx + r * 0.32, cy + r * 0.32], outline=color, width=width)


def paste_logo(img: Image.Image, ch: dict, x: int, y: int, height: int) -> int:
    """Logoni qo'yadi, logo eni qaytariladi. Logo fayli bo'lmasa, matnli logo chiziladi."""
    path = ROOT / ch.get("logo", "")
    d = ImageDraw.Draw(img)
    if path.is_file():
        logo = Image.open(path).convert("RGBA")
        ratio = height / logo.height
        logo = logo.resize((int(logo.width * ratio), height), Image.LANCZOS)
        img.alpha_composite(logo, (x, y))
        return logo.width
    c = ch["colors"]
    f = font("display", int(height * 0.62))
    d.rounded_rectangle([x, y, x + height, y + height], radius=int(height * 0.28), fill=hex2rgb(c["accent"]))
    star(d, x + height / 2, y + height / 2, height * 0.3, hex2rgb(c["bg_bottom"]), width=3)
    name = ch.get("channel_name", "EcoFin")
    d.text((x + height + 18, y + height / 2), name, font=f, fill=hex2rgb(c["text"]), anchor="lm")
    return height + 18 + int(d.textlength(name, font=f))


def pill(d, x, y, text, c, fnt, right_align=False):
    tw = d.textlength(text, font=fnt)
    w, h = tw + 44, fnt.size + 26
    if right_align:
        x -= w
    d.rounded_rectangle([x, y, x + w, y + h], radius=h // 2, outline=hex2rgb(c["accent"]), width=3)
    d.text((x + w / 2, y + h / 2), text, font=fnt, fill=hex2rgb(c["accent"]), anchor="mm")
    return w, h


def lesson_label(ch: dict, n: int) -> str:
    return f"{n}-DARS" if ch["language"] == "uz" else f"LESSON {n}"


# ---------- post kartasi ----------

def post_card(post: dict, topic: dict, ch: dict, n: int, out: Path) -> Path:
    W, H = 1080, 1350
    c = ch["colors"]
    img = background(W, H, c)
    d = ImageDraw.Draw(img)
    M = 84

    paste_logo(img, ch, M, 72, 88)
    pill(d, W - M, 84, lesson_label(ch, n), c, font("bold", 30), right_align=True)

    y = 290
    module = topic.get("module_" + ("uz" if ch["language"] == "uz" else "en"), "")
    d.text((M, y), module.upper(), font=font("semi", 28), fill=hex2rgb(c["muted"]))
    y += 64

    tf, lines = fit_text(d, post["title"], "display", 96, 60, W - 2 * M, 4)
    for line in lines:
        d.text((M, y), line, font=tf, fill=hex2rgb(c["text"]))
        y += int(tf.size * 1.12)
    y += 26
    d.rounded_rectangle([M, y, M + 120, y + 8], radius=4, fill=hex2rgb(c["accent"]))
    y += 46

    sf, slines = fit_text(d, post["subtitle"], "medium", 40, 30, W - 2 * M, 2)
    for line in slines:
        d.text((M, y), line, font=sf, fill=hex2rgb(c["muted"]))
        y += int(sf.size * 1.35)
    y += 40

    kf = font("semi", 36)
    for i, kp in enumerate(post.get("key_points", [])[:3], 1):
        cy = y + 30
        d.ellipse([M, cy - 26, M + 52, cy + 26], fill=hex2rgb(c["accent"]))
        d.text((M + 26, cy), str(i), font=font("bold", 28), fill=hex2rgb(c["bg_bottom"]), anchor="mm")
        kl = wrap(d, kp, kf, W - 2 * M - 80)[:2]
        for j, line in enumerate(kl):
            d.text((M + 80, cy + j * 46), line, font=kf, fill=hex2rgb(c["text"]), anchor="lm")
        y += 60 + 46 * (len(kl) - 1) + 26

    # pastki qism
    d.line([(M, H - 120), (W - M, H - 120)], fill=hex2rgb(c["muted"]) + (0,), width=1)
    d.rectangle([M, H - 121, W - M, H - 119], fill=hex2rgb(c["accent"], 90))
    ff = font("medium", 28)
    d.text((M, H - 72), ch.get("channel", ""), font=font("bold", 30), fill=hex2rgb(c["text"]), anchor="lm")
    d.text((W - M, H - 72), ch.get("hashtag_rubric", ""), font=ff, fill=hex2rgb(c["accent"]), anchor="rm")

    out.parent.mkdir(parents=True, exist_ok=True)
    img.convert("RGB").save(out, quality=95)
    return out


# ---------- video slaydlari ----------

def slide(post: dict, ch: dict, n: int, idx: int, total: int, out: Path, W=1080, H=1920) -> Path:
    c = ch["colors"]
    img = background(W, H, c)
    d = ImageDraw.Draw(img)
    M = 90
    s = post["slides"][idx]

    paste_logo(img, ch, M, 110, 96)
    pill(d, W - M, 124, lesson_label(ch, n), c, font("bold", 32), right_align=True)

    # progress chiziqlari
    gap, bw = 12, (W - 2 * M - 12 * (total - 1)) / total
    for k in range(total):
        x0 = M + k * (bw + gap)
        col = hex2rgb(c["accent"]) if k <= idx else hex2rgb(c["muted"], 70)
        d.rounded_rectangle([x0, 290, x0 + bw, 298], radius=4, fill=col)

    if idx == 0:   # sarlavha slaydi
        hf, hl = fit_text(d, post["title"], "display", 112, 72, W - 2 * M, 5)
        bf, bl = fit_text(d, s["text"] or post["subtitle"], "medium", 52, 38, W - 2 * M, 6)
        h_col, b_col, h_lh, b_lh = c["text"], c["muted"], 1.12, 1.4
    else:
        hf, hl = fit_text(d, s["heading"], "display", 84, 56, W - 2 * M, 3)
        bf, bl = fit_text(d, s["text"], "semi", 60, 40, W - 2 * M, 9)
        h_col, b_col, h_lh, b_lh = c["accent"], c["text"], 1.15, 1.42
    block = len(hl) * int(hf.size * h_lh) + 120 + len(bl) * int(bf.size * b_lh)
    top, bottom = 330, H - 230
    y = top + max(0, (bottom - top - block) // 2) - 40     # vertikal markazlash

    # orqa fonda katta, juda xira yulduz
    deco = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    star(ImageDraw.Draw(deco), W - 60, y + block + 260, 260, hex2rgb(c["accent"], 22), width=4)
    img.alpha_composite(deco)
    d = ImageDraw.Draw(img)

    for line in hl:
        d.text((M, y), line, font=hf, fill=hex2rgb(h_col))
        y += int(hf.size * h_lh)
    y += 40
    d.rounded_rectangle([M, y, M + 140, y + 10], radius=5, fill=hex2rgb(c["accent"]))
    y += 70
    for line in bl:
        d.text((M, y), line, font=bf, fill=hex2rgb(b_col))
        y += int(bf.size * b_lh)

    d.rectangle([M, H - 201, W - M, H - 199], fill=hex2rgb(c["accent"], 90))
    d.text((M, H - 140), ch.get("channel", ""), font=font("bold", 36), fill=hex2rgb(c["text"]), anchor="lm")
    d.text((W - M, H - 140), f"{idx + 1}/{total}", font=font("semi", 34), fill=hex2rgb(c["muted"]), anchor="rm")

    out.parent.mkdir(parents=True, exist_ok=True)
    img.convert("RGB").save(out, quality=95)
    return out
