"""EcoFin-i avtopost agenti — bosh boshqaruv.

Buyruqlar:
  python -m ecofin.main tick                      # jadval bo'yicha hamma ishni bajaradi (GitHub Actions shu buyruqni chaqiradi)
  python -m ecofin.main generate --channel uz     # hozir draft tayyorlab, tasdiqlashga yuborish
  python -m ecofin.main publish  --channel uz     # bugungi tasdiqlangan postni hozir chiqarish
  python -m ecofin.main demo     --channel uz     # API'siz sinov: namunaviy post rasm/audio/video yasaydi
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import traceback
from datetime import datetime, timedelta
from pathlib import Path

from . import audio, image, qc, topics, video, writer
from .config import (DRAFTS_DIR, ROOT, STATE_DIR, all_channels, channel, common, env,
                     log, now_local, read_state, write_state)
from .telegram import TG, approval_buttons

LEAD_HOURS = 3        # post vaqtidan necha soat oldin draft tayyorlanadi
GRACE_HOURS = 6       # post vaqtidan keyin necha soatgacha kechikib chiqarish mumkin
EARLY_MIN = 10        # GitHub jadvali uchun: post vaqtidan 10 daqiqa oldin ham chiqarsa bo'ladi
DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


# ---------------- draft fayllari ----------------

def draft_path(ch_id: str, day: str) -> Path:
    return DRAFTS_DIR / ch_id / f"{day}.json"


def load_draft(ch_id: str, day: str) -> dict | None:
    p = draft_path(ch_id, day)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def save_draft(d: dict) -> None:
    p = draft_path(d["channel"], d["day"])
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")


def workdir(ch_id: str, day: str) -> Path:
    w = ROOT / "out" / ch_id / day
    w.mkdir(parents=True, exist_ok=True)
    return w


# ---------------- 1-5 bosqichlar: tayyorlash ----------------

def create_content(ch: dict, state: dict, feedback_extra: str = "") -> dict:
    idx, topic = topics.next_topic(ch, state)
    n = idx + 1
    log(f"Mavzu #{n}: {topic['uz' if ch['language'] == 'uz' else 'en']}")
    notes = writer.research(topic, ch)
    qcfg = common().get("quality", {})
    feedback, post, report, passed = feedback_extra, None, {}, False
    for attempt in range(qcfg.get("max_rewrites", 2) + 1):
        post = writer.write_post(topic, ch, n, notes, feedback)
        passed, report = qc.review(post, topic, ch, qcfg.get("min_score", 8))
        log(f"Sifat nazorati (urinish {attempt + 1}): ball={report.get('score')} o'tdi={passed}")
        if passed:
            break
        feedback = qc.feedback_text(report)
    return {"topic_index": idx, "lesson": n, "topic": topic, "notes": notes,
            "post": post, "qc": report, "qc_passed": passed}


def ensure_ffmpeg() -> None:
    if not shutil.which("ffmpeg"):
        log("FFmpeg o'rnatilmoqda...")
        subprocess.run("sudo apt-get update -qq && sudo apt-get install -y -qq ffmpeg",
                       shell=True, check=True)


def render_media(content: dict, ch: dict, wd: Path) -> dict:
    post, n, media = content["post"], content["lesson"], ch.get("media", {})
    ensure_ffmpeg()
    files = {}
    if media.get("image", True):
        files["image"] = image.post_card(post, content["topic"], ch, n, wd / "card.jpg")
        log("Rasm tayyor.")
    if media.get("audio", True) or media.get("video", True):
        parts, full = audio.narrate_slides(post, ch, wd)
        if media.get("audio", True):
            files["audio"] = full
            log(f"Audio tayyor ({audio.duration(full):.0f} s).")
        if media.get("video", True):
            files["video"] = video.build(post, ch, n, parts, wd)
            files["thumb"] = wd / "thumb.jpg"
            log(f"Video tayyor ({audio.duration(files['video']):.0f} s).")
    return files


def qc_summary(content: dict) -> str:
    r = content["qc"]
    mark = "✅" if content["qc_passed"] else "⚠️"
    lines = [f"{mark} <b>Sifat nazorati:</b> {r.get('score', '?')}/10",
             f"Shariat: {'✅' if r.get('shariah_ok') else '⚠️'}  Faktlar: {'✅' if r.get('facts_ok') else '⚠️'}"]
    issues = (r.get("mechanical_issues") or []) + (r.get("issues") or [])
    if issues:
        lines.append("Izohlar:\n" + "\n".join(f"• {qc.clean_caption(i)}" for i in issues[:5]))
    return "\n".join(lines)


def send_preview(tg: TG, ch: dict, d: dict, files: dict, admin: str, ask: bool) -> None:
    """Admin'ga post qanday ko'rinishini yuboradi va Telegram file_id'larni saqlaydi."""
    cap = qc.full_caption(d["post"])
    ids = {}
    head = f"📝 <b>{ch['channel_name']}</b> ({ch['channel']}) — {d['day']} {ch['post_time']} uchun draft"
    tg.text(admin, head, silent=not ask)
    if "image" in files:
        _, ids["image"] = tg.photo(admin, files["image"], caption=cap if len(cap) <= 1024 else None, silent=True)
    if "audio" in files:
        _, ids["audio"] = tg.audio(admin, files["audio"], title=d["post"]["title"],
                                   performer=ch["channel_name"], silent=True)
    if "video" in files:
        vc = common().get("video", {})
        _, ids["video"] = tg.video(admin, files["video"], thumb=files.get("thumb"),
                                   w=vc.get("width", 1080), h=vc.get("height", 1920), silent=True)
    d["file_ids"] = ids
    markup = approval_buttons(f"{ch['id']}:{d['day']}") if ask else None
    note = qc_summary(d) + ("\n\nPostni tasdiqlaysizmi?" if ask else "\n\nAvtomatik rejim: vaqtida chiqadi.")
    msg = tg.text(admin, note, markup=markup, silent=not ask)
    d["admin_msg_id"] = msg["message_id"]


