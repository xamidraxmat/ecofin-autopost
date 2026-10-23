"""Maxsus postlar: admin Telegram'da botga buyruq beradi.

  /post <ma'lumot>         -> bot e'lon/reklama matni va logoli banner tayyorlaydi
  /post (rasm bilan)       -> rasm izohiga /post va ma'lumot yozilsa, o'sha rasm ishlatiladi
  /logo (rasm yoki fayl)   -> kanal logosini o'rnatadi
  /yordam                  -> qo'llanma
"""
from __future__ import annotations

import html
import json
import re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from PIL import Image

from . import image, llm, qc
from .config import ROOT, STATE_DIR, all_channels, channel, log
from .telegram import TG, approval_buttons

QUEUE = STATE_DIR / "_custom.json"

HELP = """<b>EcoFin-i bot buyruqlari</b>

📣 <b>/post</b> — maxsus post (e'lon, reklama, yangilik)
Masalan:
<code>/post Yangi kurs: "Islomiy moliya asoslari". Boshlovchilar uchun, 8 ta onlayn dars, 1-noyabrdan. Narxi 300 000 so'm, sertifikat beriladi. Ro'yxatdan o'tish: @Khamid_r</code>

🖼 O'z rasmingiz bilan: rasmni yuboring va <b>izohiga</b> /post va ma'lumotni yozing.

👤 <b>/muallif</b> — kurs e'lonlaridagi muallif bloki. Rasmingizni yuboring, izohiga yozing:
<code>/muallif
Ism: Ism Familiya
Unvon: Islomiy moliya bo'yicha ekspert
Sertifikatlar: AAOIFI CSAA, CIFE
Tajriba: 8 yillik bank tajribasi</code>
Faqat <b>/muallif</b> yozsangiz, hozirgi ma'lumot va banner ko'rinishini ko'rsatadi.

🏷 <b>/logo</b> — kanal logosini o'rnatish: logoni <b>fayl sifatida</b> (📎 → File) yuboring va izohiga /logo yozing. Shaffof fon saqlanib qoladi.

Bot har soatda (taxminan :05 da) tekshiradi. Tezlatish uchun: GitHub → Actions → Run workflow → <code>tick</code>."""


def _channel_id(args: str) -> tuple[str, str]:
    """'/post en ...' -> ('en', '...'); standart: birinchi kanal."""
    chans = all_channels()
    first, _, rest = args.partition(" ")
    if first.lower() in chans and first.lower() != "common":
        return first.lower(), rest.strip()
    return ("uz" if "uz" in chans else chans[0]), args.strip()


def _read_queue() -> list:
    return json.loads(QUEUE.read_text(encoding="utf-8")) if QUEUE.exists() else []


def _write_queue(q: list) -> None:
    STATE_DIR.mkdir(exist_ok=True)
    QUEUE.write_text(json.dumps(q, ensure_ascii=False, indent=2), encoding="utf-8")


def logo_path(ch_id: str) -> Path:
    return STATE_DIR / f"logo_{ch_id}.png"


# ---------------- admin xabarlarini qabul qilish ----------------

def handle_message(tg: TG, admin: str, msg: dict) -> None:
    if str(msg.get("from", {}).get("id")) != str(admin):
        return
    text = (msg.get("text") or msg.get("caption") or "").strip()
    cmd, _, args = text.partition(" ") if text.startswith("/") else ("", "", text)
    cmd = cmd.split("@")[0].lower()
    if "\n" in cmd:  # "/post\nmatn" holati
        cmd, _, more = cmd.partition("\n")
        args = more + " " + args
    file_id = None
    if msg.get("photo"):
        file_id = msg["photo"][-1]["file_id"]
    elif msg.get("document", {}).get("mime_type", "").startswith("image/"):
        file_id = msg["document"]["file_id"]

    if cmd == "/logo":
        ch_id, _ = _channel_id(args)
        if not file_id:
            tg.text(admin, "🏷 Logoni rasm yoki fayl sifatida yuboring va <b>izohiga</b> /logo deb yozing.")
            return
        _save_logo(tg, admin, ch_id, file_id)
    elif cmd == "/post":
        ch_id, brief = _channel_id(args)
        if len(brief) < 15 and not file_id:
            tg.text(admin, "📣 /post dan keyin e'lon haqida ma'lumot yozing.\n\n" + HELP.split("\n\n", 2)[1])
            return
        q = _read_queue()
        item = {"id": datetime.now(ZoneInfo("UTC")).strftime("%Y%m%d-%H%M%S") + f"-{len(q)}",
                "channel": ch_id, "brief": brief,
                "photo": msg["photo"][-1]["file_id"] if msg.get("photo") else None,
                "status": "new"}
        q.append(item)
        _write_queue(q)
        tg.text(admin, "📥 Qabul qilindi. Bot keyingi tekshiruvda (1 soat ichida) post tayyorlab, "
                       "sizga ko'rsatadi.\nTezlatish: GitHub → Actions → Run workflow → <code>tick</code>")
        log(f"Maxsus post navbatga qo'shildi: {item['id']}")
    elif cmd == "/muallif":
        ch_id, rest = _channel_id(args)
        _save_author(tg, admin, ch_id, rest, msg["photo"][-1]["file_id"] if msg.get("photo") else file_id)
    elif cmd in ("/start", "/yordam", "/help"):
        tg.text(admin, HELP)


