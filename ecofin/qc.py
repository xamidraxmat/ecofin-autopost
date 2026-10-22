"""5-bosqich: sifat nazorati (avtomatik tekshiruvlar + Gemini muharrir-shariat ekspert)."""
from __future__ import annotations

import html
import re

from . import llm

ALLOWED_TAG = re.compile(r"</?b>")


def clean_caption(text: str) -> str:
    """Telegram HTML uchun xavfsiz matn: faqat <b> teglari qoladi."""
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)          # markdown qoldiqlari
    parts = re.split(r"(</?b>)", text)
    out = "".join(p if ALLOWED_TAG.fullmatch(p) else html.escape(p, quote=False) for p in parts)
    # ochiq qolgan <b> ni yopish
    if out.count("<b>") > out.count("</b>"):
        out += "</b>" * (out.count("<b>") - out.count("</b>"))
    return re.sub(r"\n{3,}", "\n\n", out).strip()


def full_caption(post: dict) -> str:
    tags = " ".join(t if t.startswith("#") else f"#{t}" for t in post.get("hashtags", []))
    return f"{clean_caption(post['caption'])}\n\n{html.escape(tags)}".strip()


def mechanical_checks(post: dict, ch: dict) -> list[str]:
    issues = []
    for field in ("title", "subtitle", "caption", "hashtags", "slides", "key_points"):
        if not post.get(field):
            issues.append(f"'{field}' maydoni bo'sh.")
    if issues:
        return issues
    cap = full_caption(post)
    visible = re.sub(r"<[^>]+>", "", cap)
    if len(visible) > 1024:
        issues.append(f"Caption is {len(visible)} characters; must be under 1024 including hashtags. Shorten it.")
    if len(post["title"]) > 70:
        issues.append("Title too long for the image (max 55 characters).")
    if not (4 <= len(post["slides"]) <= 7):
        issues.append("Need 5-6 slides.")
    for s in post["slides"]:
        if re.search(r"[#%$€]|\d{3,}", s.get("narration", "")):
            issues.append("Narration must spell numbers and symbols as words (no #, %, $ or long digit groups).")
            break
    if ch["language"] == "uz" and re.search(r"[а-яА-ЯёЁ]", post["caption"]):
        issues.append("Caption contains Cyrillic letters; use Latin script only.")
    tag0 = ch.get("hashtag_rubric")
    if tag0 and post["hashtags"][0].lower() != tag0.lower():
        post["hashtags"] = [tag0] + [t for t in post["hashtags"] if t.lower() != tag0.lower()]
    return issues


def ai_review(post: dict, topic: dict, ch: dict) -> dict:
    prompt = f"""You are the chief editor and Shariah reviewer of an Islamic finance education channel.
Review this lesson draft (language: {ch['language']}). Topic: "{topic['en']}".

TITLE: {post['title']}
CAPTION:
{post['caption']}
SLIDES: {[(s['heading'], s['text']) for s in post['slides']]}

Check strictly:
1. Shariah accuracy vs AAOIFI standards and majority scholarly view; no fatwa-like personal verdicts;
   disagreements presented fairly.
2. Factual accuracy: no invented numbers, laws, quotes or Quran/Hadith references; references must be correct.
3. Language quality: natural, grammatical, correct spelling (for Uzbek: Latin script, oʻ/gʻ).
4. Teaching value for beginners: clear definition, concrete example, practical takeaway.
5. Engagement: strong first line, readable formatting, ends with question or next step.

Return JSON: {{"score": 1-10 overall, "shariah_ok": true/false, "facts_ok": true/false,
"issues": ["specific problems"], "fix_instructions": "concise instructions for the writer"}}"""
    return llm.generate_json(prompt, temperature=0.2)


def review(post: dict, topic: dict, ch: dict, min_score: int) -> tuple[bool, dict]:
    mech = mechanical_checks(post, ch)
    try:
        ai = ai_review(post, topic, ch)
    except llm.LLMError as e:
        ai = {"score": 0, "shariah_ok": False, "facts_ok": False,
              "issues": [f"AI tekshiruv bajarilmadi: {e}"], "fix_instructions": ""}
    ok = (not mech and ai.get("score", 0) >= min_score
          and ai.get("shariah_ok") and ai.get("facts_ok", True))
    report = {**ai, "mechanical_issues": mech}
    return bool(ok), report


def feedback_text(report: dict) -> str:
    lines = report.get("mechanical_issues", []) + report.get("issues", [])
    if report.get("fix_instructions"):
        lines.append(report["fix_instructions"])
    return "\n".join(f"- {l}" for l in lines)