def generate(ch_id: str, day: str | None = None, feedback: str = "") -> dict:
    ch = channel(ch_id)
    day = day or now_local(ch["timezone"]).strftime("%Y-%m-%d")
    state = read_state(ch_id)
    content = create_content(ch, state, feedback)
    write_state(ch_id, state)              # yangi mavzular qo'shilgan bo'lishi mumkin
    files = render_media(content, ch, workdir(ch_id, day))
    ask = ch.get("require_approval", True) or not content["qc_passed"]
    d = {"channel": ch_id, "day": day, "status": "pending" if ask else "approved",
         "created": datetime.utcnow().isoformat(timespec="seconds") + "Z", **content}
    tg = TG()
    send_preview(tg, ch, d, files, env("ADMIN_CHAT_ID"), ask)
    save_draft(d)
    log(f"Draft saqlandi: {draft_path(ch_id, day).relative_to(ROOT)} (holat: {d['status']})")
    return d


# ---------------- 6-bosqich: chiqarish ----------------

def publish(ch_id: str, d: dict, tg: TG | None = None) -> None:
    ch, tg = channel(ch_id), tg or TG()
    post, ids, chat = d["post"], d.get("file_ids", {}), ch["channel"]
    cap = qc.full_caption(post)
    lesson = image.lesson_label(ch, d["lesson"]).capitalize()
    if ids.get("image") and len(cap) <= 1024:
        msg, _ = tg.photo(chat, ids["image"], caption=cap)
    else:
        if ids.get("image"):
            tg.photo(chat, ids["image"])
        msg = tg.text(chat, cap)
    if ids.get("audio"):
        a_cap = f"🎧 {lesson}: audio" if ch["language"] == "uz" else f"🎧 {lesson}: audio"
        tg.audio(chat, ids["audio"], title=post["title"], performer=ch["channel_name"],
                 caption=a_cap, silent=True)
    if ids.get("video"):
        v_cap = f"🎬 {lesson}: qisqa video-dars" if ch["language"] == "uz" else f"🎬 {lesson}: short video lesson"
        tg.video(chat, ids["video"], caption=v_cap, silent=True)

    d["status"], d["published_at"] = "published", datetime.utcnow().isoformat(timespec="seconds") + "Z"
    d["channel_message_id"] = msg["message_id"]
    save_draft(d)
    state = read_state(ch_id)
    state["next_topic"] = max(state.get("next_topic", 0), d["topic_index"] + 1)
    state.setdefault("history", []).append({"day": d["day"], "lesson": d["lesson"], "title": post["title"]})
    write_state(ch_id, state)
    link = f"https://t.me/{chat.lstrip('@')}/{msg['message_id']}" if str(chat).startswith("@") else ""
    tg.text(env("ADMIN_CHAT_ID"), f"🚀 {ch['channel_name']}: {d['lesson']}-dars chiqdi. {link}", silent=True)
    log(f"Chiqarildi: {chat} #{msg['message_id']}")