def _save_logo(tg: TG, admin: str, ch_id: str, file_id: str) -> None:
    tmp = ROOT / "out" / "logo_upload"
    tg.download(file_id, tmp)
    img = Image.open(tmp).convert("RGBA")
    bbox = img.getbbox()            # shaffof chetlarni kesish
    if bbox:
        img = img.crop(bbox)
    if img.height > 600:
        img = img.resize((int(img.width * 600 / img.height), 600), Image.LANCZOS)
    STATE_DIR.mkdir(exist_ok=True)
    img.save(logo_path(ch_id))
    ch = channel(ch_id)
    sample = json.loads((ROOT / "samples" / "uz_lesson1.json").read_text(encoding="utf-8"))
    card = image.post_card(sample["post"], sample["topic"], ch, 1, ROOT / "out" / "logo_preview.jpg")
    tg.photo(admin, card, caption="✅ Logo saqlandi. Postlar endi shunday ko'rinadi.")
    log(f"Logo yangilandi: {logo_path(ch_id).name}")


FIELDS = {"ism": "name", "name": "name", "unvon": "title", "lavozim": "title", "title": "title",
          "sertifikatlar": "credentials", "sertifikat": "credentials", "certificates": "credentials",
          "tajriba": "bio", "bio": "bio"}


def _save_author(tg: TG, admin: str, ch_id: str, text: str, file_id: str | None) -> None:
    path = STATE_DIR / f"author_{ch_id}.json"
    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    changed = False
    for line in text.replace(";", "\n").splitlines():
        key, sep, val = line.partition(":")
        field = FIELDS.get(key.strip().lower())
        if sep and field:
            val = val.strip()
            data[field] = [v.strip() for v in re.split(r"[,•|]", val) if v.strip()][:6] if field == "credentials" else val
            changed = True
    if file_id:
        photo = STATE_DIR / f"author_{ch_id}.jpg"
        tg.download(file_id, ROOT / "out" / "author_upload")
        Image.open(ROOT / "out" / "author_upload").convert("RGB").save(photo, quality=92)
        data["photo"] = f"state/author_{ch_id}.jpg"
        changed = True
    if changed:
        STATE_DIR.mkdir(exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        log("Muallif ma'lumoti yangilandi")
    ch = channel(ch_id)
    a = ch.get("author") or {}
    if not a.get("name"):
        tg.text(admin, "👤 Muallif ma'lumoti hali yo'q. Namuna:\n\n<code>/muallif\nIsm: Ism Familiya\n"
                       "Unvon: Islomiy moliya bo'yicha ekspert\nSertifikatlar: AAOIFI CSAA, CIFE\n"
                       "Tajriba: 8 yillik bank tajribasi</code>\n\nRasmingizni ham shu izoh bilan yuboring.")
        return
    demo = {"title": "Kurs nomi shu yerda turadi", "subtitle": "E'lonning qisqa mazmuni",
            "key_points": ["Kursning birinchi afzalligi", "Ikkinchi afzallik"]}
    card = image.post_card(demo, {}, ch, 0, ROOT / "out" / "author_preview.jpg", badge="YANGI KURS",
                           kicker="Islomiy moliya", with_author=True)
    info = (f"✅ Saqlandi. Kurs e'lonlarida shunday ko'rinadi.\n\n<b>{html.escape(a['name'], False)}</b>\n"
            f"{html.escape(a.get('title') or '—', False)}\nSertifikatlar: {html.escape(', '.join(a.get('credentials') or []) or '—', False)}\n"
            f"Tajriba: {html.escape(a.get('bio') or '—', False)}\nRasm: {'bor ✅' if a.get('photo') and (ROOT / a['photo']).is_file() else 'yo`q — rasm bilan /muallif yuboring'}")
    tg.photo(admin, card, caption=info[:1024])


# ---------------- maxsus post tayyorlash ----------------

AD_PROMPT = """Write a promotional Telegram post for the channel "{name}" ({handle}).
Language: {lang}. The channel teaches Islamic finance; tone: trustworthy, warm, professional, not pushy.

The admin's brief (the ONLY source of facts):
\"\"\"{brief}\"\"\"
{author}{fix}
Rules:
- Use ONLY facts from the brief. Never invent prices, dates, discounts, contacts, numbers or guarantees.
  If something is not in the brief, do not mention it.
- Copy every contact (usernames, links, phone numbers) exactly as written in the brief.
- Structure: strong first line (hook) -> why it matters -> what you get (3-5 lines with ▫️) ->
  practical details from the brief -> clear call to action with the contact.
- Max {max_chars} characters, plain text with line breaks; <b>bold</b> allowed for 2-4 phrases; no markdown.
Return ONLY JSON:
{{"badge": "short label for the image, max 14 chars, e.g. YANGI KURS / E'LON",
  "title": "headline for the image, max 55 chars",
  "subtitle": "one line, max 80 chars",
  "key_points": ["3 short benefits, each max 45 chars"],
  "caption": "the post text",
  "hashtags": ["2-4 hashtags"],
  "is_course_ad": true if this post announces or promotes a course/training/webinar, else false}}"""

AUTHOR_BLOCK = """
Course instructor (verified facts, use them):
- Name: {name}
- Title: {title}
- Certificates: {creds}
- Bio: {bio}
If this is a course announcement, add a short credibility line before the call to action, e.g.
"👤 Kurs muallifi: <name> — <1-3 key certificates>". Do not exaggerate or add titles not listed.
"""

LANG = {"uz": "Uzbek (Latin script, oʻ/gʻ)", "en": "English"}


def _contacts(text: str) -> list[str]:
    return re.findall(r"@\w{4,}|https?://\S+|t\.me/\S+|\+?\d[\d\s\-]{8,}\d", text)


def author_info(ch: dict) -> str:
    a = ch.get("author") or {}
    if not a.get("name"):
        return ""
    return AUTHOR_BLOCK.format(name=a["name"], title=a.get("title") or "-",
                               creds=", ".join(a.get("credentials") or []) or "-", bio=a.get("bio") or "-")


def write_ad(ch: dict, brief: str) -> dict:
    fix, post = "", {}
    for _ in range(3):
        post = llm.generate_json(AD_PROMPT.format(
            name=ch["channel_name"], handle=ch["channel"], lang=LANG.get(ch["language"], ch["language"]),
            brief=brief, author=author_info(ch), fix=fix,
            max_chars=ch.get("post_max_chars", 1000) - 90), temperature=0.6)
        problems = []
        visible = re.sub(r"<[^>]+>", "", qc.full_caption(post)) if post.get("caption") else ""
        if not visible:
            problems.append("caption is empty")
        if len(visible) > 1024:
            problems.append(f"caption is {len(visible)} characters, must be under 930")
        missing = [c for c in _contacts(brief) if c.strip() not in post.get("caption", "")]
        if missing:
            problems.append("the caption must contain these contacts exactly: " + ", ".join(missing))
        if not problems:
            return post
        fix = "\nFIX THESE PROBLEMS: " + "; ".join(problems) + "\n"
    return post


def build_draft(tg: TG, admin: str, ch_id: str, item: dict, feedback: str = "") -> dict:
    ch = channel(ch_id)
    brief = item["brief"] + (f"\n\nEditor feedback: {feedback}" if feedback else "")
    post = write_ad(ch, brief) if item["brief"] else {"caption": "", "hashtags": []}
    d = {"channel": ch_id, "day": f"custom-{item['id']}", "kind": "custom", "status": "pending",
         "brief": item["brief"], "photo": item.get("photo"), "post": post, "file_ids": {}}
    cap = qc.full_caption(post) if post.get("caption") else ""
    tg.text(admin, f"📣 <b>Maxsus post</b> ({ch['channel']}) — ko'rib chiqing:", silent=True)
    if item.get("photo"):
        _, d["file_ids"]["image"] = tg.photo(admin, item["photo"], caption=cap or None, silent=True)
    else:
        card = image.post_card(post, {}, ch, 0, ROOT / "out" / f"{d['day']}.jpg",
                               badge=post.get("badge") or "E'LON", with_author=bool(post.get("is_course_ad")),
                               kicker="Islomiy moliya" if ch["language"] == "uz" else "Islamic finance")
        _, d["file_ids"]["image"] = tg.photo(admin, card, caption=cap if len(cap) <= 1024 else None, silent=True)
    if len(cap) > 1024:
        tg.text(admin, cap, silent=True)
    m = tg.text(admin, "Chiqaraymi? ✅ bossangiz, keyingi tekshiruvda darhol kanalga chiqadi.",
                markup=approval_buttons(f"{ch_id}:{d['day']}"))
    d["admin_msg_id"] = m["message_id"]
    return d


def process(tg: TG, admin: str, load_draft, save_draft, publish) -> None:
    """Navbatdagi yangi so'rovlar, qayta yozish va tasdiqlangan maxsus postlar."""
    q = _read_queue()
    for item in q:
        if item["status"] != "new":
            continue
        try:
            d = build_draft(tg, admin, item["channel"], item)
            save_draft(d)
            item["status"] = "drafted"
        except Exception as e:
            item["status"] = "failed"
            tg.text(admin, f"⚠️ Maxsus postni tayyorlab bo'lmadi: <code>{html.escape(str(e))[:500]}</code>")
        _write_queue(q)

    for p in sorted((ROOT / "drafts").glob("*/custom-*.json")):
        d = json.loads(p.read_text(encoding="utf-8"))
        if d["status"] == "regen":
            item = {"id": d["day"].removeprefix("custom-"), "brief": d["brief"], "photo": d.get("photo")}
            nd = build_draft(tg, admin, d["channel"], item, feedback="Write a fresh, more compelling version.")
            save_draft(nd)
        elif d["status"] == "approved":
            publish(d["channel"], d, tg)
    # eski yozuvlarni tozalash
    _write_queue([i for i in q if i["status"] == "new"][-20:])