# ---------------- admin tugmalari ----------------

def process_buttons(tg: TG, admin: str) -> None:
    bot_state_path = STATE_DIR / "_bot.json"
    bs = json.loads(bot_state_path.read_text()) if bot_state_path.exists() else {"offset": 0}
    for upd in tg.updates(bs["offset"]):
        bs["offset"] = upd["update_id"] + 1
        cq = upd.get("callback_query")
        if not cq:
            continue
        if str(cq["from"]["id"]) != str(admin):
            tg.answer(cq["id"], "Ruxsat yo'q")
            continue
        try:
            action, key = cq["data"].split("|", 1)
            ch_id, day = key.split(":", 1)
        except ValueError:
            continue
        d = load_draft(ch_id, day)
        if not d or d["status"] in ("published", "skipped"):
            tg.answer(cq["id"], "Bu draft endi faol emas")
            continue
        d["status"] = {"ok": "approved", "no": "rejected", "re": "regen"}[action]
        save_draft(d)
        tg.clear_buttons(cq["message"]["chat"]["id"], cq["message"]["message_id"])
        reply = {"ok": "✅ Tasdiqlandi — vaqtida chiqadi",
                 "no": "❌ Bekor qilindi. Mavzu ertaga qayta olinadi",
                 "re": "🔄 Qayta yoziladi (keyingi tekshiruvda)"}[action]
        tg.answer(cq["id"], reply)
        tg.text(admin, f"{reply} ({ch_id}, {day})", silent=True)
        log(f"Admin javobi: {ch_id} {day} -> {d['status']}")
    STATE_DIR.mkdir(exist_ok=True)
    bot_state_path.write_text(json.dumps(bs))


# ---------------- jadval: tick ----------------

def tick() -> None:
    tg, admin = TG(), env("ADMIN_CHAT_ID")
    process_buttons(tg, admin)
    for ch_id in all_channels():
        ch = channel(ch_id)
        if not ch.get("enabled", True):
            continue
        try:
            tick_channel(ch, tg, admin)
        except Exception as e:
            log(f"[{ch_id}] XATO: {e}")
            traceback.print_exc()
            try:
                tg.text(admin, f"⚠️ {ch['channel_name']} agentida xato:\n<code>{qc.clean_caption(str(e))[:900]}</code>")
            except Exception:
                pass
    cleanup()


def tick_channel(ch: dict, tg: TG, admin: str) -> None:
    now = now_local(ch["timezone"])
    day = now.strftime("%Y-%m-%d")
    if DAYS[now.weekday()] not in [x.lower()[:3] for x in ch.get("days", DAYS)]:
        return
    hh, mm = map(int, ch["post_time"].split(":"))
    pub = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
    d = load_draft(ch["id"], day)

    if d and d["status"] == "regen":
        tg.text(admin, f"🔄 {ch['channel_name']}: qayta yozilmoqda...", silent=True)
        d = generate(ch["id"], day, feedback="The editor asked for a fresh, better version.")
    elif d and d["status"] == "failed" and d.get("attempts", 0) < 3 and now < pub + timedelta(hours=GRACE_HOURS):
        d = None  # qayta urinish
    if d is None and pub - timedelta(hours=LEAD_HOURS) <= now < pub + timedelta(hours=GRACE_HOURS):
        prev = load_draft(ch["id"], day) or {}
        try:
            d = generate(ch["id"], day)
        except Exception:
            save_draft({"channel": ch["id"], "day": day, "status": "failed",
                        "attempts": prev.get("attempts", 0) + 1})
            raise
    if not d:
        return

    due = now >= pub - timedelta(minutes=EARLY_MIN)
    late = now >= pub + timedelta(hours=GRACE_HOURS)
    if d["status"] == "approved" and due and not late:
        publish(ch["id"], d, tg)
    elif d["status"] == "pending" and due:
        if ch.get("if_no_answer", "skip") == "publish" and d.get("qc_passed"):
            publish(ch["id"], d, tg)
        elif late:
            d["status"] = "skipped"
            save_draft(d)
            tg.clear_buttons(admin, d.get("admin_msg_id"))
            tg.text(admin, f"⏭ {ch['channel_name']}: {day} posti javob bo'lmagani uchun chiqarilmadi.")


def cleanup() -> None:
    keep = common().get("keep_drafts_days", 7)
    limit = datetime.now() - timedelta(days=keep)
    for p in DRAFTS_DIR.glob("*/*.json"):
        try:
            if datetime.strptime(p.stem, "%Y-%m-%d") < limit:
                p.unlink()
        except ValueError:
            pass
    shutil.rmtree(ROOT / "out", ignore_errors=True)


# ---------------- demo (API'siz sinov) ----------------

def demo(ch_id: str, sample: Path) -> None:
    ch = channel(ch_id)
    content = json.loads(sample.read_text(encoding="utf-8"))
    content.setdefault("qc", {"score": "-", "shariah_ok": True, "facts_ok": True})
    content["qc"]["mechanical_issues"] = qc.mechanical_checks(content["post"], ch)
    wd = workdir(ch_id, "demo")
    files = render_media(content, ch, wd)
    (wd / "caption.html").write_text(qc.full_caption(content["post"]), encoding="utf-8")
    log(f"Avtomatik tekshiruv izohlari: {content['qc']['mechanical_issues'] or 'yo`q'}")
    log("Fayllar: " + ", ".join(str(p.relative_to(ROOT)) for p in files.values()))


def main() -> None:
    ap = argparse.ArgumentParser(description="EcoFin-i avtopost agenti")
    ap.add_argument("command", choices=["tick", "generate", "publish", "demo"])
    ap.add_argument("--channel", default="uz")
    ap.add_argument("--day", help="YYYY-MM-DD (standart: bugun)")
    ap.add_argument("--sample", default="samples/uz_lesson1.json")
    a = ap.parse_args()
    if a.command == "tick":
        tick()
    elif a.command == "generate":
        generate(a.channel, a.day)
    elif a.command == "publish":
        ch = channel(a.channel)
        day = a.day or now_local(ch["timezone"]).strftime("%Y-%m-%d")
        d = load_draft(a.channel, day)
        if not d or d.get("status") in ("published", "failed"):
            raise SystemExit("Chiqarish uchun tayyor draft topilmadi.")
        publish(a.channel, d)
    elif a.command == "demo":
        demo(a.channel, ROOT / a.sample)


if __name__ == "__main__":
    main()
